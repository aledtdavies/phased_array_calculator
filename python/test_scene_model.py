"""Scene model invariants: every view draws the same geometry, decided once here."""
import unittest

import numpy as np

from delay_law import DelayLaw
from focal_rules import focal_targets
from material import Material
from probe import create_probe_assembly
from scene_model import build_scene, envelope_indices, scene_bounds, section_y, solid_prims, triangulate_polygon
from wedge import Wedge


def setups():
    yield "linear sub-aperture", create_probe_assembly("Linear", 32, 0.6e-3, 5e6, start_element=9,
                                                       num_active_elements=16), Wedge(36, 0.01, 2330)
    yield "matrix row-first", create_probe_assembly("Matrix", 8, 1e-3, 5e6, num_elements_y=4, pitch_y=1e-3,
                                                    start_element=3, num_active_elements=20,
                                                    element_order="row-first"), Wedge(20, 0.008, 2330)
    yield "dual linear, Rx only partly active", create_probe_assembly(
        "Dual Linear", 16, 0.5e-3, 5e6, array_separation=8e-3, start_element=12,
        num_active_elements=10), Wedge(15, 0.006, 2330, roof_angle_degrees=3)
    yield "dual matrix contact", create_probe_assembly(
        "Dual Matrix", 4, 1e-3, 5e6, num_elements_y=2, pitch_y=1e-3, array_separation=10e-3,
        start_element=2, num_active_elements=12), Wedge(0, 0.0, 2330)


def scene_for(probe, wedge, current=1, max_rays=None, outline_mm=None):
    s = DelayLaw(probe, wedge, Material(5920, 3240))
    targets = focal_targets(s, "constant-depth", 0.03, [40, 50, 60], [0, 10] if probe.num_elements_y > 1 else [0])
    laws = [s.calculate_law(*t.point) for t in targets]
    get = lambda i: (laws[i]["interface_points"] * 1e3, np.array(targets[i].point) * 1e3)
    fp = np.array([t.point for t in targets]) * 1e3
    return s, laws, targets, build_scene(s, get, range(len(laws)), current=current, max_rays=max_rays,
                                         outline_mm=outline_mm, sweep_focal_mm=fp)


class TestSceneModel(unittest.TestCase):
    def test_elements_once_each_with_active_flags(self):
        for name, probe, wedge in setups():
            with self.subTest(name):
                s, _, _, sc = scene_for(probe, wedge)
                el = s.wedge.get_transformed_elements(probe) * 1e3
                idx = np.concatenate([p.meta["indices"] for p in sc.find("element")])
                self.assertEqual(sorted(idx), list(range(probe.total_elements)))
                act = set(probe.get_active_element_indices())
                for p in sc.find("element"):
                    np.testing.assert_array_equal(p.coords, el[p.meta["indices"]])
                    self.assertTrue(all((i in act) == p.meta["active"] for i in p.meta["indices"]))
                    if p.meta["array"] != "single":
                        half = probe.total_elements // 2
                        self.assertTrue(all((i < half) == (p.meta["array"] == "tx")
                                            for i in p.meta["indices"]))

    def test_rays_run_element_interface_focus(self):
        for name, probe, wedge in setups():
            with self.subTest(name):
                s, laws, targets, sc = scene_for(probe, wedge)
                el = s.wedge.get_transformed_elements(probe) * 1e3
                for law in range(len(laws)):
                    env = sc.find("envelope-ray", law=law)
                    want = [i for _, i0, i1 in envelope_indices(probe) for i in (i0, i1)]
                    self.assertEqual([p.meta["element"] for p in env], want)
                    focus = sc.one("focus", law=law).coords[0]
                    np.testing.assert_allclose(focus, np.array(targets[law].point) * 1e3)
                    for p in env:
                        a, b, c, d = p.coords
                        np.testing.assert_array_equal(a, el[p.meta["element"]])
                        np.testing.assert_array_equal(b, c)
                        self.assertEqual(b[2], 0.0)          # the interface is Z = 0
                        np.testing.assert_array_equal(d, focus)
                rays = sc.find("ray", law=1)
                self.assertEqual(sorted(np.concatenate([p.meta["elements"] for p in rays])),
                                 sorted(probe.get_active_element_indices()))

    def test_ray_decimation_keeps_ends(self):
        probe = create_probe_assembly("Linear", 128, 0.5e-3, 5e6)
        _, _, _, sc = scene_for(probe, Wedge(36, 0.01, 2330), max_rays=10)
        (rays,) = sc.find("ray")
        self.assertLessEqual(len(rays.meta["elements"]), 10)
        self.assertEqual((rays.meta["elements"][0], rays.meta["elements"][-1]), (0, 127))
        self.assertEqual(rays.meta["n_active"], 128)

    def test_wedge_source_and_contact(self):
        probe = create_probe_assembly("Linear", 16, 0.6e-3, 5e6)
        _, _, _, sc = scene_for(probe, Wedge(36, 0.01, 2330))
        self.assertEqual(sc.one("wedge").meta["source"], "schematic")
        self.assertFalse(sc.contact)
        outline = [(0.0, 0.0), (60.0, 0.0), (60.0, -40.0), (0.0, -2.0)]
        _, _, _, sc = scene_for(probe, Wedge(36, 0.01, 2330), outline_mm=outline)
        w = sc.one("wedge")
        self.assertEqual(w.meta["source"], "catalogue")
        np.testing.assert_array_equal(w.coords[:, [0, 2]], outline)
        self.assertTrue(np.all(w.coords[:, 1] == 0))
        self.assertLess(w.meta["y0"], 0)
        self.assertGreater(w.meta["y1"], 0)
        _, _, _, sc = scene_for(probe, Wedge(0, 0.0, 2330))
        self.assertTrue(sc.contact)
        self.assertEqual(sc.find("wedge"), [])
        self.assertEqual(len(sc.find("contact")), 1)

    def test_single_law_scene(self):
        """One law (no neighbours) builds a complete scene (review of PR #23)."""
        probe = create_probe_assembly("Linear", 16, 0.6e-3, 5e6)
        s = DelayLaw(probe, Wedge(36, 0.01, 2330), Material(5920, 3240))
        (t,) = focal_targets(s, "constant-depth", 0.03, [45])
        law = s.calculate_law(*t.point)
        sc = build_scene(s, lambda i: (law["interface_points"] * 1e3, np.array(t.point) * 1e3), [0],
                         current=0, sweep_focal_mm=np.array([t.point]) * 1e3)
        self.assertEqual(len(sc.find("focus")), 1)
        self.assertEqual(len(sc.find("focus-sweep")[0].coords), 1)
        self.assertTrue(sc.find("ray"))


