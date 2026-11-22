"""The browser version's Python layer (web/pac_web.py), run here in CPython: it must calculate and
draw what the desktop window does, and its panels (web/panels.json) must have the desktop's
defaults."""
import base64
import json
import os
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "web"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import field_job                                   # noqa: E402
import pac_web                                     # noqa: E402
from session import build_solver, calculate, write_laws_csv    # noqa: E402

BUILDFE_CATALOG = os.path.normpath(os.path.join(ROOT, "..", "buildFE", "catalog"))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "tk_saved_configs.json")


def cfg(**over):
    c = {"probe": {"probe_type": "Linear", "num_elements": 64, "pitch_mm": 0.75, "freq_mhz": 2.25},
         "wedge": {"angle_deg": 36, "height_mm": 5, "velocity_ms": 2337, "offset_mm": 4},
         "material": {"vel_long_ms": 5900, "vel_shear_ms": 3230, "thickness_mm": 25},
         "sub_aperture": {"start_element": 1, "num_active_elements": 32},
         "scan": {"wave_type": "Shear", "focus_mode": "Constant Depth", "param_val": 20,
                  "start_angle": 30, "end_angle": 80, "step_angle": 10}}
    c.update(over)
    return c


def call(fn, arg=None):
    return json.loads(getattr(pac_web, fn)(json.dumps(arg or {})))


FIELD = {"model": "2D", "pulsed": False, "cycles": 3, "grid_mm": 1.0, "element_width_mm": 0.55,
         "elevation_mm": 10, "wedge_shear_ms": 1157, "wedge_density": 1049, "component_density": 7900}


class TestPanels(unittest.TestCase):
    def test_the_panels_have_the_desktop_defaults(self):
        panels = json.load(open(os.path.join(ROOT, "web", "panels.json"), encoding="utf-8"))
        got = {s["id"]: {f["key"]: f["default"] for f in s["fields"] if not f["key"].startswith("_")}
               for s in panels["sections"]}
        with open(FIXTURE) as f:
            tk = json.load(f)["defaults"]             # saved by the desktop (Tk) window itself
        for sec in ("probe", "wedge", "material", "scan", "sub_aperture"):
            self.assertEqual(got[sec], tk[sec], sec)
        # the weld and beam-field panels of the Qt window (no Tk equivalent)
        self.assertEqual(got["weld"], {"type": "None", "centre_x_mm": 40.0, "bevel_deg": 30.0, "bevel2_deg": 30.0,
                                       "root_gap_mm": 2.0, "root_face_mm": 1.5, "root_depth_mm": 0.0,
                                       "root_radius_mm": 6.0, "j_side": "near", "dxf_path": "", "dxf_datum": "surface",
                                       "dxf_units": "", "dxf_layer": ""})
        self.assertEqual(got["beam_field"], {"model": "2D", "pulsed": True, "cycles": 3.0, "grid_mm": 0.5,
                                             "element_width_mm": 0.5, "elevation_mm": 10.0, "wedge_shear_ms": 1157.0,
                                             "wedge_density": 1049.0, "component_density": 7850.0})
        self.assertEqual(panels["matrix"], ["Matrix", "Dual Matrix"])
        self.assertEqual(panels["dual"], ["Dual Linear", "Dual Matrix"])


