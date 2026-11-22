"""The browser version's Python layer (web/pac_web.py), run here in CPython: it must give the
desktop window's calculation, and a beam field normalised to 0 dB with the -30 dB floor."""
import json
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web"))

import pac_web                                    # noqa: E402
from session import build_solver, calculate       # noqa: E402

CFG = {"probe": {"probe_type": "Linear", "num_elements": 64, "pitch_mm": 0.75, "freq_mhz": 2.25},
       "wedge": {"angle_deg": 36, "height_mm": 5, "velocity_ms": 2337, "offset_mm": 4},
       "material": {"vel_long_ms": 5900, "vel_shear_ms": 3230, "thickness_mm": 40},
       "sub_aperture": {"start_element": 1, "num_active_elements": 32},
       "scan": {"wave_type": "Shear", "focus_mode": "Constant Depth", "param_val": 25,
                "start_angle": 30, "end_angle": 80, "step_angle": 10}}


class TestWebLayer(unittest.TestCase):
    def test_the_table_and_laws_are_the_desktop_calculation(self):
        r = json.loads(pac_web.calc(json.dumps(CFG)))
        c = calculate(build_solver(CFG["probe"], CFG["wedge"], CFG["material"], CFG["sub_aperture"]),
                      CFG["scan"], "Linear")
        self.assertEqual(r["rows"], [[str(v) for v in values] for values, _ in c.rows])
        self.assertEqual(len(r["laws"]), len(c.results))
        self.assertEqual(r["active"], list(range(32)))
        for law, res in zip(r["laws"], c.results):
            np.testing.assert_allclose(law["delays"], res["delays_us"][:32], atol=1e-5)
            np.testing.assert_allclose(law["focus"], [res["fx"] * 1e3, res["fz"] * 1e3], atol=1e-4)
            self.assertEqual(len(law["interface"]), 32)

    def test_the_field_is_in_db_re_its_maximum(self):
        pac_web.calc(json.dumps(CFG))
        r = json.loads(pac_web.field(json.dumps({
            "law": 1, "pulsed": False, "cycles": 3, "grid_mm": 1.0, "element_width_mm": 0.55,
            "wedge_shear_ms": 1157, "wedge_density": 1049, "component_density": 7900})))
        db = np.array(r["db"])
        self.assertEqual(db.shape, (len(r["z"]), len(r["x"])))
        self.assertAlmostEqual(db.max(), 0.0, places=6)
        self.assertGreaterEqual(db.min(), pac_web.FLOOR_DB)
        self.assertEqual(r["points"], db.size)
        self.assertTrue(all(0 < z <= 40 + 1e-9 for z in r["z"]))

    def test_a_tiny_grid_step_never_allocates_more_than_the_limit(self):
        """Review of PR #37: section_grid made the full arrays before coarsening them."""
        from unittest import mock
        import beam_field
        real = np.arange
        sizes = []

        def spy(n, *a, **k):
            sizes.append(n)
            return real(n, *a, **k)
        pac_web.calc(json.dumps(CFG))
        with mock.patch.object(beam_field.np, "arange", side_effect=spy):
            (x, z), step = beam_field.section_grid((0.0, 1e-9), (0.1, 0.04), 1e-12, pac_web.MAX_POINTS)
        self.assertLessEqual(x.size * z.size, pac_web.MAX_POINTS)
        self.assertTrue(all(n <= pac_web.MAX_POINTS for n in sizes), sizes)
        for bad in (0.0, -1.0, float("nan")):
            with self.assertRaises(ValueError):
                beam_field.section_grid((0.0, 0.0), (0.1, 0.04), bad, 100)

    def test_the_field_reply_names_its_law_and_the_model(self):
        pac_web.calc(json.dumps(CFG))
        r = json.loads(pac_web.field(json.dumps({
            "law": 2, "pulsed": False, "cycles": 3, "grid_mm": 1e-9, "element_width_mm": 0.55,
            "wedge_shear_ms": 1157, "wedge_density": 1049, "component_density": 7900})))
        self.assertEqual(r["law"], 2)
        self.assertLessEqual(r["points"], pac_web.MAX_POINTS)
        self.assertIn("direct beam only", r["note"])

    def test_the_build_empties_only_a_folder_it_built(self):
        """Review of PR #37: the build emptied whatever folder it was given."""
        import tempfile
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
        import build_web
        for bad in (build_web.ROOT, os.path.dirname(build_web.ROOT), os.path.join(build_web.ROOT, "python"),
                    os.path.join(build_web.ROOT, "docs", "plans")):
            with self.assertRaises(SystemExit):
                build_web.build(bad)
        with tempfile.TemporaryDirectory() as d:
            precious = os.path.join(d, "keep.txt")
            open(precious, "w").close()
            with self.assertRaises(SystemExit):
                build_web.build(d)                       # not empty, not a built site
            self.assertTrue(os.path.exists(precious))
            site = os.path.join(d, "site")
            build_web.build(site)                        # new folder: built and marked
            build_web.build(site)                        # rebuilt in place
            self.assertTrue(os.path.isfile(os.path.join(site, "py", "session.py")))
            for f in ("help.html", "web.config", "config.js"):
                self.assertTrue(os.path.isfile(os.path.join(site, f)), f)
            self.assertTrue(os.path.isfile(os.path.join(site, build_web.MARKER)))
            # the model note the page links to, with the figure it shows (review of PR #37)
            note = open(os.path.join(site, "docs", "beam_field_model.html"), encoding="utf-8").read()
            self.assertIn('src="plans/images/step6_beam_vs_buildfe.png"', note)
            self.assertTrue(os.path.isfile(os.path.join(site, "docs", "plans", "images", "step6_beam_vs_buildfe.png")))

    def test_bad_input_is_refused_with_a_reason(self):
        bad = json.loads(json.dumps(CFG))
        bad["material"]["vel_shear_ms"] = 0
        with self.assertRaises(Exception):
            pac_web.calc(json.dumps(bad))


if __name__ == "__main__":
    unittest.main()
