"""
The PyVista 3D view (plan step 3): renderer off-screen for every probe type, element footprints,
camera conventions, and picking in the Qt tab for both numbering conventions on a dual matrix.
"""
import os
import sys
import unittest

import numpy as np

HEADLESS = sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
try:
    import pyvista as pv
    HAVE_PV = not HEADLESS
except ImportError:
    HAVE_PV = False

from session import build_solver, calculate
from scene_model import build_scene, element_faces_mm, element_size, user_element_numbers

SV = {"focus_mode": "Constant Depth", "wave_type": "Longitudinal", "param_val": 20, "start_angle": 35,
      "end_angle": 55, "step_angle": 10, "start_skew": -10, "end_skew": 10, "step_skew": 10,
      "y_focus_mode": "Derived from Skew", "target_y_mm": 0, "y_start_mm": 0, "y_end_mm": 0, "y_step_mm": 1}
MAT = {"vel_long_ms": 5920, "vel_shear_ms": 3240}
SETUPS = {
    "linear sub-aperture": ({"probe_type": "Linear", "num_elements": 32, "pitch_mm": 0.6, "freq_mhz": 5},
                            {"angle_deg": 36, "height_mm": 10, "velocity_ms": 2330, "offset_mm": 0},
                            {"start_element": 9, "num_active_elements": 16, "element_order": "column-first"}),
    "matrix row-first": ({"probe_type": "Matrix", "num_elements": 8, "pitch_mm": 1, "num_elements_y": 4,
                          "pitch_y_mm": 1.2, "freq_mhz": 5},
                         {"angle_deg": 20, "height_mm": 8, "velocity_ms": 2330, "offset_mm": 0},
                         {"start_element": 3, "num_active_elements": 20, "element_order": "row-first"}),
    "dual linear roof": ({"probe_type": "Dual Linear", "num_elements": 16, "pitch_mm": 0.5, "freq_mhz": 5},
                         {"angle_deg": 15, "height_mm": 6, "velocity_ms": 2330, "offset_mm": 0,
                          "array_sep_mm": 8, "roof_angle_deg": 3},
                         {"start_element": 5, "num_active_elements": 20, "element_order": "column-first"}),
    "dual matrix contact": ({"probe_type": "Dual Matrix", "num_elements": 4, "pitch_mm": 1, "num_elements_y": 2,
                             "pitch_y_mm": 1, "freq_mhz": 5},
                            {"angle_deg": 0, "height_mm": 0, "velocity_ms": 2330, "offset_mm": 0,
                             "array_sep_mm": 10, "roof_angle_deg": 0},
                            {"start_element": 2, "num_active_elements": 12, "element_order": "column-first"}),
}


def calc_for(pv_, wv, sav):
    s = build_solver(pv_, wv, MAT, sav)
    return s, calculate(s, SV, pv_["probe_type"])


def scene_for(s, c, law=1, size=(None, None)):
    get = lambda i: (c.results[i]["interface_points"] * 1e3, np.asarray(c.focal_points[i]) * 1e3)
    return build_scene(s, get, [law], current=law, max_rays=48,
                       sweep_focal_mm=np.asarray(c.focal_points) * 1e3, element_size_m=size)


class TestElementFaces(unittest.TestCase):
    def test_faces_centred_on_elements_in_the_probe_face(self):
        for name, (pv_, wv, sav) in SETUPS.items():
            with self.subTest(name):
                s = build_solver(pv_, wv, MAT, sav)
                w, l, _ = element_size(s.probe)
                faces = element_faces_mm(s, w, l).reshape(-1, 4, 3)
                centres = s.wedge.get_transformed_elements(s.probe) * 1e3
                np.testing.assert_allclose(faces.mean(axis=1), centres, atol=1e-9)
                e1 = faces[:, 1] - faces[:, 0]
                e2 = faces[:, 3] - faces[:, 0]
                np.testing.assert_allclose(np.linalg.norm(e1, axis=1), w * 1e3, rtol=1e-12)
                np.testing.assert_allclose(np.linalg.norm(e2, axis=1), l * 1e3, rtol=1e-12)
                np.testing.assert_allclose(np.einsum("ij,ij->i", e1, e2), 0, atol=1e-9)

    def test_size_rule(self):
        s = build_solver(*SETUPS["linear sub-aperture"][:2], MAT, SETUPS["linear sub-aperture"][2])
        self.assertEqual(element_size(s.probe, 0.00055, 0.012), (0.00055, 0.012, False))
        self.assertEqual(element_size(s.probe)[2], True)
        m = build_solver(*SETUPS["matrix row-first"][:2], MAT, SETUPS["matrix row-first"][2])
        self.assertTrue(element_size(m.probe, 0.0009, 0.012)[2])     # matrix passive size never given


