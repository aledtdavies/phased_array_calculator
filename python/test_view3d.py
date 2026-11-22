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

    @staticmethod
    def click(tab, xy, drag=(0, 0)):
        """A left press and release through the VTK interactor, as a mouse click delivers it."""
        iren = tab.plotter.iren.interactor
        x, y = int(round(xy[0])), int(round(xy[1]))
        iren.SetEventInformation(x, y)
        iren.InvokeEvent("LeftButtonPressEvent")
        iren.SetEventInformation(x + drag[0], y + drag[1])
        iren.InvokeEvent("LeftButtonReleaseEvent")

    def test_dual_matrix_numbering(self):
        """
        Clicking each element on screen picks it and reports its number in the chosen
        convention (plan step 3; review of PR #26): real click events at the projected element
        centres, Iso and Top views, with highlights and rays present, and a background click.
        """
        from qt_view3d import Scene3DTab
        from scene_vtk import display_positions
        pv_ = {"probe_type": "Dual Matrix", "num_elements": 4, "pitch_mm": 1.0, "num_elements_y": 3,
               "pitch_y_mm": 1.5, "freq_mhz": 5}
        wv = {"angle_deg": 20, "height_mm": 8, "velocity_ms": 2330, "offset_mm": 0, "array_sep_mm": 12,
              "roof_angle_deg": 3}
        for order in ("column-first", "row-first"):
            s, c = calc_for(pv_, wv, {"start_element": 3, "num_active_elements": 18, "element_order": order})
            tab = Scene3DTab()
            tab.resize(900, 700)
            tab.plotter.window_size = (900, 700)     # hidden widget: give the render window a size
            tab.update_plot(s, c.focal_points, c.wave_type, results=c.results, is_matrix=True,
                            component_thickness_mm=30)
            centres = s.wedge.get_transformed_elements(s.probe) * 1e3
            numbers = user_element_numbers(s.probe)
            act = set(s.probe.get_active_element_indices())
            for view in ("Iso", "Top"):
                with self.subTest(order=order, view=view):
                    tab.set_view(view)
                    tab.plotter.render()
                    disp = display_positions(tab.plotter.renderer, centres)
                    for idx in range(len(centres)):
                        self.click(tab, disp[idx, :2] + 1.0)        # a pixel off the centre
                        self.assertEqual(tab.picked, idx, f"{order} {view}: clicked {idx}")
                        info = tab.element_info(idx)
                        self.assertEqual(info["number"], numbers[idx])
                        self.assertEqual(info["array"], "Tx" if idx < 12 else "Rx")
                        self.assertEqual(info["active"], idx in act)
                        n0 = (numbers[idx] - 1) % 12
                        want = (n0 % 4 + 1, n0 // 4 + 1) if order == "row-first" else (n0 // 3 + 1, n0 % 3 + 1)
                        self.assertEqual((info["x_index"], info["y_index"]), want)
                        self.assertIn(f"Element {numbers[idx]} ", tab.lbl_pick.text() + " ")
                        if info["active"]:
                            self.assertEqual(info["delay_us"], c.results[tab.current_idx]["delays_us"][idx])
                    self.assertIn("pick:element", tab.plotter.renderer.actors)
                    last = tab.picked
                    self.click(tab, (3, 3))                       # background corner: nothing
                    self.assertEqual(tab.picked, last)
                    self.click(tab, disp[0, :2], drag=(30, 0))    # a drag (rotation) does not pick
                    self.assertEqual(tab.picked, last)
            tab.plotter.close()
            tab.deleteLater()


    def test_recalculation_keeps_the_angle_and_frames_the_new_setup(self):
        """Review of PR #26: a moved setup stays in view; the user's viewing direction is kept."""
        from qt_view3d import Scene3DTab
        from scene_vtk import display_positions
        pv_, wv, sav = SETUPS["linear sub-aperture"]
        tab = Scene3DTab()
        tab.resize(600, 450)
        tab.plotter.window_size = (600, 450)
        s, c = calc_for(pv_, wv, sav)
        tab.update_plot(s, c.focal_points, c.wave_type, results=c.results, component_thickness_mm=20)
        tab.plotter.camera.azimuth += 25          # the user turns the view
        tab.plotter.render()
        cam = tab.plotter.camera
        before = np.subtract(cam.position, cam.focal_point)
        s2, c2 = calc_for(pv_, dict(wv, offset_mm=1000), sav)
        tab.update_plot(s2, c2.focal_points, c2.wave_type, results=c2.results, component_thickness_mm=20)
        tab.plotter.render()
        after = np.subtract(cam.position, cam.focal_point)
        np.testing.assert_allclose(after / np.linalg.norm(after), before / np.linalg.norm(before), atol=1e-9)
        disp = display_positions(tab.plotter.renderer, s2.wedge.get_transformed_elements(s2.probe) * 1e3)
        w, h = tab.plotter.render_window.GetSize()
        self.assertTrue(((disp[:, 0] >= 0) & (disp[:, 0] <= w) & (disp[:, 1] >= 0) & (disp[:, 1] <= h)).all())
        tab.plotter.close()
        tab.deleteLater()

    def test_millimetre_axes(self):
        """Review of PR #26: labelled coordinate axes in mm."""
        from qt_view3d import Scene3DTab
        pv_, wv, sav = SETUPS["matrix row-first"]
        tab = Scene3DTab()
        tab.plotter.window_size = (500, 400)
        s, c = calc_for(pv_, wv, sav)
        tab.update_plot(s, c.focal_points, c.wave_type, results=c.results, is_matrix=True)
        axes = tab.plotter.renderer.cube_axes_actor
        self.assertIsNotNone(axes)
        self.assertEqual((axes.GetXTitle(), axes.GetYTitle(), axes.GetZTitle()),
                         ("X (mm)", "Y (mm)", "Z depth (mm)"))
        tab.plotter.close()
        tab.deleteLater()

    def test_real_qt_mouse_clicks(self):
        """A mouse click through Qt (QTest) on the shown view picks the element under it."""
        from qtpy import QtCore
        from qtpy.QtTest import QTest
        from qt_view3d import Scene3DTab
        from scene_vtk import display_positions
        pv_ = {"probe_type": "Dual Matrix", "num_elements": 4, "pitch_mm": 1.0, "num_elements_y": 3,
               "pitch_y_mm": 1.5, "freq_mhz": 5}
        wv = {"angle_deg": 20, "height_mm": 8, "velocity_ms": 2330, "offset_mm": 0, "array_sep_mm": 12,
              "roof_angle_deg": 3}
        s, c = calc_for(pv_, wv, {"start_element": 3, "num_active_elements": 18, "element_order": "row-first"})
        tab = Scene3DTab()
        tab.resize(900, 700)
        tab.show()
        self.qapp.processEvents()
        tab.update_plot(s, c.focal_points, c.wave_type, results=c.results, is_matrix=True,
                        component_thickness_mm=30)
        tab.plotter.render()
        self.qapp.processEvents()
        widget = tab.plotter.interactor
        dpr = widget.devicePixelRatioF()
        height = tab.plotter.render_window.GetSize()[1]
        centres = s.wedge.get_transformed_elements(s.probe) * 1e3
        for view in ("Iso", "Top"):
            tab.set_view(view)
            self.qapp.processEvents()
            disp = display_positions(tab.plotter.renderer, centres)
            for idx in range(len(centres)):
                pos = QtCore.QPoint(int(round(disp[idx, 0] / dpr)), int(round((height - 1 - disp[idx, 1]) / dpr)))
                QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
                self.qapp.processEvents()
                self.assertEqual(tab.picked, idx, f"{view}: Qt click on element {idx}")
        tab.plotter.close()
        tab.close()
        tab.deleteLater()


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE_PV, "pyvista not installed, or no display")
class WeldRendering(unittest.TestCase):
    """Review of PR #29: every accepted weld outline renders in 3D with its full cross-section."""

    def test_templates_including_a_pinched_double_v(self):
        from scene_model import Prim, Scene, weld_prims
        from scene_vtk import add_setup
        from weld import polygon_area, template_profile
        cases = [("single-V", dict(bevel_deg=30, root_gap_mm=2, root_face_mm=1.5)),
                 ("double-V", dict(bevel_deg=30, root_gap_mm=0, root_face_mm=0)),     # two lobes at a point
                 ("double-V", dict(bevel_deg=30, root_gap_mm=2, root_face_mm=2)),
                 ("single-J", dict(bevel_deg=10, root_gap_mm=0, root_face_mm=1.5, root_radius_mm=6))]
        for kind, kw in cases:
            with self.subTest(kind=kind, **kw):
                prof = template_profile(kind, 25, 40, **kw)
                el = Prim("points", np.array([[0.0, 0.0, -10.0]]), "element",
                          {"array": "single", "active": True, "indices": np.array([0])})
                scene = Scene([el] + weld_prims(prof), contact=False)
                pl = pv.Plotter(off_screen=True, window_size=(200, 150))
                try:
                    lo, hi = add_setup(pl, scene, 25.0)
                    body = pl.actors["setup:weld"].mapper.dataset
                    self.assertGreater(body.n_cells, 0)
                    # the body's end cap (cells lying in the plane Y = lo) is the outline's area
                    tri = body.triangulate()
                    y = tri.points[:, 1]
                    cap = [c for c in range(tri.n_cells) if np.all(np.abs(y[tri.get_cell(c).point_ids] - lo[1]) < 1e-6)]
                    area = tri.extract_cells(cap).extract_surface(algorithm="dataset_surface").area
                    self.assertAlmostEqual(area, abs(polygon_area(prof.polygon)),
                                           delta=1e-6 * abs(polygon_area(prof.polygon)))
                finally:
                    pl.close()


