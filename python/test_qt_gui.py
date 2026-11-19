"""
The Qt window (qt_app.py), off-screen: parity with the Tk window (panel keys and defaults, data
table, configuration files both ways) and the GUI regressions of test_gui.py, ported.
Skipped where PySide6 is not installed.
"""
import json
import os
import tempfile
import unittest

import sys

# The native Qt platform: VTK (the 3D tab) needs a real OpenGL render window, which the
# 'offscreen' platform cannot give. Windows are created but never shown. Without a display
# (headless Linux) the Qt tests are skipped rather than letting Qt abort the process.
os.environ.setdefault("QT_API", "pyside6")
HEADLESS = sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
try:
    if HEADLESS:
        raise ImportError("no display")
    from qtpy import QtCore, QtWidgets
    import pyvistaqt  # noqa: F401
    HAVE_QT = True
except Exception:          # qtpy raises its own error when no binding is installed
    HAVE_QT = False

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDFE_CATALOG = os.path.normpath(os.path.join(HERE, "..", "..", "buildFE", "catalog"))

SCAN_CASES = {
    "depth linear": ({"probe_type": "Linear", "num_elements": 16, "pitch_mm": 0.6},
                     {"focus_mode": "Constant Depth", "param_val": 30, "start_angle": 40, "end_angle": 80,
                      "step_angle": 5}),
    "vertical line with refusals": ({"probe_type": "Linear"},
                                    {"focus_mode": "Vertical Line", "param_val": 40, "start_angle": -10,
                                     "end_angle": 70, "step_angle": 10}),
    "sound path shear": ({"probe_type": "Linear"},
                         {"focus_mode": "Constant Sound Path", "param_val": 35, "wave_type": "Shear",
                          "start_angle": 30, "end_angle": 80, "step_angle": 10}),
    "matrix skew": ({"probe_type": "Matrix", "num_elements": 8, "num_elements_y": 4, "pitch_mm": 1,
                     "pitch_y_mm": 1},
                    {"focus_mode": "Constant Depth", "wave_type": "Longitudinal", "param_val": 25,
                     "start_angle": 40, "end_angle": 60, "step_angle": 10, "start_skew": -10,
                     "end_skew": 10, "step_skew": 10, "y_focus_mode": "Derived from Skew"}),
    "matrix y sweep": ({}, {"focus_mode": "Constant Depth", "param_val": 25, "y_focus_mode": "Y Sweep",
                            "y_start_mm": -4, "y_end_mm": 4, "y_step_mm": 4}),
    "path y sweep out of reach": ({}, {"focus_mode": "Constant Sound Path", "param_val": 40,
                                       "y_focus_mode": "Y Sweep", "y_start_mm": 0, "y_end_mm": 30,
                                       "y_step_mm": 10, "start_angle": 30, "end_angle": 70,
                                       "step_angle": 20}),
}


@unittest.skipUnless(HAVE_QT, "PySide6/qtpy/pyvistaqt not installed, or no display")
class QtCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        import qt_app
        self.win = qt_app.MainWindow()
        self.dialogs = []
        for kind in ("info", "warn", "error"):
            setattr(self.win, kind, lambda title, text, k=kind: self.dialogs.append((k, title, text)))

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        self.qapp.processEvents()

    def errors(self):
        return [d for d in self.dialogs if d[0] == "error"]

    def tabs(self):
        return (self.win.plot_tab, self.win.hist_tab, self.win.scene3d_tab)


class TkCase(QtCase):
    """A Qt window and a Tk window side by side (skipped where Tk cannot open)."""

    def setUp(self):
        super().setUp()
        from tkinter import TclError, messagebox
        import app as tk_app
        self._saved = (messagebox.showinfo, messagebox.showwarning, messagebox.showerror)
        messagebox.showinfo = messagebox.showwarning = lambda *a, **k: None
        messagebox.showerror = lambda *a, **k: self.dialogs.append(("tk-error",) + a)
        try:
            self.tk = tk_app.App()
        except TclError as e:
            self.skipTest(f"Tk unavailable: {e}")
        self.tk.withdraw()

    def tearDown(self):
        from tkinter import messagebox
        messagebox.showinfo, messagebox.showwarning, messagebox.showerror = self._saved
        if hasattr(self, "tk"):
            self.tk.destroy()
        super().tearDown()