@unittest.skipUnless(HAVE_PV, "pyvista not installed, or no display")
class TestRenderer(unittest.TestCase):
    def test_every_probe_type_renders(self):
        from scene_vtk import add_law, add_setup, render_scene
        for name, (pv_, wv, sav) in SETUPS.items():
            for section in (False, True):
                with self.subTest(name, section=section):
                    s, c = calc_for(pv_, wv, sav)
                    scene = scene_for(s, c)
                    img = render_scene(scene, 30.0, "Iso", window_size=(400, 300), section=section)
                    self.assertEqual(img.shape, (300, 400, 3))
                    self.assertGreater(img.std(), 5)        # not blank
                    pl = pv.Plotter(off_screen=True, window_size=(200, 150))
                    add_setup(pl, scene, 30.0, section=section)
                    add_law(pl, scene)
                    n = len(pl.renderer.actors)
                    add_law(pl, scene_for(s, c, law=0))     # the next law replaces, never adds
                    self.assertEqual(len(pl.renderer.actors), n)
                    self.assertIn("law:focus", pl.renderer.actors)
                    pl.close()

    def test_camera_presets_keep_depth_down(self):
        from scene_vtk import add_setup, set_camera
        s, c = calc_for(*SETUPS["matrix row-first"])
        pl = pv.Plotter(off_screen=True, window_size=(200, 150))
        lo, hi = add_setup(pl, scene_for(s, c))
        for view, look, up in (("X-Z", (0, -1, 0), (0, 0, -1)), ("Y-Z", (1, 0, 0), (0, 0, -1)),
                               ("Top", (0, 0, 1), (0, -1, 0))):
            set_camera(pl, view, lo, hi)
            d = np.subtract(pl.camera.focal_point, pl.camera.position)
            np.testing.assert_allclose(d / np.linalg.norm(d), look, atol=2e-3)
            np.testing.assert_allclose(pl.camera.up, up, atol=1e-9)
            # +X (X-Z, Top) or +Y (Y-Z) runs to the right: right = look x up
            right = np.cross(look, up)
            self.assertEqual(tuple(right), {"X-Z": (1, 0, 0), "Y-Z": (0, 1, 0), "Top": (1, 0, 0)}[view])
            self.assertTrue(pl.camera.parallel_projection)
        set_camera(pl, "Iso", lo, hi)
        self.assertFalse(pl.camera.parallel_projection)
        pl.close()


@unittest.skipUnless(HAVE_PV, "pyvista not installed, or no display")
class TestPicking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_API", "pyside6")
        from qtpy import QtWidgets
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_dual_matrix_numbering(self):
        """Picking reports the element's number in the chosen convention (plan step 3)."""
        from qt_view3d import Scene3DTab
        pv_ = {"probe_type": "Dual Matrix", "num_elements": 4, "pitch_mm": 1.0, "num_elements_y": 3,
               "pitch_y_mm": 1.5, "freq_mhz": 5}
        wv = {"angle_deg": 20, "height_mm": 8, "velocity_ms": 2330, "offset_mm": 0, "array_sep_mm": 12,
              "roof_angle_deg": 3}
        for order in ("column-first", "row-first"):
            with self.subTest(order):
                s, c = calc_for(pv_, wv, {"start_element": 3, "num_active_elements": 18, "element_order": order})
                tab = Scene3DTab()
                tab.update_plot(s, c.focal_points, c.wave_type, results=c.results, is_matrix=True,
                                component_thickness_mm=30)
                centres = s.wedge.get_transformed_elements(s.probe) * 1e3
                numbers = user_element_numbers(s.probe)
                act = set(s.probe.get_active_element_indices())
                for idx, p in enumerate(centres):
                    tab._clicked(p + np.array([0.2, 0.1, 0.0]))     # a click near, not on, the centre
                    info = tab.element_info(tab.picked)
                    self.assertEqual(tab.picked, idx)
                    self.assertEqual(info["number"], numbers[idx])
                    self.assertEqual(info["array"], "Tx" if idx < 12 else "Rx")
                    self.assertEqual(info["active"], idx in act)
                    # The grid position matches the number: row-first runs along X first.
                    n0 = (numbers[idx] - 1) % 12
                    want = (n0 % 4 + 1, n0 // 4 + 1) if order == "row-first" else (n0 // 3 + 1, n0 % 3 + 1)
                    self.assertEqual((info["x_index"], info["y_index"]), want)
                    if info["active"]:
                        self.assertEqual(info["delay_us"], c.results[tab.current_idx]["delays_us"][idx])
                tab._clicked(centres[0] + np.array([0.0, 0.0, -50.0]))   # far from every element
                self.assertEqual(tab.picked, len(centres) - 1)           # unchanged
                self.assertIn("pick:element", tab.plotter.renderer.actors)
                tab.plotter.close()
                tab.deleteLater()


if __name__ == "__main__":
    unittest.main()
