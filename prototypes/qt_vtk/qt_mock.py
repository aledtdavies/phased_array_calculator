"""
PROTOTYPE (plan steps 2-4): the GUI shell on qtpy/PySide6 with a pyvistaqt 3D view and
pyqtgraph 2D views, all fed by the scene model and linked to one law slider.

    python qt_mock.py [buildFE/catalog folder]            interactive
    python qt_mock.py [folder] --screenshot               writes docs/plans/images/proto_qt_mock.png

The input panels are non-functional placeholders (layout only). The slider, table, 2D view,
3D view and delay chart are live: moving the slider redraws the law in every view.
"""
import os
import sys
import time

os.environ.setdefault("QT_API", "pyside6")
import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtGui, QtWidgets
from pyvistaqt import QtInteractor

from scene_model import build_scene, constant_depth_sweep, demo_setup, single_v_weld
from render_pyvista import add_scene, z_down_camera

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "plans", "images"))
pg.setConfigOptions(antialias=True, background="w", foreground="k")

QCOL = {"wedge": (34, 197, 94, 40), "weld": (245, 158, 11, 70), "coverage-leg1": (37, 99, 235, 30),
        "coverage-leg2": (124, 58, 237, 25), "component": (148, 163, 184, 25)}


def form(fields):
    box = QtWidgets.QWidget()
    lay = QtWidgets.QFormLayout(box)
    for label, widget in fields:
        lay.addRow(label, widget)
    return box


def spin(v, suffix="", dec=2):
    s = QtWidgets.QDoubleSpinBox()
    s.setDecimals(dec)
    s.setRange(-1e6, 1e6)
    s.setValue(v)
    s.setSuffix(suffix)
    return s


def combo(items):
    c = QtWidgets.QComboBox()
    c.addItems(items)
    return c


