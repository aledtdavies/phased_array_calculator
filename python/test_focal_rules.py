"""Focal-target rules: invariants of every mode, rotation signs, refusals, and the shared case table."""
import json
import math
import os
import unittest

import numpy as np

from delay_law import DelayLaw
from focal_rules import Refused, Target, focal_targets
from material import Material
from probe import create_probe_assembly
from wedge import Wedge

VW, VL, VS = 2330.0, 5920.0, 3240.0


def solver(matrix=True, start=1, active=0):
    if matrix:
        p = create_probe_assembly("Matrix", 8, 1e-3, 5e6, num_elements_y=4, pitch_y=1.2e-3,
                                  start_element=start, num_active_elements=active)
    else:
        p = create_probe_assembly("Linear", 16, 0.6e-3, 5e6, start_element=start,
                                  num_active_elements=active)
    return DelayLaw(p, Wedge(30.0, 0.012, VW, 0.003), Material(VL, VS))


def entry_point(s, t, wave="longitudinal"):
    """The central ray's entry point for target t, from the rule's own definition."""
    cx, cy, cz = s.aperture_centre()
    v = VL if wave == "longitudinal" else VS
    e = abs(cz) * math.tan(math.asin(VW / v * math.sin(math.radians(t.angle_deg))))
    sk = math.radians(t.skew_deg)
    return np.array([cx + e * math.cos(sk), cy + e * math.sin(sk), 0.0])


class TestInvariants(unittest.TestCase):
    """
    Every target lies on its central ray: from the entry point along
    (sin b cos s, sin b sin s, cos b), b the refracted angle and s the skew.
    """

    def check_on_ray(self, s, targets, wave="longitudinal"):
        n = 0
        for t in targets:
            if not isinstance(t, Target):
                continue
            d = np.array(t.point) - entry_point(s, t, wave)
            b, sk = math.radians(t.angle_deg), math.radians(t.skew_deg)
            want = np.array([math.sin(b) * math.cos(sk), math.sin(b) * math.sin(sk), math.cos(b)])
            np.testing.assert_allclose(d / np.linalg.norm(d), want, atol=1e-12)
            n += 1
        self.assertGreater(n, 0)

    def test_constant_depth(self):
        s = solver()
        ts = focal_targets(s, "constant-depth", 0.025, [-20, 0, 35, 60], [-15, 0, 20])
        self.check_on_ray(s, ts)
        self.assertTrue(all(abs(t.z - 0.025) < 1e-15 for t in ts))

    def test_sound_path(self):
        s = solver()
        ts = focal_targets(s, "sound-path", 0.04, [0, 30, 55], [-10, 0, 25], wave="shear")
        self.check_on_ray(s, ts, "shear")
        for t in ts:
            self.assertAlmostEqual(np.linalg.norm(np.array(t.point) - entry_point(s, t, "shear")), 0.04, places=12)

    def test_vertical_line(self):
        s = solver()
        ts = [t for t in focal_targets(s, "vertical-line", 0.05, [20, 45, 70], [-20, 0, 30])
              if isinstance(t, Target)]
        self.check_on_ray(s, ts)
        self.assertTrue(all(abs(t.x - 0.05) < 1e-15 for t in ts))

    def test_sub_aperture_moves_the_ray_start(self):
        full, sub = solver(False), solver(False, start=9, active=8)
        a = focal_targets(full, "constant-depth", 0.03, [45])[0]
        b = focal_targets(sub, "constant-depth", 0.03, [45])[0]
        self.check_on_ray(sub, [b])
        self.assertGreater(b.x, a.x)   # elements 9-16 sit further along +X


class TestSigns(unittest.TestCase):
    """Rotation signs: +skew turns the beam from +X towards +Y; +angle steers towards +X."""

    def test_skew_sign(self):
        s = solver()
        cx, cy, _ = s.aperture_centre()
        plus, minus = focal_targets(s, "constant-depth", 0.03, [45], [20, -20])
        self.assertGreater(plus.y, cy)
        self.assertLess(minus.y, cy)
        self.assertAlmostEqual(plus.y - cy, cy - minus.y, places=12)
        self.assertAlmostEqual(plus.x, minus.x, places=12)

    def test_angle_sign(self):
        s = solver()
        cx, _, _ = s.aperture_centre()
        pos, neg = focal_targets(s, "constant-depth", 0.03, [30, -30])
        self.assertGreater(pos.x, cx)
        self.assertLess(neg.x, cx)