class TestWebLayer(unittest.TestCase):
    def test_the_table_laws_and_delays_are_the_desktop_calculation(self):
        c0 = cfg()
        r = call("calc", c0)
        c = calculate(build_solver(c0["probe"], c0["wedge"], c0["material"], c0["sub_aperture"]), c0["scan"], "Linear")
        self.assertEqual([row[:-1] for row in r["rows"]], [[str(v) for v in values] for values, _ in c.rows])
        self.assertEqual([row[-1] for row in r["rows"]], [idx for _, idx in c.rows])
        self.assertEqual(len(r["laws"]), len(c.results))
        self.assertEqual(r["probe"]["active"], list(range(32)))
        for i, res in enumerate(c.results):
            law = call("law", {"law": i})
            np.testing.assert_allclose(np.array(law["delays_us"], dtype=float), res["delays_us"], atol=1e-5, equal_nan=True)
            np.testing.assert_allclose(law["focus"], [res["fx"] * 1e3, res["fy"] * 1e3, res["fz"] * 1e3], atol=1e-3)
            self.assertEqual({p["role"] for p in law["prims"]}, {"envelope-ray", "ray", "interface-point", "focus"})
        roles = {p["role"] for p in r["setup"]}
        self.assertTrue({"element", "wedge", "focus-sweep"} <= roles, roles)

    def test_every_shared_scan_case_gives_the_desktop_table(self):
        """The scan cases the desktop window's tests use (test_qt_gui.SCAN_CASES): matrix, dual,
        Y sweeps and refusals, each from the desktop's own defaults."""
        from test_qt_gui import SCAN_CASES
        with open(FIXTURE) as f:
            base = json.load(f)["defaults"]
        probe = dict(base["probe"])
        for name, (pv, sv) in SCAN_CASES.items():      # as the desktop test: probe values carry over
            with self.subTest(name):
                probe.update(pv)
                c0 = dict(base, probe=dict(probe), scan=dict(base["scan"], **sv))
                r = call("calc", c0)
                c = calculate(build_solver(c0["probe"], c0["wedge"], c0["material"], c0["sub_aperture"]),
                              c0["scan"], c0["probe"]["probe_type"])
                self.assertEqual([row[:-1] for row in r["rows"]], [[str(v) for v in values] for values, _ in c.rows])
                self.assertGreater(len(r["rows"]), 0)
                if r["laws"]:
                    law = call("law", {"law": len(r["laws"]) - 1})
                    np.testing.assert_allclose(np.array(law["delays_us"], dtype=float), c.results[-1]["delays_us"],
                                               atol=1e-5, equal_nan=True)

    def test_coverage_and_a_weld_come_with_the_scene(self):
        c0 = cfg(view={"coverage_legs": 2},
                 weld={"type": "Single-V", "centre_x_mm": 45, "bevel_deg": 30, "root_gap_mm": 2, "root_face_mm": 1.5})
        r = call("calc", c0)
        roles = {p["role"] for p in r["setup"]}
        self.assertTrue({"coverage", "weld"} <= roles and roles & {"fusion-covered", "fusion-gap"}, roles)
        self.assertIn("Fusion faces", r["notes"]["weld"])
        self.assertEqual(r["notes"]["coverage"], pac_web.MODE_ASSUMPTION)
        law = call("law", {"law": 0})
        self.assertIn("central-ray", {p["role"] for p in law["prims"]})
        # a weld that cannot be made is reported, and the laws are still calculated
        bad = call("calc", cfg(weld={"type": "DXF file", "centre_x_mm": 45, "dxf_path": ""}))
        self.assertIn("DXF", bad["notes"]["weld_error"])
        self.assertTrue(bad["laws"])

    def test_the_initial_frame_holds_the_weld(self):
        """Review of PR #39: a weld away from the foci was outside the initial view."""
        c0 = cfg(probe={"probe_type": "Linear", "num_elements": 16, "pitch_mm": 0.6, "freq_mhz": 5},
                 sub_aperture={"start_element": 1, "num_active_elements": 0},
                 scan={"wave_type": "Shear", "focus_mode": "Constant Depth", "param_val": 20,
                       "start_angle": 40, "end_angle": 45, "step_angle": 5},
                 weld={"type": "Single-V", "centre_x_mm": 65, "bevel_deg": 30, "root_gap_mm": 2, "root_face_mm": 1.5})
        r = call("calc", c0)
        weld = [p for p in r["setup"] if p["role"] == "weld"][0]
        xs = [c[0] for c in weld["coords"]]
        self.assertLessEqual(r["frame"]["lo"][0], min(xs) + 1e-3)       # coordinates are rounded to 0.001 mm
        self.assertGreaterEqual(r["frame"]["hi"][0], max(xs) - 1e-3)

    def test_the_initial_frame_holds_the_wedge_and_probe(self):
        """Review of PR #39: a shallow single law framed the elements but clipped the wedge."""
        with open(FIXTURE) as f:
            base = json.load(f)["defaults"]
        c0 = dict(base, scan=dict(base["scan"], wave_type="Shear", param_val=5, start_angle=40, end_angle=40))
        r = call("calc", c0)
        lo, hi = np.array(r["frame"]["lo"]), np.array(r["frame"]["hi"])
        for p in r["setup"]:
            if p["role"] in ("wedge", "probe-body"):
                c = np.array(p["coords"])
                self.assertTrue(np.all(c >= lo - 1e-3) and np.all(c <= hi + 1e-3), p["role"])
                if "y0" in p["meta"]:
                    self.assertLessEqual(lo[1], p["meta"]["y0"] + 1e-3)
                    self.assertGreaterEqual(hi[1], p["meta"]["y1"] - 1e-3)

    def test_the_3d_view_frames_and_fills_as_the_desktop(self):
        """The 3D view's bounds, section plane and solids come from scene_model, as the desktop's:
        its bounds hold the desktop 3D tab's for any law, and the element readout gives the ray."""
        from scene_model import build_scene, scene_bounds, section_y
        r = call("calc", cfg(weld={"type": "Single-V", "centre_x_mm": 40, "bevel_deg": 30, "root_gap_mm": 2,
                                   "root_face_mm": 1.5}, view={"coverage_legs": 1}))
        v3 = r["view3d"]
        self.assertEqual([s["role"] for s in v3["solids"]], ["component", "wedge", "weld"])
        for s in v3["solids"]:
            self.assertEqual(len(s["tris"]), len(s["xz"]) - 2, s["role"])
        st = pac_web._state
        solver, c = st["solver"], st["calc"]
        lo, hi = np.array(v3["lo"]), np.array(v3["hi"])
        for i in (0, len(c.results) - 1):
            get = lambda k: (c.results[k]["interface_points"] * 1e3, np.asarray(c.focal_points[k]) * 1e3)  # noqa: E731
            sc = build_scene(solver, get, [i], current=i, sweep_focal_mm=np.asarray(c.focal_points) * 1e3)
            dlo, dhi = scene_bounds(sc, 25)
            self.assertTrue((lo <= dlo + 1e-3).all() and (hi >= dhi - 1e-3).all(), f"law {i}")
            self.assertAlmostEqual(v3["section_y"], section_y(sc))
        call("law", {"law": 2})
        e = call("element", {"index": 5, "law": 2})
        self.assertTrue(e["active"])
        np.testing.assert_allclose(e["interface"], c.results[2]["interface_points"][5] * 1e3, atol=1e-3)
        self.assertIsNone(call("element", {"index": 40, "law": 2})["interface"])      # outside the aperture

    def test_a_dragged_focus_is_solved_and_refused_above_the_surface(self):
        call("calc", cfg())
        r = call("custom", {"x": 30, "z": 18, "from_law": 1})
        self.assertTrue(r["custom"])
        np.testing.assert_allclose(r["focus"], [30, 0, 18], atol=1e-9)
        with self.assertRaises(ValueError):
            call("custom", {"x": 30, "z": -1, "from_law": 1})
        el = call("element", {"index": 3, "law": 1})
        self.assertEqual(el["number"], 4)
        self.assertTrue(el["active"])

    def test_exports_are_the_desktop_files(self):
        c0 = cfg()
        call("calc", c0)
        got = call("laws_csv")["text"]
        c = calculate(build_solver(c0["probe"], c0["wedge"], c0["material"], c0["sub_aperture"]), c0["scan"], "Linear")
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "laws.csv")
            write_laws_csv(p, c.results)
            want = open(p, encoding="utf-8").read()
        self.assertEqual(got, want)
        for fmt in ("csv", "m", "mat"):
            r = call("element_coords", {"format": fmt, "config": c0})
            self.assertTrue(r["name"].endswith("." + fmt))
            self.assertGreater(len(base64.b64decode(r["base64"])), 100)

    def test_the_field_is_the_desktop_field_job(self):
        c0 = cfg()
        call("calc", c0)
        r = call("field", {"law": 2, "custom": False, "values": FIELD})
        solver = build_solver(c0["probe"], c0["wedge"], c0["material"], c0["sub_aperture"])
        res = calculate(solver, c0["scan"], "Linear").results[2]
        job = field_job.run_job(field_job.make_job(solver, res, "Shear", 25, FIELD))
        np.testing.assert_allclose(np.array(r["sections"][0]["db"]), np.round(job["sections"][0]["db"], 2), atol=1e-9)
        self.assertIn("direct beam only", r["note"])
        three = call("field", {"law": 2, "custom": False, "values": dict(FIELD, model="3D", elevation_mm=4)})
        self.assertEqual([s["name"] for s in three["sections"]], ["X-Z", "Y-Z"])
        # in steps, as the page computes it (progress, Cancel): the same field
        fine = dict(FIELD, grid_mm=0.3)                     # several blocks of points
        whole = call("field", {"law": 2, "custom": False, "values": fine})
        st = call("field_start", {"law": 2, "custom": False, "values": fine})
        self.assertEqual(st["done"], 0)
        seen = []
        while True:
            st = call("field_step", {"seconds": 0.0})
            seen.append(st["done"])
            if st["finished"]:
                break
        self.assertGreater(len(seen), 1)
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(seen[-1], st["points"])
        self.assertEqual(st["result"]["sections"], whole["sections"])
        with self.assertRaises(ValueError):                # finished: nothing left to step
            call("field_step", {"seconds": 0.0})

    @unittest.skipUnless(os.path.isdir(BUILDFE_CATALOG), "no sibling buildFE checkout")
    def test_catalogue_entries_apply_as_on_the_desktop(self):
        data = open(os.path.join(BUILDFE_CATALOG, "probes.json"), "rb").read()
        call("put_file", {"name": "probes.json", "data": base64.b64encode(data).decode()})
        r = call("catalog_open", {"kind": "probe", "name": "probes.json"})
        self.assertIn("evident-2.25L64-A2", [e["id"] for e in r["entries"]])
        a = call("catalog_apply", {"kind": "probe", "id": "evident-2.25L64-A2"})
        self.assertEqual(a["values"]["num_elements"], 64)
        self.assertAlmostEqual(a["field"]["element_width_mm"], 0.55)
        refs = call("catalog_status", {"probe": a["values"], "wedge": {}})
        self.assertTrue(refs["probe"]["values_match"])


