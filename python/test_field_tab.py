"""The Beam Field tab (plan step 6) in the Qt window, off-screen: invariants of what it shows."""
import unittest

import numpy as np

from beam_field import field_region, section_grid
from test_qt_gui import HAVE_QT, QtCase


class TestRegion(unittest.TestCase):
    def test_the_section_holds_the_focus_whichever_way_the_beam_steers(self):
        """Review of PR #30: the lower X bound ignored the focus."""
        ip = np.array([[0.000, 0, 0], [0.005, 0, 0]])
        for fx in (-0.030, 0.002, 0.040):
            (lo, hi), (zl, zh) = field_region({"interface_points": ip, "fx": fx, "fz": 0.03}, 0.0, [0, 1])
            self.assertLessEqual(lo, min(fx, 0.0) - 0.02 + 1e-12)
            self.assertGreaterEqual(hi, max(fx, 0.005) + 0.02 - 1e-12)
            self.assertEqual(zl, 0.0)
            self.assertAlmostEqual(zh, 0.039)


class TestGrid(unittest.TestCase):
    def test_the_grid_is_coarsened_to_the_point_limit(self):
        (x, z), step = section_grid((0.0, 0.0), (0.2, 0.1), 1e-4, 5000)
        self.assertLessEqual(x.size * z.size, 5000)
        self.assertGreater(step, 1e-4)
        self.assertAlmostEqual(x[1] - x[0], step)
        (x, z), step = section_grid((0.0, 0.0), (0.01, 0.01), 1e-3, 5000)
        self.assertEqual(step, 1e-3)
        self.assertEqual((x.size, z.size), (11, 11))

    def test_samples_stay_inside_thin_parts(self):
        """Review of PR #30: a coarse grid put samples below the backwall."""
        for th, step in ((0.005, 0.005), (0.003, 0.005), (0.005, 0.0012)):
            z0 = min(step, th / 2)
            (x, z), _ = section_grid((0.0, z0), (0.05, th), step, 40000)
            self.assertGreaterEqual(z.size, 2)
            self.assertTrue(np.all((z > 0) & (z <= th + 1e-15)), (th, step, z))
            self.assertEqual(len(set(np.round(z, 12))), z.size)
        with self.assertRaises(ValueError):
            section_grid((0.0, 0.01), (0.05, 0.01), 0.001, 1000)