class TestYModes(unittest.TestCase):
    def test_fixed_y(self):
        ts = focal_targets(solver(), "constant-depth", 0.03, [40, 50], [-10, 10], y_mode="fixed",
                           y_values=[0.004])
        self.assertTrue(all(t.y == 0.004 for t in ts))
        self.assertEqual(len(ts), 4)

    def test_sweep_constant_depth(self):
        ts = focal_targets(solver(), "constant-depth", 0.03, [40], [0, 10], y_mode="sweep",
                           y_values=[-0.002, 0.0, 0.002])
        self.assertEqual([(t.skew_deg, t.y) for t in ts],
                         [(0.0, -0.002), (0.0, 0.0), (0.0, 0.002),
                          (10.0, -0.002), (10.0, 0.0), (10.0, 0.002)])

    def test_sound_path_sweep_solves_skew(self):
        s = solver()
        ts = focal_targets(s, "sound-path", 0.04, [30, 60], [-30, 0, 30], y_mode="sweep",
                           y_values=[0.0, 0.01, 0.1])
        good = [t for t in ts if isinstance(t, Target)]
        TestInvariants().check_on_ray(s, good)
        for t in good:
            self.assertAlmostEqual(np.linalg.norm(np.array(t.point) - entry_point(s, t)), 0.04, places=12)
        # Skew list used once: 3 Y values per angle; 0.1 m is out of reach at both angles.
        self.assertEqual(len(ts), 6)
        self.assertEqual([t.reason for t in ts if isinstance(t, Refused)], ["Y out of reach"] * 2)

    def test_sound_path_sweep_without_reach(self):
        """At 0 deg the central ray has no horizontal reach: only the centre's Y is on it."""
        s = solver()
        _, cy, _ = s.aperture_centre()
        ts = focal_targets(s, "sound-path", 0.04, [0], [0], y_mode="sweep", y_values=[cy, cy + 0.01])
        self.assertIsInstance(ts[0], Target)
        self.assertEqual(ts[1].reason, "Y out of reach")
        TestInvariants().check_on_ray(s, ts[:1])
        self.assertAlmostEqual(np.linalg.norm(np.array(ts[0].point) - entry_point(s, ts[0])), 0.04, places=12)

    def test_numpy_y_values(self):
        s = solver()
        for mode, y_mode, ys in (("constant-depth", "fixed", [0.0]),
                                 ("constant-depth", "sweep", [0.0, 0.001]),
                                 ("sound-path", "sweep", [0.0, 0.001])):
            a = focal_targets(s, mode, 0.03, [40], [0, 5], y_mode=y_mode, y_values=ys)
            b = focal_targets(s, mode, 0.03, [40], [0, 5], y_mode=y_mode, y_values=np.array(ys))
            self.assertEqual(a, b)
        with self.assertRaises(ValueError):
            focal_targets(s, "constant-depth", 0.03, [40], y_mode="sweep", y_values=np.array([]))

    def test_fixed_y_with_sound_path_is_refused(self):
        with self.assertRaises(ValueError):
            focal_targets(solver(), "sound-path", 0.04, [30], y_mode="fixed", y_values=[0.0])


class TestRefusals(unittest.TestCase):
    def test_reasons(self):
        s = solver()
        slow = DelayLaw(s.probe, s.wedge, Material(2000.0, 1000.0))   # 2330/2000 sin 80 > 1
        crit = focal_targets(slow, "constant-depth", 0.03, [80], [0, 10])
        self.assertEqual([r.reason for r in crit], ["critical angle"] * 2)
        self.assertEqual([r.skew_deg for r in crit], [0.0, 10.0])
        par = focal_targets(s, "vertical-line", 0.05, [0, 40], [0, 90])
        self.assertEqual([getattr(r, "reason", "ok") for r in par],
                         ["beam parallel to line", "beam parallel to line", "ok",
                          "beam parallel to line"])
        neg = focal_targets(s, "constant-depth", -0.01, [40])
        self.assertEqual(neg[0].reason, "focus not below surface")
        zero = focal_targets(s, "constant-depth", 0.0, [40])
        self.assertEqual(zero[0].reason, "focus not below surface")
        behind = focal_targets(s, "vertical-line", -0.05, [40], [0, 60])
        self.assertTrue(all(r.reason == "focus not below surface" for r in behind))

    def test_bad_inputs(self):
        s = solver()
        for kw in ({"mode": "banana"}, {"wave": "banana"}, {"y_mode": "sweep"}):
            args = dict(mode="constant-depth", wave="longitudinal", y_mode="from-skew")
            args.update(kw)
            with self.assertRaises(ValueError):
                focal_targets(s, args["mode"], 0.03, [40], wave=args["wave"], y_mode=args["y_mode"])
        s.material = Material(VL)
        with self.assertRaises(ValueError):
            focal_targets(s, "constant-depth", 0.03, [40], wave="shear")


CASES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "focal_rule_cases.json")


class TestSharedCaseTable(unittest.TestCase):
    """tests/focal_rule_cases.json (read by MATLAB's testFocalRules) is current."""

    def test_case_table_is_current(self):
        from make_focal_rule_cases import build_cases
        with open(CASES, encoding="utf-8") as f:
            stored = json.load(f)
        fresh = json.loads(json.dumps(build_cases()))
        self.assertEqual(len(stored["cases"]), len(fresh["cases"]))
        for a, b in zip(stored["cases"], fresh["cases"]):
            self.assertEqual(a["inputs"], b["inputs"])
            self.assertEqual(len(a["targets"]), len(b["targets"]), a["name"])
            for ta, tb in zip(a["targets"], b["targets"]):
                self.assertEqual(ta.get("reason"), tb.get("reason"))
                for k in ("angle", "skew", "x", "y", "z"):
                    if ta.get(k) is None or tb.get(k) is None:
                        self.assertEqual(ta.get(k), tb.get(k))
                    else:
                        self.assertAlmostEqual(ta[k], tb[k], places=12)


if __name__ == "__main__":
    unittest.main()
