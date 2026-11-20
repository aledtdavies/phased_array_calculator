"""The Beam Field tab (plan step 6) in the Qt window, off-screen: invariants of what it shows."""
import unittest

import numpy as np

from test_qt_gui import HAVE_QT, QtCase

from qt_field import section_grid


class TestGrid(unittest.TestCase):
    def test_the_grid_is_coarsened_to_the_point_limit(self):
        (x, z), step = section_grid((0.0, 0.0), (0.2, 0.1), 1e-4, 5000)
        self.assertLessEqual(x.size * z.size, 5000)
        self.assertGreater(step, 1e-4)
        self.assertAlmostEqual(x[1] - x[0], step)
        (x, z), step = section_grid((0.0, 0.0), (0.01, 0.01), 1e-3, 5000)
        self.assertEqual(step, 1e-3)
        self.assertEqual((x.size, z.size), (11, 11))


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

    def test_no_laws_no_field(self):
        self.win.field_tab.compute(sync=True)
        self.assertIn("calculate laws first", self.win.field_tab.status.text())


if __name__ == "__main__":
    unittest.main()