@unittest.skipUnless(HAVE_PV, "pyvista not available")
class SharedSolids(unittest.TestCase):
    """The desktop draws scene_model.solid_prims' solids (as the browser does): closed bodies with
    each solid's cross-section and extent."""

    def test_the_desktop_draws_the_shared_solids(self):
        from scene_model import solid_prims, weld_prims
        from scene_vtk import add_setup, solid_mesh
        from weld import polygon_area, split_lobes, template_profile
        solver = build_solver({"probe_type": "Linear", "num_elements": 32, "pitch_mm": 0.6, "freq_mhz": 5},
                              {"angle_deg": 36, "height_mm": 10, "velocity_ms": 2330, "offset_mm": 0},
                              dict(MAT, thickness_mm=25), {"start_element": 1, "num_active_elements": 0})
        c = calculate(solver, dict(SV, wave_type="Shear", param_val=15), "Linear")
        scene = build_scene(solver, lambda i: None, [], sweep_focal_mm=np.asarray(c.focal_points) * 1e3)
        prof = template_profile("double-V", 25, 40, bevel_deg=30, root_gap_mm=0, root_face_mm=0)   # two lobes
        scene.prims += weld_prims(prof)
        solids = solid_prims(scene, 25.0, split_lobes)
        pl = pv.Plotter(off_screen=True, window_size=(200, 150))
        try:
            add_setup(pl, scene, 25.0)
            for role in ("component", "wedge", "weld"):
                with self.subTest(role):
                    mine = [s for s in solids if s["role"] == role]
                    body = pl.actors[f"setup:{role}"].mapper.dataset
                    for sd in mine:                       # each closed (a pinched weld's lobes touch on a line)
                        self.assertEqual(solid_mesh(sd).clean().n_open_edges, 0, "a closed body")
                    want = sum(abs(polygon_area(s["xz"])) * (s["y1"] - s["y0"]) for s in mine)
                    self.assertAlmostEqual(body.triangulate().volume, want, delta=1e-6 * want)
                    b = body.bounds
                    self.assertAlmostEqual(b[2], min(s["y0"] for s in mine))
                    self.assertAlmostEqual(b[3], max(s["y1"] for s in mine))
        finally:
            pl.close()
