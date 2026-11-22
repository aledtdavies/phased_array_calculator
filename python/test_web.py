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

    def test_bad_input_is_refused_with_a_reason(self):
        bad = json.loads(json.dumps(CFG))
        bad["material"]["vel_shear_ms"] = 0
        with self.assertRaises(Exception):
            pac_web.calc(json.dumps(bad))


if __name__ == "__main__":
    unittest.main()
