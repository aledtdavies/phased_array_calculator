"""
Phased Array Focal Law Calculator: the Qt window (qtpy; PySide6).

    python python/qt_app.py

Plan step 2 (docs/plans/PLAN-2026-11-qt-vtk-migration.md): every feature of the Tk window
(app.py) on Qt, with the same calculation, table, exports and configuration files through
session.py. The views are matplotlib canvases for now; steps 3-4 move them to PyVista and
pyqtgraph.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("QT_API", "pyside6")
from qtpy import QtCore, QtGui, QtWidgets

from catalog import Catalog, CatalogError, default_catalog_dir
from qt_catalog_dialog import CatalogPicker
from qt_panels import MaterialPanel, ProbePanel, ScanPanel, SubAperturePanel, WedgePanel
from qt_view3d import Scene3DTab
from qt_views2d import DelayTab, RayTab
from session import (TABLE_HEADINGS, CatalogLinks, asset_message, build_solver, calculate,
                     law_result, write_laws_csv)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Phased Array Focal Law Calculator")
        self.resize(1300, 900)
        self.catalog = CatalogLinks()
        self.last_results = None

        # --- left: scrollable input panels, buttons ---
        self.probe_panel = ProbePanel()
        self.wedge_panel = WedgePanel()
        self.mat_panel = MaterialPanel()
        self.scan_panel = ScanPanel()
        self.sub_aperture_panel = SubAperturePanel()
        inner = QtWidgets.QWidget()
        col = QtWidgets.QVBoxLayout(inner)
        for p in self.panels():
            col.addWidget(p)
        buttons = QtWidgets.QHBoxLayout()
        self.calc_btn = QtWidgets.QPushButton("Calculate Laws")
        self.export_btn = QtWidgets.QPushButton("Export CSV")
        self.export_btn.setEnabled(False)
        buttons.addWidget(self.calc_btn)
        buttons.addWidget(self.export_btn)
        col.addLayout(buttons)
        col.addStretch(1)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340)
        dock = QtWidgets.QDockWidget("Setup")
        dock.setObjectName("setup")
        dock.setWidget(scroll)
        dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

        # --- right: tabs ---
        self.tabs = QtWidgets.QTabWidget()
        self.plot_tab = RayTab()
        self.tree = QtWidgets.QTableWidget(0, len(TABLE_HEADINGS))
        self.tree.setHorizontalHeaderLabels(TABLE_HEADINGS)
        self.tree.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tree.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tree.verticalHeader().setVisible(False)
        self.hist_tab = DelayTab()
        self.scene3d_tab = Scene3DTab()
        self.tabs.addTab(self.plot_tab, "Ray Tracing")
        self.tabs.addTab(self.tree, "Data Table")
        self.tabs.addTab(self.hist_tab, "Delays")
        self.tabs.addTab(self.scene3d_tab, "3D View")
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("Ready.")

        self._menu()
        self.calc_btn.clicked.connect(self.run_calculation)
        self.export_btn.clicked.connect(self.export_csv)
        self.tree.itemSelectionChanged.connect(self.on_table_select)
        self.probe_panel.probe_type_changed.connect(self.on_probe_type_changed)
        for tab in self.law_tabs():
            tab.element_selected.connect(self.select_element)
            tab.law_changed.connect(self.on_law_changed)
        self.plot_tab.focus_dragged.connect(self.on_focus_dragged)
        self.on_probe_type_changed(self.probe_panel.type_combo.currentText())

    # -- dialogs (overridable, so tests run without user input) -----------------------
    def info(self, title, text):
        QtWidgets.QMessageBox.information(self, title, text)

    def warn(self, title, text):
        QtWidgets.QMessageBox.warning(self, title, text)

    def error(self, title, text):
        QtWidgets.QMessageBox.critical(self, title, text)

    def ask_open(self, title, filters, directory=""):
        return QtWidgets.QFileDialog.getOpenFileName(self, title, directory, filters)[0]

    def ask_save(self, title, filters, name=""):
        return QtWidgets.QFileDialog.getSaveFileName(self, title, name, filters)[0]

    def pick_catalog_entry(self, cat, kind):
        picker = CatalogPicker(self, cat, kind)
        return picker.selected if picker.exec() else None

    # -- structure ------------------------------------------------------------------
    def panels(self):
        return (self.probe_panel, self.wedge_panel, self.mat_panel, self.scan_panel,
                self.sub_aperture_panel)

    def _menu(self):
        m = self.menuBar().addMenu("&File")
        for entry in (("Save Configuration", self.save_config),
                      ("Load Configuration", self.load_config), None,
                      ("Export Element Coordinates", self.export_element_coords), None,
                      ("Load Probe from Catalogue...", lambda: self.load_from_catalog("probe")),
                      ("Load Wedge from Catalogue...", lambda: self.load_from_catalog("wedge")),
                      None, ("Exit", self.close)):
            if entry is None:
                m.addSeparator()
            else:
                m.addAction(*entry)

    def on_probe_type_changed(self, ptype):
        self.wedge_panel.update_visibility(ptype)
        self.scan_panel.update_visibility(ptype)
        self.sub_aperture_panel.update_visibility(ptype)

    # -- configuration --------------------------------------------------------------
    def config_dict(self):
        """The full setup as saved: panel values and any catalogue references (as app.py)."""
        config = {"probe": self.probe_panel.get_values(), "wedge": self.wedge_panel.get_values(),
                  "material": self.mat_panel.get_values(), "scan": self.scan_panel.get_values(),
                  "sub_aperture": self.sub_aperture_panel.get_values()}
        refs = self.catalog_status()
        if refs:
            config["catalog"] = refs
        return config

    def apply_config(self, config):
        """Set the panels from a saved configuration (either window's)."""
        for key, panel in (("probe", self.probe_panel), ("wedge", self.wedge_panel),
                           ("material", self.mat_panel), ("scan", self.scan_panel),
                           ("sub_aperture", self.sub_aperture_panel)):
            if key in config:
                panel.set_values(config[key])
        self.catalog.loaded(config, {"probe": self.probe_panel.get_values(),
                                     "wedge": self.wedge_panel.get_values()})

    def save_config(self):
        try:
            config = self.config_dict()
        except ValueError as e:
            self.error("Save Error", str(e))
            return
        path = self.ask_save("Save Configuration", "JSON Config (*.json);;All Files (*)")
        if not path:
            return
        try:
            with open(path, "w") as f:
                json.dump(config, f, indent=4)
            self.statusBar().showMessage(f"Configuration saved to {os.path.basename(path)}")
        except OSError as e:
            self.error("Save Error", str(e))

    def load_config(self):
        path = self.ask_open("Load Configuration", "JSON Config (*.json);;All Files (*)")
        if not path:
            return
        try:
            with open(path) as f:
                self.apply_config(json.load(f))
            self.statusBar().showMessage(f"Configuration loaded from {os.path.basename(path)}")
        except (OSError, ValueError, KeyError) as e:
            self.error("Load Error", str(e))

    # -- catalogues -----------------------------------------------------------------
    def catalog_status(self):
        return self.catalog.status({"probe": self.probe_panel.get_values(),
                                    "wedge": self.wedge_panel.get_values()})

    def wedge_outline_mm(self):
        return self.catalog.wedge_outline_mm(self.wedge_panel.get_values(),
                                         self.probe_panel.get_values().get("probe_type", "Linear"))

    def load_from_catalog(self, kind, path=None):
        """Fill the probe or wedge panel from a buildFE or nde-knowledge catalogue entry."""
        if path is None:
            path = self.ask_open(f"Open a {kind} catalogue (buildFE catalog/{kind}s.json or "
                                 f"nde-knowledge export)", "JSON catalogue (*.json);;All Files (*)",
                                 default_catalog_dir() or os.getcwd())
        if not path:
            return
        try:
            cat = Catalog(path)
            if not cat.entries(kind):
                raise CatalogError(f"{os.path.basename(path)} has no {kind}s")
            entry = self.pick_catalog_entry(cat, kind)
            if entry is None:
                return
            asset = cat.probe(entry) if kind == "probe" else cat.wedge(entry)
        except CatalogError as e:
            self.error("Catalogue", str(e))
            return
        if kind == "probe":
            self.probe_panel.set_values(asset.panel_values())
        else:
            self.wedge_panel.set_values(asset.panel_values())
            self.wedge_panel.material.setCurrentText("Custom")
        self.catalog.apply(kind, asset)
        self.statusBar().showMessage(f"{kind.capitalize()} from catalogue: {asset.ref.id}")
        self.info("Catalogue entry applied", asset_message(kind, asset))

    # -- calculation ----------------------------------------------------------------
    def get_solver(self):
        return build_solver(self.probe_panel.get_values(), self.wedge_panel.get_values(),
                            self.mat_panel.get_values(), self.sub_aperture_panel.get_values())

    def run_calculation(self):
        try:
            solver = self.get_solver()
            self.statusBar().showMessage("Calculating...")
            QtWidgets.QApplication.processEvents()
            calc = calculate(solver, self.scan_panel.get_values(),
                             self.probe_panel.get_values().get("probe_type", "Linear"))
        except Exception as e:      # shown, as the Tk window does; nothing is drawn
            self.error("Error", str(e))
            self.statusBar().showMessage("Error during calculation.")
            return

        self.tree.blockSignals(True)
        self.tree.setRowCount(0)
        for values, idx in calc.rows:
            r = self.tree.rowCount()
            self.tree.insertRow(r)
            for c, v in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(v))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setData(QtCore.Qt.UserRole, idx)
                self.tree.setItem(r, c, item)
        self.tree.blockSignals(False)

        self.last_results = calc.results
        if calc.focal_points:
            thickness_mm = self.mat_panel.get_values().get("thickness_mm", 0.0)
            outline_mm = self.wedge_outline_mm()
            self.plot_tab.update_plot(solver, calc.focal_points, calc.wave_type, results=calc.results,
                                      is_matrix=calc.is_matrix, component_thickness_mm=thickness_mm,
                                      outline_mm=outline_mm)
            self.scene3d_tab.update_plot(solver, calc.focal_points, calc.wave_type, results=calc.results,
                                         is_matrix=calc.is_matrix, component_thickness_mm=thickness_mm,
                                         outline_mm=outline_mm,
                                         element_size_m=self.catalog.element_size_m(self.probe_panel.get_values()))
            self.hist_tab.update_plot(solver, calc.focal_points, calc.wave_type,
                                      global_max_delay=calc.global_max_delay, results=calc.results,
                                      is_matrix=calc.is_matrix)
        else:
            for tab in (self.plot_tab, self.hist_tab, self.scene3d_tab):
                tab.clear_laws()

        if not calc.results:
            self.warn("No Results", "No valid focal laws could be calculated.\nPlease check your "
                                    "geometry, angles, and target coordinates.")
            self.statusBar().showMessage("Calculation complete. 0 laws generated.")
            self.export_btn.setEnabled(False)
        else:
            self.statusBar().showMessage(f"Calculation complete. {len(calc.results)} laws generated.")
            self.export_btn.setEnabled(True)

    def table_rows(self):
        """The Data Table's text, row by row (as the Tk window shows it)."""
        return [[self.tree.item(r, c).text() for c in range(self.tree.columnCount())]
                for r in range(self.tree.rowCount())]

    def law_tabs(self):
        return (self.plot_tab, self.hist_tab, self.scene3d_tab)

    def select_element(self, idx):
        """An element clicked in any view: show it selected in every view."""
        for tab in self.law_tabs():
            tab.highlight_element(idx)

    def on_law_changed(self, idx):
        """One tab chose sweep law idx: every tab shows it (hidden tabs draw it when shown)."""
        source = self.sender()
        for t in self.law_tabs():
            if t is not source and (t.custom is not None or t.current_idx != idx):
                t.show_law(idx, notify=False)

    def on_focus_dragged(self, x, z):
        """The X-Z focus dragged to (x, z) m: solve that law live and show it in every tab."""
        tab = self.plot_tab
        if tab.solver is None or not tab.focal_points:
            return
        y = float(tab.current_focal()[1])
        if not z > 0:
            self.statusBar().showMessage("The focus must be below the surface (Z > 0).")
            tab.reset_focus_marker()
            return
        try:
            result = law_result(tab.solver, (x, y, z), tab.wave_type)
        except (ValueError, ArithmeticError) as e:
            self.statusBar().showMessage(f"No law for that focus: {e}")
            tab.reset_focus_marker()
            return
        for t in self.law_tabs():
            t.set_custom(result, (x, y, z))
        self.statusBar().showMessage(f"Dragged focus: ({x*1e3:.1f}, {y*1e3:.1f}, {z*1e3:.1f}) mm "
                                     "(not in the sweep; the table and CSV are unchanged)")

    def on_table_select(self):
        rows = self.tree.selectionModel().selectedRows()
        if not rows:
            return
        idx = self.tree.item(rows[0].row(), 0).data(QtCore.Qt.UserRole)
        if idx is None:      # a refused law
            return
        for tab in self.law_tabs():
            tab.show_law(idx, notify=False)

    # -- exports ----------------------------------------------------------------------
    def export_csv(self):
        if not self.last_results:
            self.info("Export", "No data to export.")
            return
        path = self.ask_save("Export Focal Laws", "CSV File (*.csv);;All Files (*)", "focal_laws_gui.csv")
        if not path:
            return
        try:
            write_laws_csv(path, self.last_results)
        except OSError as e:
            self.error("Export Error", str(e))
            return
        self.statusBar().showMessage(f"Exported to {os.path.basename(path)}")
        self.info("Success", f"Exported to {os.path.basename(path)}")

    def export_element_coords(self):
        try:
            solver = self.get_solver()
        except ValueError as e:
            self.error("Export Error", f"Cannot formulate probe geometry: {e}")
            return
        path = self.ask_save("Export Element Coordinates",
                             "CSV File (*.csv);;MATLAB MAT File (*.mat);;MATLAB Script (*.m);;All Files (*)")
        if not path:
            return
        try:
            solver.export_element_positions(path)
        except OSError as e:
            self.error("Export Error", str(e))
            return
        self.statusBar().showMessage(f"Element coordinates exported to {os.path.basename(path)}")
        self.info("Success", f"Exported element coordinates to {os.path.basename(path)}")


    def closeEvent(self, event):      # noqa: N802 - Qt's name
        self.scene3d_tab.plotter.close()     # release the VTK render window
        super().closeEvent(event)


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