class Mock(QtWidgets.QMainWindow):
    def __init__(self, catalog_dir):
        super().__init__()
        self.setWindowTitle("Phased Array Focal Law Calculator - Qt/VTK prototype")
        self.resize(1700, 980)
        self.solver, self.outline, self.freq = demo_setup(catalog_dir)
        self.T = 0.025
        self.sweep = constant_depth_sweep(self.solver, np.arange(40, 71, 1.0), 0.020, wave="shear")
        self.weld = single_v_weld(self.sweep[len(self.sweep) // 2][1][0] + 0.040, self.T)

        # --- left dock: input panels (layout only) ---
        tool = QtWidgets.QToolBox()
        cat = QtWidgets.QLabel("<b>evident-2.25L64-A2</b><br>buildFE 0.1 &middot; hash 057554e1e4de "
                               "<span style='color:#15803d'>&#10003; ok</span>")
        tool.addItem(form([("Catalogue", cat), ("", QtWidgets.QPushButton("Load from catalogue...")),
                           ("Type", combo(["Linear", "Matrix", "Dual Linear", "Dual Matrix"])),
                           ("Elements", spin(64, "", 0)), ("Pitch", spin(0.75, " mm")),
                           ("Frequency", spin(2.25, " MHz")),
                           ("Sub-aperture", QtWidgets.QLabel("17 - 48 (32 active)"))]), "Probe")
        tool.addItem(form([("Catalogue", QtWidgets.QLabel("<b>evident-SA2-N55S</b> &#10003; ok")),
                           ("Angle", spin(36, " °")), ("Height @ el. 1", spin(5.0, " mm")),
                           ("Velocity", spin(2337, " m/s", 0)), ("Offset X", spin(4.0, " mm"))]), "Wedge")
        tool.addItem(form([("Material", combo(["Mild steel", "Stainless 304"])),
                           ("Thickness", spin(25, " mm")),
                           ("Weld", combo(["Single-V 60°", "None", "From DXF..."]))]), "Component")
        tool.addItem(form([("Focus", combo(["Constant depth", "Vertical line", "Sound path"])),
                           ("Wave", combo(["Shear", "Longitudinal"])),
                           ("Angles", QtWidgets.QLabel("40 - 70°, step 1°")),
                           ("Depth", spin(20, " mm")), ("Skips", combo(["Direct + 1st skip", "Direct"]))]),
                     "Scan")
        tool.setCurrentIndex(0)
        dock = QtWidgets.QDockWidget("Setup")
        dock.setWidget(tool)
        dock.setMinimumWidth(300)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

        # --- 3D view ---
        self.vtk = QtInteractor(self)
        self.vtk.set_background("white")

        # --- 2D X-Z view ---
        self.xz = pg.PlotWidget(title="X-Z (live)")
        self.xz.invertY(True)
        self.xz.setAspectLocked(True)
        self.xz.showGrid(x=True, y=True, alpha=0.25)
        self.xz.setLabel("bottom", "X", "mm")
        self.xz.setLabel("left", "Z depth", "mm")
        self.rays2d = pg.PlotDataItem(pen=pg.mkPen((29, 78, 216, 110), width=1), connect="pairs")
        self.focus2d = pg.ScatterPlotItem(size=14, symbol="x", pen=pg.mkPen("k", width=2.5))
        self.central2d = pg.PlotDataItem(pen=pg.mkPen("k", width=2, style=QtCore.Qt.DashLine))

        # --- delay chart and table ---
        self.bars = pg.PlotWidget(title="Delays (µs), law")
        self.bars.setLabel("bottom", "Element")
        self.bar_item = pg.BarGraphItem(x=[], height=[], width=0.8, brush=(56, 189, 248))
        self.bars.addItem(self.bar_item)
        self.table = QtWidgets.QTableWidget(len(self.sweep), 5)
        self.table.setHorizontalHeaderLabels(["Angle °", "Fx mm", "Fz mm", "Min µs", "Max µs"])
        for r, (a, _, f, law) in enumerate(self.sweep):
            d = law["delays"] * 1e6
            for c, v in enumerate([a, f[0] * 1e3, f[2] * 1e3, np.nanmin(d), np.nanmax(d)]):
                item = QtWidgets.QTableWidgetItem()
                item.setData(QtCore.Qt.DisplayRole, round(float(v), 2))   # numeric sort
                item.setData(QtCore.Qt.UserRole, r)                       # law index survives sorting
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, QtCore.Qt.AscendingOrder)
        self.table.itemSelectionChanged.connect(self._table_selected)

        # --- law slider ---
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, len(self.sweep) - 1)
        self.slider.valueChanged.connect(self.show_law)
        self.readout = QtWidgets.QLabel()
        nav = QtWidgets.QHBoxLayout()
        nav.addWidget(QtWidgets.QLabel("Law"))
        nav.addWidget(self.slider, 1)
        nav.addWidget(self.readout)

        top = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        top.addWidget(self.vtk.interactor)
        top.addWidget(self.xz)
        top.setSizes([800, 600])
        bottom = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        bottom.addWidget(self.bars)
        bottom.addWidget(self.table)
        bottom.setSizes([800, 600])
        main = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        main.addWidget(top)
        main.addWidget(bottom)
        main.setSizes([640, 300])
        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(central)
        lay.addWidget(main, 1)
        lay.addLayout(nav)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Prototype: input panels are layout only; "
                                     "slider, table, 2D, 3D and delays are live and linked.")

        self._static_2d()
        self.ray_actor = None
        self.show_law(len(self.sweep) // 2)
        z_down_camera(self.vtk, (60, 0, 0), 230, -35, 30)

    def _table_selected(self):
        item = self.table.currentItem()
        if item is not None:
            self.slider.setValue(int(item.data(QtCore.Qt.UserRole)))

    def _static_2d(self):
        prims = build_scene(self.solver, self.sweep, 0, self.T, self.outline, self.weld)
        for p in prims:
            xz = p.coords[:, [0, 2]]
            if p.kind in ("prism", "polygon"):
                n = p.meta.get("n_quads", 1)
                chunks = np.split(xz, n) if p.kind == "polygon" else [xz]
                for ch in chunks:
                    item = QtWidgets.QGraphicsPolygonItem(QtGui.QPolygonF([QtCore.QPointF(*v) for v in ch]))
                    item.setBrush(pg.mkBrush(QCOL[p.role]))
                    item.setPen(QtGui.QPen(QtCore.Qt.NoPen) if p.kind == "polygon"
                                else pg.mkPen(QCOL[p.role][:3]))
                    self.xz.addItem(item)
            elif p.kind == "box":
                (x0, _, z0), (x1, _, z1) = p.coords
                self.xz.addItem(pg.PlotDataItem([x0, x1, x1, x0, x0], [z0, z0, z1, z1, z0],
                                                pen=pg.mkPen("#475569")))
            elif p.role in ("element-active", "element-inactive"):
                self.xz.addItem(pg.ScatterPlotItem(
                    xz[:, 0], xz[:, 1], size=5, symbol="s",
                    brush=pg.mkBrush("#dc2626") if p.role == "element-active" else None,
                    pen=pg.mkPen("#94a3b8") if p.role == "element-inactive" else None))
            elif p.role == "focus-sweep":
                cmap = pg.colormap.get("viridis")
                cols = cmap.map(p.meta["law"] / max(1, len(xz) - 1), mode="qcolor")
                self.xz.addItem(pg.ScatterPlotItem(xz[:, 0], xz[:, 1], size=6, brush=cols, pen=None))
        for item in (self.rays2d, self.central2d, self.focus2d):
            self.xz.addItem(item)
        self.xz.setRange(xRange=(-5, 125), yRange=(-48, self.T * 1e3 + 5), padding=0)

    def show_law(self, i):
        t0 = time.perf_counter()
        prims = build_scene(self.solver, self.sweep, i, self.T, self.outline, self.weld)
        by = {p.role: p for p in prims}
        seg = by["ray"].coords[:, [0, 2]]
        self.rays2d.setData(seg[:, 0], seg[:, 1])
        self.central2d.setData(*by["central-ray"].coords[:, [0, 2]].T)
        self.focus2d.setData(*by["focus"].coords[:, [0, 2]].T)
        d = self.sweep[i][3]["delays"] * 1e6
        ok = np.isfinite(d)
        self.bar_item.setOpts(x=np.arange(1, len(d) + 1)[ok], height=d[ok])
        self.bars.setTitle(f"Delays (µs), law {i + 1}")
        # 3D: the static scene once, then only the law's rays and focus
        if self.ray_actor is None:
            add_scene(self.vtk, prims)
            self.ray_actor = True
        else:
            import pyvista as pv
            for name in ("rays", "focus"):
                self.vtk.remove_actor(name)
            self.vtk.add_mesh(pv.line_segments_from_points(by["ray"].coords), color="#1d4ed8",
                              opacity=0.5, name="rays")
            self.vtk.add_points(by["focus"].coords, color="black", point_size=16,
                                render_points_as_spheres=True, name="focus")
        a, _, f, _ = self.sweep[i]
        ms = (time.perf_counter() - t0) * 1e3
        self.readout.setText(f"{i + 1}/{len(self.sweep)}  {a:.1f}° SW  F = ({f[0]*1e3:.1f}, "
                             f"{f[2]*1e3:.1f}) mm   redraw {ms:.0f} ms")
        if self.slider.value() != i:
            self.slider.blockSignals(True)
            self.slider.setValue(i)
            self.slider.blockSignals(False)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    app = QtWidgets.QApplication(sys.argv)
    w = Mock(args[0] if args else None)
    w.show()
    if "--screenshot" in sys.argv:
        def snap():
            app.processEvents()
            w.vtk.render()
            app.processEvents()
            img = w.grab()
            # VTK's OpenGL widget can grab black: paint the plotter's own image over it.
            shot = w.vtk.screenshot(return_img=True)
            h, wd = shot.shape[:2]
            qimg = QtGui.QImage(np.ascontiguousarray(shot).data, wd, h, 3 * wd,
                                QtGui.QImage.Format_RGB888)
            painter = QtGui.QPainter(img)
            pos = w.vtk.interactor.mapTo(w, QtCore.QPoint(0, 0))
            painter.drawImage(QtCore.QRect(pos, w.vtk.interactor.size()), qimg)
            painter.end()
            os.makedirs(OUT, exist_ok=True)
            img.save(os.path.join(OUT, "proto_qt_mock.png"))
            # Timing of live redraws across the sweep
            t = []
            for k in range(len(w.sweep)):
                t0 = time.perf_counter()
                w.show_law(k)
                app.processEvents()
                t.append(time.perf_counter() - t0)
            print(f"redraw per law: median {np.median(t)*1e3:.0f} ms, max {np.max(t)*1e3:.0f} ms")
            t0 = time.perf_counter()
            for _ in range(20):
                w.solver.calculate_law(*w.sweep[5][2], wave_type="shear")
            print(f"one law (32 elements) solve: {(time.perf_counter()-t0)/20*1e3:.1f} ms")
            app.quit()
        QtCore.QTimer.singleShot(1500, snap)
    app.exec()


if __name__ == "__main__":
    main()
