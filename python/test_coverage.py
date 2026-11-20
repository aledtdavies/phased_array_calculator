"""Coverage: central rays, skips in a flat plate and fans (plan step 5a)."""
import math
import unittest

import numpy as np

from coverage import central_ray, fans, skip_path, sweep_paths
from delay_law import DelayLaw
from focal_rules import Target, focal_targets
from material import Material
from probe import create_probe_assembly
from wedge import Wedge

VW, VL, VS = 2330.0, 5920.0, 3240.0


def solver(matrix=False):
    p = (create_probe_assembly("Matrix", 8, 1e-3, 5e6, num_elements_y=4, pitch_y=1.2e-3) if matrix
         else create_probe_assembly("Linear", 32, 0.6e-3, 5e6, start_element=9, num_active_elements=16))
    return DelayLaw(p, Wedge(36.0, 0.010, VW, 0.004), Material(VL, VS))


class TestCentralRay(unittest.TestCase):
    def test_snell_at_the_entry_and_the_rules_direction(self):
        for wave, v in (("longitudinal", VL), ("shear", VS)):
            s = solver(matrix=True)
            for t in focal_targets(s, "constant-depth", 0.02, [0, 35, 50, 65], [-20, 0, 15], wave=wave):
                if not isinstance(t, Target):
                    continue
                entry, d = central_ray(s, t.point, wave)
                self.assertEqual(entry[2], 0.0)
                inc = entry - s.aperture_centre()
                sin_i = math.hypot(inc[0], inc[1]) / np.linalg.norm(inc)
                sin_r = math.hypot(d[0], d[1])
                self.assertAlmostEqual(sin_i / VW, sin_r / v, places=12)
                b, sk = math.radians(t.angle_deg), math.radians(t.skew_deg)
                want = [math.sin(b) * math.cos(sk), math.sin(b) * math.sin(sk), math.cos(b)]
                np.testing.assert_allclose(d, want, atol=1e-9)

    def test_focus_above_the_surface_is_refused(self):
        with self.assertRaises(ValueError):
            central_ray(solver(), (0.03, 0.0, -0.001))


class TestSkips(unittest.TestCase):
    def test_walls_and_angle(self):
        T = 0.025
        for skew in (-30.0, 0.0, 30.0):
            b, sk = math.radians(55), math.radians(skew)
            d = np.array([math.sin(b) * math.cos(sk), math.sin(b) * math.sin(sk), math.cos(b)])
            path = skip_path(np.array([0.01, 0.0, 0.0]), d, T, 3)
            np.testing.assert_allclose(path[:, 2], [0.0, T, 0.0, T], atol=1e-15)
            for a, c in zip(path[:-1], path[1:]):
                seg = c - a
                # angle to the wall normal preserved, horizontal direction unchanged
                self.assertAlmostEqual(abs(seg[2]) / np.linalg.norm(seg), math.cos(b), places=12)
                h = seg[:2] / np.linalg.norm(seg[:2])
                np.testing.assert_allclose(h, [math.cos(sk), math.sin(sk)], atol=1e-12)
            # sign: +skew moves +Y, -skew -Y, and every leg spans T * tan(b) horizontally
            self.assertEqual(np.sign(path[-1, 1]), np.sign(skew))
            np.testing.assert_allclose(np.linalg.norm(np.diff(path[:, :2], axis=0), axis=1),
                                       T * math.tan(b), rtol=1e-12)

    def test_refusals(self):
        down = np.array([0.5, 0.0, math.sqrt(0.75)])
        with self.assertRaises(ValueError):
            skip_path(np.zeros(3), down, 0.0, 2)                  # no thickness
        with self.assertRaises(ValueError):
            skip_path(np.zeros(3), np.array([1.0, 0, 0]), 0.02, 2)  # parallel to the walls
        with self.assertRaises(ValueError):
            skip_path(np.zeros(3), down, 0.02, 0)


class TestFans(unittest.TestCase):
    def test_fans_by_skew_between_neighbouring_angles(self):
        s = solver(matrix=True)
        ts = [t for t in focal_targets(s, "constant-depth", 0.02, [40, 50, 60], [-10, 10]) if isinstance(t, Target)]
        results = [{"angle": t.angle_deg, "skew": t.skew_deg, "fy": t.y} for t in ts]
        paths = sweep_paths(s, [t.point for t in ts], 0.03, 2)
        f = fans(results, paths)
        self.assertEqual(sorted(f), [1, 2])
        self.assertEqual(len(f[1]), 4)                 # 2 skews x (3 angles - 1)
        for q in f[1]:
            np.testing.assert_allclose(q[[0, 3], 2], 0.0, atol=1e-15)   # top edge on the surface
            np.testing.assert_allclose(q[[1, 2], 2], 0.03, atol=1e-15)  # bottom edge on the backwall
            ys = q[:, 1] - s.aperture_centre()[1]
            self.assertTrue(np.all(ys[1:3] > 0) or np.all(ys[1:3] < 0))  # one skew side per quad

    def test_y_sweep_targets_at_one_angle_make_no_fan(self):
        results = [{"angle": 40.0, "skew": 0.0, "fy": y} for y in (-0.002, 0.0, 0.002)]
        paths = [np.zeros((2, 3))] * 3
        self.assertEqual(fans(results, paths), {1: []})


if __name__ == "__main__":
    unittest.main()