@unittest.skipUnless(HAVE_QT, "PySide6/qtpy/pyvistaqt not installed, or no display")
class TestFieldTab(QtCase):
    def setup_linear(self, focus_mm=20.0):
        w = self.win
        w.probe_panel.set_values({"probe_type": "Linear", "num_elements": 32, "pitch_mm": 0.6, "freq_mhz": 5})
        w.mat_panel.set_values({"thickness_mm": 30})
        w.scan_panel.set_values({"focus_mode": "Constant Depth", "param_val": focus_mm, "wave_type": "Shear",
                                 "start_angle": 45, "end_angle": 60, "step_angle": 15})
        w.field_tab.set_values({"element_width_mm": 0.5, "grid_mm": 1.0, "cycles": 2})
        w.run_calculation()
        self.assertEqual(self.errors(), [])
        self.field3d = []
        w.field_tab.field_changed.connect(self.field3d.append)

    def test_a_focused_law_is_brightest_near_its_focus_and_reaches_the_3d_view(self):
        self.setup_linear()
        ft = self.win.field_tab
        ft.compute(sync=True)
        self.assertTrue(ft.job["fresh"], ft.status.text())
        s = ft.job["sections"][0]
        self.assertEqual(s["db"].shape, (s["z"].size, s["h"].size))
        self.assertAlmostEqual(float(np.nanmax(s["db"])), 0.0, places=9)
        self.assertGreaterEqual(float(np.nanmin(s["db"])), -30.0)
        r = self.win.plot_tab.current_result()
        iz, ix = np.unravel_index(np.nanargmax(s["db"]), s["db"].shape)
        # a 32-element shear focus: the peak lies on the beam near the focus (focal shift allowed)
        self.assertLess(abs(s["h"][ix] - r["fx"]), 0.008)
        self.assertLess(abs(s["z"][iz] - r["fz"]), 0.008)
        self.assertIsNotNone(self.field3d[-1])
        self.assertIs(self.win.scene3d_tab.field_slices, self.field3d[-1])
        self.assertIsNotNone(ft.job["metrics"])
        self.assertAlmostEqual(ft.job["metrics"].angle_deg, r["angle"], delta=3.0)

    def test_a_new_law_makes_the_field_stale_and_takes_it_out_of_3d(self):
        self.setup_linear()
        ft = self.win.field_tab
        ft.compute(sync=True)
        self.win.plot_tab.step_law(1)
        self.assertFalse(ft.job["fresh"])
        self.assertIn("stale", ft.status.text())
        self.assertIsNone(self.field3d[-1])
        self.assertIsNone(self.win.scene3d_tab.field_slices)
        ft.compute(sync=True)
        self.assertTrue(ft.job["fresh"])
        ft.set_values({"cycles": 4})                     # an input change also makes it stale
        self.assertFalse(ft.job["fresh"])

    def test_3d_sections_are_symmetric_about_a_linear_array(self):
        self.setup_linear()
        ft = self.win.field_tab
        ft.set_values({"model": "3D", "pulsed": False, "elevation_mm": 6, "grid_mm": 1.0})
        ft.compute(sync=True)
        self.assertTrue(ft.job["fresh"], ft.status.text())
        names = [s["name"] for s in ft.job["sections"]]
        self.assertEqual(names, ["X-Z", "Y-Z"])
        yz = ft.job["sections"][1]
        np.testing.assert_allclose(yz["h"], -yz["h"][::-1], atol=1e-12)     # Y grid about Y = 0
        np.testing.assert_allclose(yz["db"], yz["db"][:, ::-1], atol=1e-6)
        self.assertEqual(len(self.field3d[-1]), 2)

    def test_a_matrix_probe_has_no_2d_section(self):
        w = self.win
        w.probe_panel.set_values({"probe_type": "Matrix", "num_elements": 8, "num_elements_y": 4,
                                  "pitch_mm": 1, "pitch_y_mm": 1})
        w.scan_panel.set_values({"focus_mode": "Constant Depth", "param_val": 20, "start_angle": 40,
                                 "end_angle": 50, "step_angle": 10, "start_skew": 0, "end_skew": 0})
        w.run_calculation()
        w.field_tab.set_values({"model": "2D"})
        w.field_tab.compute(sync=True)
        self.assertIn("No field", w.field_tab.status.text())
        self.assertIsNone(w.field_tab.job)

    def test_inputs_travel_with_the_configuration(self):
        ft = self.win.field_tab
        vals = {"model": "3D", "pulsed": False, "cycles": 4.5, "grid_mm": 0.8, "element_width_mm": 0.55,
                "elevation_mm": 12.0, "wedge_shear_ms": 1157.0, "wedge_density": 1049.0,
                "component_density": 7900.0}
        ft.set_values(vals)
        config = self.win.config_dict()
        self.assertEqual(config["beam_field"], vals)
        ft.set_values({"model": "2D", "cycles": 3})
        self.win.apply_config(config)
        self.assertEqual(ft.get_values(), vals)
        ft.set_values(ft.DEFAULTS)                      # defaults: no key, as the Tk window saves
        self.assertNotIn("beam_field", self.win.config_dict())
        ft.set_values(vals)
        self.win.apply_config({})                       # a file without the key: defaults
        self.assertTrue(ft.is_default())

    def test_negative_steering_maps_its_focus(self):
        """Review of PR #30: a beam steered to -X kept its focus outside the map."""
        w = self.win
        w.probe_panel.set_values({"probe_type": "Linear", "num_elements": 8, "pitch_mm": 0.6, "freq_mhz": 5})
        w.wedge_panel.set_values({"angle_deg": 0, "height_mm": 10})
        w.scan_panel.set_values({"focus_mode": "Constant Depth", "param_val": 30, "wave_type": "Longitudinal",
                                 "start_angle": -40, "end_angle": -40, "step_angle": 5})
        w.run_calculation()
        self.assertEqual(self.errors(), [])
        w.field_tab.set_values({"element_width_mm": 0.5, "grid_mm": 1.0})
        w.field_tab.compute(sync=True)
        s = w.field_tab.job["sections"][0]
        r = w.plot_tab.current_result()
        self.assertLess(r["fx"], 0)
        self.assertLessEqual(s["h"][0], r["fx"] - 0.019)
        # the focus lies inside the mapped beam (a small aperture: the peak itself sits nearer the probe)
        ix = int(np.argmin(np.abs(s["h"] - r["fx"])))
        iz = int(np.argmin(np.abs(s["z"] - r["fz"])))
        self.assertGreater(s["db"][iz, ix], -12.0)
        self.assertGreater(s["db"][iz, ix], s["db"][iz, int(np.argmin(np.abs(s["h"] + r["fx"])))] + 10)

    def test_setup_edits_make_the_field_stale_until_the_laws_are_recalculated(self):
        """Review of PR #30: editing the setup left the field fresh and in 3D."""
        edits = [lambda w: w.mat_panel.set_values({"thickness_mm": 50}),
                 lambda w: w.mat_panel.set_values({"vel_shear_ms": 3100}),
                 lambda w: w.probe_panel.set_values({"pitch_mm": 0.7}),
                 lambda w: w.wedge_panel.set_values({"height_mm": 7}),
                 lambda w: w.sub_aperture_panel.set_values({"start_element": 3}),
                 lambda w: w.scan_panel.set_values({"wave_type": "Longitudinal"}),
                 lambda w: w.scan_panel.set_values({"param_val": 24})]
        self.setup_linear()
        ft = self.win.field_tab
        for k, change in enumerate(edits):
            with self.subTest(k):
                self.win.run_calculation()
                ft.compute(sync=True)
                self.assertTrue(ft.job["fresh"], ft.status.text())
                change(self.win)
                self.assertFalse(ft.job["fresh"])
                self.assertIsNone(self.field3d[-1])
                self.assertIsNone(self.win.scene3d_tab.field_slices)
                old = ft.job
                ft.compute(sync=True)                     # refused against the old solver
                self.assertIs(ft.job, old)
                self.assertIn("Calculate Laws", ft.status.text())

    def test_setup_edits_while_computing_leave_the_result_stale(self):
        """Review of PR #30: a field finishing after a setup edit was marked fresh."""
        from qt_field import run_job
        self.setup_linear()
        ft = self.win.field_tab
        ft.compute(sync=True)                             # a fresh field in 3D first
        self.assertIsNotNone(self.field3d[-1])
        job = run_job(ft.make_job())                      # a computation that started ...
        self.win.wedge_panel.set_values({"height_mm": 7})  # ... then the setup changed ...
        ft._done(job)                                     # ... and it finished
        self.assertFalse(ft.job["fresh"])
        self.assertIn("Stale", ft.status.text())
        self.assertIsNone(self.field3d[-1])
        self.assertIsNone(self.win.scene3d_tab.field_slices)

    def test_a_thin_plate_with_a_coarse_grid_maps_only_inside_it(self):
        self.setup_linear()
        self.win.mat_panel.set_values({"thickness_mm": 5})
        self.win.run_calculation()
        ft = self.win.field_tab
        ft.set_values({"grid_mm": 5})
        ft.compute(sync=True)
        z = ft.job["sections"][0]["z"]
        self.assertGreaterEqual(z.size, 2)
        self.assertTrue(np.all((z > 0) & (z <= 0.005 + 1e-15)), z)

    def test_the_hidden_3d_tab_shows_and_drops_the_field_when_shown(self):
        """Review of PR #30: field slices sent while the 3D tab was hidden never reached its scene."""
        w = self.win
        self.setup_linear()
        w.show()
        w.tabs.setCurrentWidget(w.scene3d_tab)
        self.qapp.processEvents()
        actors = lambda: [k for k in w.scene3d_tab.plotter.renderer.actors if str(k).startswith("beam-field")]
        self.assertEqual(actors(), [])
        w.tabs.setCurrentWidget(w.field_tab)
        self.qapp.processEvents()
        w.field_tab.compute(sync=True)
        self.qapp.processEvents()
        w.tabs.setCurrentWidget(w.scene3d_tab)
        self.qapp.processEvents()
        self.assertEqual(actors(), ["beam-field-0"])
        w.tabs.setCurrentWidget(w.field_tab)
        self.qapp.processEvents()
        w.field_tab.set_values({"cycles": 5})            # stale: taken out of 3D
        self.qapp.processEvents()
        w.tabs.setCurrentWidget(w.scene3d_tab)
        self.qapp.processEvents()
        self.assertEqual(actors(), [])

    def test_an_unchanged_context_keeps_a_running_field_fresh(self):
        """Review of PR #30: re-selecting the same law during a computation made it stale."""
        from qt_field import run_job
        self.setup_linear()
        ft = self.win.field_tab
        job = run_job(ft.make_job())
        self.win.update_field_context()                   # the same law again
        self.win.update_field_context()
        ft._done(job)
        self.assertTrue(ft.job["fresh"], ft.status.text())
        self.assertIsNotNone(self.field3d[-1])

    def test_closing_during_a_computation_exits_cleanly(self):
        """Review of PR #30: closing the window while the field worker ran left it running."""
        import os
        import subprocess
        import sys
        import textwrap
        script = textwrap.dedent("""
            import os
            os.environ.setdefault('QT_API', 'pyside6')
            from qtpy import QtCore, QtWidgets
            import qt_app
            app = QtWidgets.QApplication([])
            w = qt_app.MainWindow()
            w.info = w.warn = w.error = lambda *a: None
            w.probe_panel.set_values({'probe_type': 'Linear', 'num_elements': 64, 'pitch_mm': 0.6})
            w.mat_panel.set_values({'thickness_mm': 60})
            w.scan_panel.set_values({'focus_mode': 'Constant Depth', 'param_val': 40, 'wave_type': 'Shear',
                                     'start_angle': 45, 'end_angle': 45, 'step_angle': 5})
            w.field_tab.set_values({'element_width_mm': 0.5, 'grid_mm': 0.1})
            w.show()
            w.run_calculation()
            w.field_tab.compute()
            assert w.field_tab.worker.isRunning()
            QtCore.QTimer.singleShot(300, w.close)
            QtCore.QTimer.singleShot(400, app.quit)
            rc = app.exec()
            assert not w.field_tab.worker.isRunning(), 'worker still running'
            print('CLEAN', rc)
            """)
        here = os.path.dirname(os.path.abspath(__file__))
        r = subprocess.run([sys.executable, "-c", script], cwd=here, capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        self.assertIn("CLEAN 0", r.stdout)

    def test_no_laws_no_field(self):
        self.win.field_tab.compute(sync=True)
        self.assertIn("calculate laws first", self.win.field_tab.status.text())


if __name__ == "__main__":
    unittest.main()