class TestParityWithTk(TkCase):
    def test_panel_keys_and_defaults(self):
        for name in ("probe_panel", "wedge_panel", "mat_panel", "scan_panel", "sub_aperture_panel"):
            self.assertEqual(getattr(self.win, name).get_values(), getattr(self.tk, name).get_values(), name)

    def test_same_table_for_every_scan_case(self):
        for name, (pv, sv) in SCAN_CASES.items():
            with self.subTest(name):
                for w in (self.win, self.tk):
                    if pv:
                        w.probe_panel.set_values(pv)
                    w.scan_panel.set_values(sv)
                    w.run_calculation()
                tk_rows = [[str(v) for v in self.tk.tree.item(r, "values")] for r in self.tk.tree.get_children()]
                self.assertEqual(self.win.table_rows(), tk_rows)
                self.assertGreater(len(tk_rows), 0)
        self.assertEqual(self.errors(), [])

    def test_configuration_files_both_ways(self):
        self.tk.probe_panel.set_values({"probe_type": "Dual Matrix", "num_elements": 6, "num_elements_y": 3,
                                        "pitch_mm": 0.8, "pitch_y_mm": 1.1})
        self.tk.wedge_panel.set_values({"angle_deg": 18.95, "height_mm": 8.65, "array_sep_mm": 12,
                                        "roof_angle_deg": 4})
        self.tk.scan_panel.set_values({"focus_mode": "Vertical Line", "y_focus_mode": "Fixed Y",
                                       "target_y_mm": 2.5, "param_val": 33.3})
        self.tk.sub_aperture_panel.set_values({"start_element": 4, "num_active_elements": 9,
                                               "element_order": "row-first"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "tk.json")
            with open(path, "w") as f:
                json.dump(self.tk.config_dict(), f)
            self.win.ask_open = lambda *a, **k: path
            self.win.load_config()
            self.assertEqual(self.win.config_dict(), self.tk.config_dict())
            self.win.scan_panel.set_values({"param_val": 21.5})
            self.tk.apply_config(json.loads(json.dumps(self.win.config_dict())))
            self.assertEqual(self.tk.config_dict(), self.win.config_dict())
        self.assertEqual(self.errors(), [])


class TestQtWindow(QtCase):
    def test_every_tk_feature_is_reachable(self):
        menu = [a.text() for a in self.win.menuBar().actions()[0].menu().actions() if a.text()]
        self.assertEqual(menu, ["Save Configuration", "Load Configuration", "Export Element Coordinates",
                                "Load Probe from Catalogue...", "Load Wedge from Catalogue...", "Exit"])
        self.assertEqual([self.win.tabs.tabText(i) for i in range(self.win.tabs.count())],
                         ["Ray Tracing", "Data Table", "Delays", "3D View"])
        self.assertTrue(hasattr(self.win.plot_tab, "chk_all") and hasattr(self.win.plot_tab, "play_btn"))
        self.assertEqual(sorted(self.win.scene3d_tab.view_buttons), ["Iso", "Top", "X-Z", "Y-Z"])

    def test_visibility_follows_probe_type(self):
        w = self.win
        for ptype, matrix, dual in (("Linear", False, False), ("Matrix", True, False),
                                    ("Dual Linear", False, True), ("Dual Matrix", True, True)):
            w.probe_panel.set_values({"probe_type": ptype})
            self.assertEqual(w.probe_panel.form.isRowVisible(w.probe_panel.entries["num_elements_y"]), matrix)
            self.assertEqual(w.wedge_panel.form.isRowVisible(w.wedge_panel.entries["array_sep_mm"]), dual)
            self.assertEqual(w.scan_panel.form.isRowVisible(w.scan_panel.entries["start_skew"]), matrix)
            self.assertEqual(w.sub_aperture_panel.form.isRowVisible(w.sub_aperture_panel.order), matrix)

    def test_sound_path_offers_no_fixed_y(self):
        sp = self.win.scan_panel
        sp.set_values({"focus_mode": "Constant Sound Path"})
        self.assertEqual(sp.y_focus_mode.findText("Fixed Y"), -1)
        with self.assertRaises(ValueError):
            sp.set_values({"y_focus_mode": "Fixed Y"})
        sp.set_values({"focus_mode": "Constant Depth", "y_focus_mode": "Fixed Y"})
        self.assertEqual(sp.get_values()["y_focus_mode"], "Fixed Y")

    def test_numbers_are_read_exactly_and_bad_text_is_named(self):
        w = self.win
        w.wedge_panel.set_values({"offset_mm": 10.33, "height_mm": 8.650000000000002})
        self.assertEqual(w.wedge_panel.get_values()["height_mm"], 8.650000000000002)
        w.probe_panel.entries["pitch_mm"].setText("abc")
        w.run_calculation()
        self.assertEqual(len(self.errors()), 1)
        self.assertIn("Primary Pitch (mm)", self.errors()[0][2])

    def test_table_row_selects_the_law_in_every_tab(self):
        w = self.win
        w.probe_panel.set_values({"probe_type": "Matrix", "num_elements": 8, "num_elements_y": 4,
                                  "pitch_mm": 1, "pitch_y_mm": 1})
        w.scan_panel.set_values({"focus_mode": "Constant Depth", "param_val": 25, "y_focus_mode": "Y Sweep",
                                 "y_start_mm": -4, "y_end_mm": 4, "y_step_mm": 4, "start_angle": 40,
                                 "end_angle": 50, "step_angle": 10})
        w.run_calculation()
        w.tree.selectRow(2)        # third Y target: shares its angle and skew with laws 1-2
        for tab in self.tabs():
            self.assertEqual(tab.current_idx, 2)
        w.scene3d_tab.step_law(1)                      # navigation is shared by every tab
        for tab in self.tabs():
            self.assertEqual(tab.current_idx, 3)
        w.plot_tab.toggle_play()
        for _ in range(4):
            w.plot_tab.animate()
        w.plot_tab.toggle_play()
        for tab in self.tabs():
            self.assertEqual(tab.current_idx, (3 + 4) % len(w.last_results))   # wraps
        self.assertEqual(self.errors(), [])

    def test_shorter_sparse_sweep_after_a_late_law(self):
        w = self.win
        w.probe_panel.set_values({"probe_type": "Matrix", "num_elements": 8, "num_elements_y": 4,
                                  "pitch_mm": 1, "pitch_y_mm": 1})
        w.scan_panel.set_values({"start_angle": 40, "end_angle": 70, "step_angle": 1,
                                 "focus_mode": "Constant Depth", "param_val": 30})
        w.run_calculation()
        for tab in self.tabs():
            tab.show_law(len(w.last_results) - 1)
        w.scan_panel.set_values({"start_angle": 40, "end_angle": 50, "step_angle": 10,
                                 "focus_mode": "Constant Sound Path", "param_val": 40,
                                 "y_focus_mode": "Y Sweep", "y_start_mm": 2, "y_end_mm": 6, "y_step_mm": 4})
        w.run_calculation()
        n = len(w.last_results)
        for tab in self.tabs():
            self.assertTrue(0 <= tab.current_idx < n)
            tab.slider_skew.setValue(0)
            tab.refresh_plot()
            self.assertTrue(0 <= tab.current_idx < n)

    def test_no_laws_clears_every_tab_and_play_stays_idle(self):
        w = self.win
        w.scene3d_tab.toggle_play()
        self.assertFalse(w.scene3d_tab.is_playing)
        w.run_calculation()
        self.assertTrue(w.last_results)
        w.scan_panel.set_values({"focus_mode": "Vertical Line", "param_val": -200})
        w.run_calculation()
        self.assertEqual(w.last_results, [])
        self.assertFalse(w.export_btn.isEnabled())
        for tab in self.tabs():
            self.assertEqual((tab.focal_points, tab.results, tab.solver), ([], [], None))
            tab.step_law(1)
            if hasattr(tab, "plotter"):
                self.assertEqual(list(tab.plotter.renderer.actors), [])
            elif hasattr(tab, "xz"):
                for plot in (tab.xz, tab.yz):
                    self.assertEqual(plot.setup_items, [])
                    self.assertTrue(all(len(it.getData()[0] or []) == 0 for it in plot.env_items.values()))
            else:
                self.assertEqual(tab.items, {})

    def test_exports(self):
        w = self.win
        w.run_calculation()
        with tempfile.TemporaryDirectory() as d:
            csv_path, el_path = os.path.join(d, "laws.csv"), os.path.join(d, "els.csv")
            w.ask_save = lambda *a, **k: csv_path
            w.export_csv()
            w.ask_save = lambda *a, **k: el_path
            w.export_element_coords()
            with open(csv_path) as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), len(w.last_results) + 1)
            self.assertTrue(lines[0].startswith("LawID,Angle_Deg,Skew_Deg"))
            self.assertTrue(os.path.getsize(el_path) > 0)
        self.assertEqual(self.errors(), [])

    def test_hidden_dual_fields_do_not_reach_a_single_array(self):
        """Roof and separation hide for single arrays and are not applied (as in MATLAB)."""
        w = self.win
        w.probe_panel.set_values({"probe_type": "Dual Linear"})
        w.wedge_panel.set_values({"roof_angle_deg": 3.0, "array_sep_mm": 12})
        self.assertAlmostEqual(w.get_solver().wedge.roof_angle_degrees, 3.0)
        w.probe_panel.set_values({"probe_type": "Linear"})
        s = w.get_solver()
        self.assertEqual(s.wedge.roof_angle_degrees, 0.0)
        self.assertTrue((s.wedge.get_transformed_elements(s.probe)[:, 1] == 0).all())

    def test_pick_readout_cleared_by_a_new_calculation(self):
        w = self.win
        w.run_calculation()
        w.scene3d_tab.pick_element(3)
        self.assertIn("Element 4", w.scene3d_tab.lbl_pick.text())
        w.run_calculation()
        self.assertNotIn("Element", w.scene3d_tab.lbl_pick.text())

    def test_catalogue_values_match_round_trip(self):
        w = self.win
        w.probe_panel.set_values({"probe_type": "Linear", "num_elements": 64, "pitch_mm": 0.75, "freq_mhz": 2.25})
        cfg = w.config_dict()
        cfg["catalog"] = {"probe": {"kind": "probe", "id": "l64", "values_match": True}}
        w.apply_config(cfg)
        self.assertTrue(w.config_dict()["catalog"]["probe"]["values_match"])
        w.probe_panel.set_values({"pitch_mm": 0.6})
        self.assertFalse(w.config_dict()["catalog"]["probe"]["values_match"])

    @unittest.skipUnless(os.path.isdir(BUILDFE_CATALOG), "no sibling buildFE checkout")
    def test_load_wedge_from_buildfe_catalogue(self):
        from qt_catalog_dialog import CatalogPicker
        from catalog import Catalog
        cat = Catalog(os.path.join(BUILDFE_CATALOG, "wedges.json"))
        picker = CatalogPicker(self.win, cat, "wedge")
        picker.filter.setText("N55S")
        self.assertEqual(picker.visible_ids(), ["evident-SA2-N55S"])
        self.win.pick_catalog_entry = lambda c, k: "evident-SA2-N55S"
        self.win.load_from_catalog("wedge", path=os.path.join(BUILDFE_CATALOG, "wedges.json"))
        self.assertEqual(self.win.wedge_panel.get_values()["angle_deg"], 36.0)
        self.assertEqual(self.win.config_dict()["catalog"]["wedge"]["stamp"], "ok")
        self.win.run_calculation()
        self.assertIsNotNone(self.win.plot_tab.outline_mm)
        self.assertEqual(self.errors(), [])


if __name__ == "__main__":
    unittest.main()
