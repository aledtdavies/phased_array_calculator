"""GUI regressions driven without user input (skipped where Tk cannot open a window)."""
import unittest

from tkinter import TclError, messagebox


class GuiCase(unittest.TestCase):
    def setUp(self):
        import app as appmod
        self._saved = (messagebox.showinfo, messagebox.showwarning, messagebox.showerror)
        messagebox.showinfo = messagebox.showwarning = lambda *a, **k: None

        def fail(*a, **k):
            raise AssertionError(f"error dialog: {a}")
        messagebox.showerror = fail
        try:
            self.app = appmod.App()
        except TclError as e:
            self.skipTest(f"Tk unavailable: {e}")
        self.app.withdraw()

    def tearDown(self):
        messagebox.showinfo, messagebox.showwarning, messagebox.showerror = self._saved
        if hasattr(self, "app"):
            self.app.destroy()

    def tabs(self):
        return (self.app.plot_tab, self.app.hist_tab, self.app.scene3d_tab)


class TestRecalculation(GuiCase):
    def test_shorter_sparse_sweep_after_a_late_law(self):
        a = self.app
        a.probe_panel.set_values({"probe_type": "Matrix", "num_elements": 8, "num_elements_y": 4,
                                  "pitch_mm": 1.0, "pitch_y_mm": 1.0})
        a.scan_panel.set_values({"start_angle": 40, "end_angle": 70, "step_angle": 1,
                                 "focus_mode": "Constant Depth", "param_val": 30})
        a.run_calculation()
        late = len(a.last_results) - 1
        for tab in self.tabs():
            tab.show_law(late)
        # Constant Sound Path Y sweep with positive Y targets: the effective skew
        # depends on the angle, so the (minimum angle, minimum skew) pair is absent.
        a.scan_panel.set_values({"start_angle": 40, "end_angle": 50, "step_angle": 10,
                                 "focus_mode": "Constant Sound Path", "param_val": 40,
                                 "y_focus_mode": "Y Sweep", "y_start_mm": 2, "y_end_mm": 6,
                                 "y_step_mm": 4})
        a.run_calculation()
        n = len(a.last_results)
        self.assertGreater(n, 0)
        keys = {(r['angle'], r['skew']) for r in a.last_results}
        angles = sorted({k[0] for k in keys})
        skews = sorted({k[1] for k in keys})
        self.assertNotIn((angles[0], skews[0]), keys)
        for tab in self.tabs():
            self.assertTrue(0 <= tab.current_idx < n, (type(tab).__name__, tab.current_idx, n))
            tab.refresh_plot()
            tab.figure.canvas.draw()
            tab.slider_skew.set(0)
            tab.on_slider_change()
            self.assertTrue(0 <= tab.current_idx < n)


class TestCatalogueRoundTrip(GuiCase):
    def config_with_reference(self, match=True):
        a = self.app
        a.probe_panel.set_values({"probe_type": "Linear", "num_elements": 64, "pitch_mm": 0.75,
                                  "freq_mhz": 2.25})
        cfg = a.config_dict()
        cfg["catalog"] = {"probe": {"kind": "probe", "id": "l64", "values_match": match}}
        return cfg

    def test_edit_after_reload_clears_values_match(self):
        a = self.app
        a.apply_config(self.config_with_reference())
        self.assertTrue(a.config_dict()["catalog"]["probe"]["values_match"])   # unchanged round trip
        a.probe_panel.set_values({"pitch_mm": 0.6})
        self.assertFalse(a.config_dict()["catalog"]["probe"]["values_match"])
        a.probe_panel.set_values({"pitch_mm": 0.75})
        self.assertTrue(a.config_dict()["catalog"]["probe"]["values_match"])

    def test_false_stays_false(self):
        a = self.app
        a.apply_config(self.config_with_reference(match=False))
        self.assertFalse(a.config_dict()["catalog"]["probe"]["values_match"])


if __name__ == "__main__":
    unittest.main()