class TestBuild(unittest.TestCase):
    def test_the_build_empties_only_a_folder_it_built(self):
        """Review of PR #37: the build emptied whatever folder it was given."""
        import build_web
        for bad in (build_web.ROOT, os.path.dirname(build_web.ROOT), os.path.join(build_web.ROOT, "python"),
                    os.path.join(build_web.ROOT, "docs", "plans")):
            with self.assertRaises(SystemExit):
                build_web._check_destination(bad)
        with tempfile.TemporaryDirectory() as d:
            precious = os.path.join(d, "keep.txt")
            open(precious, "w").close()
            with self.assertRaises(SystemExit):
                build_web._check_destination(d)         # not empty, not a built site
            self.assertTrue(os.path.exists(precious))

    def test_the_build_label_comes_from_the_environment_or_git(self):
        import build_web
        old = os.environ.get("PAC_BUILD")
        try:
            os.environ["PAC_BUILD"] = "abc1234 2026-11-22"
            self.assertEqual(build_web.build_id(), "abc1234 2026-11-22")      # a Docker build (no .git)
            del os.environ["PAC_BUILD"]
            if os.path.exists(os.path.join(ROOT, ".git")):                          # a git checkout (not the Docker image)
                self.assertRegex(build_web.build_id(), r"^[0-9a-f]{7,} \d{4}-\d{2}-\d{2}")
            else:
                self.assertEqual(build_web.build_id(), "")
        finally:
            if old is not None:
                os.environ["PAC_BUILD"] = old

    def test_every_file_the_page_and_worker_load_is_shipped(self):
        import build_web
        worker = open(os.path.join(ROOT, "web", "worker.js"), encoding="utf-8").read()
        for f in [x.strip('" ') for x in worker.split("PY_FILES = [")[1].split("]")[0].replace("\n", "").split(",")]:
            if f != "pac_web.py":
                self.assertIn(f, build_web.PY, f)
        self.assertIn("materials.json", build_web.PY)
        page = open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8").read()
        for f in ("style.css", "views.js", "view3d.js", "app.js", "config.js", "vendor/plotly.min.js"):
            self.assertIn(f, page)
        for f in ("style.css", "views.js", "view3d.js", "app.js", "worker.js", "panels.json", "help.html", "web.config"):
            self.assertIn(f, build_web.WEB)
        self.assertIn(build_web.EZDXF_WHEEL, worker)


if __name__ == "__main__":
    unittest.main()