def _area(xy):
    p = np.asarray(xy, dtype=float)
    return 0.5 * abs(float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])))


def _tri_area(p, t):
    a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
    return 0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))


class TestSolids(unittest.TestCase):
    """The 3D views' solids (scene_model.solid_prims): both the desktop and the browser fill these."""

    def test_triangulation_fills_the_polygon_exactly(self):
        shapes = {
            "square": [(0, 0), (1, 0), (1, 1), (0, 1)],
            "clockwise L": [(0, 0), (0, 2), (1, 2), (1, 1), (2, 1), (2, 0)],
            "collinear points": [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)],
            "single-V weld": [(-7, 0), (7, 0), (1, 23.5), (1, 25), (-1, 25), (-1, 23.5)],
            "comb": [(0, 0), (5, 0), (5, 3), (4, 3), (4, 1), (3, 1), (3, 3), (2, 3), (2, 1), (1, 1), (1, 3), (0, 3)],
            # a vertex on the diagonal (0,0)-(2,2): that diagonal must not be cut (review of PR #40)
            "vertex on a diagonal": [(0, 0), (2, 0), (2, 2), (1, 1), (0, 2)],
            "vertex on a diagonal, reversed": [(0, 2), (1, 1), (2, 2), (2, 0), (0, 0)],
            "notch to the diagonal": [(0, 0), (4, 0), (4, 4), (2, 2), (2, 4), (0, 4)],
        }
        for name, poly in shapes.items():
            with self.subTest(name):
                p = np.asarray(poly, dtype=float)
                t = triangulate_polygon(p)
                self.assertEqual(len(t), len(p) - 2)
                self.assertAlmostEqual(float(_tri_area(p, t).sum()), _area(p), places=9)   # no overlap, nothing outside
                # every triangle inside: its centroid lies in the polygon (non-convex shapes)
                from matplotlib.path import Path
                cen = p[t].mean(axis=1)
                self.assertTrue(Path(p).contains_points(cen).all())

    def test_solids_cover_the_component_wedge_and_weld(self):
        from session import build_solver, calculate
        from scene_model import weld_prims
        import weld
        solver = build_solver({"probe_type": "Linear", "num_elements": 32, "pitch_mm": 0.6, "freq_mhz": 5},
                              {"angle_deg": 36, "height_mm": 5, "velocity_ms": 2337, "offset_mm": 0},
                              {"vel_long_ms": 5900, "vel_shear_ms": 3230, "thickness_mm": 20},
                              {"start_element": 1, "num_active_elements": 0})
        c = calculate(solver, {"focus_mode": "Constant Depth", "param_val": 15, "start_angle": 45, "end_angle": 60,
                               "step_angle": 5, "wave_type": "Shear"}, "Linear")
        sc = build_scene(solver, lambda i: None, [], sweep_focal_mm=np.asarray(c.focal_points) * 1e3)
        prof = weld.template_profile("double-V", 20, 30, bevel_deg=30, bevel2_deg=30, root_gap_mm=0,
                                     root_face_mm=0, root_depth_mm=10)
        sc.prims += weld_prims(prof)
        lo, hi = scene_bounds(sc, 20)
        solids = solid_prims(sc, 20, weld.split_lobes)
        roles = [s["role"] for s in solids]
        self.assertEqual(roles, ["component", "wedge", "weld", "weld"])     # a closed-root double-V: two lobes
        comp = solids[0]
        self.assertAlmostEqual(_tri_area(comp["xz"], comp["tris"]).sum(), (hi[0] - lo[0]) * 20)
        w = sc.one("wedge")
        self.assertEqual((solids[1]["y0"], solids[1]["y1"]), (w.meta["y0"], w.meta["y1"]))
        weld_area = sum(_tri_area(s["xz"], s["tris"]).sum() for s in solids[2:])
        self.assertAlmostEqual(weld_area, _area(prof.polygon), places=6)
        for s in solids[2:]:
            self.assertEqual((s["y0"], s["y1"]), (lo[1], hi[1]))
        self.assertAlmostEqual(section_y(sc), float(np.mean(solver._geometry()[0][:, 1] * 1e3)))
        # no thickness: no component block (the views draw the interface plane instead)
        self.assertEqual([s["role"] for s in solid_prims(sc, 0.0)][:1], ["wedge"])


if __name__ == "__main__":
    unittest.main()
