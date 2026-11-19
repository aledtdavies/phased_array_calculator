"""Catalogue reading: buildFE 0.1 and nde-knowledge 1 formats, content hash, frame mapping."""
import json
import math
import os
import tempfile
import unittest

import numpy as np

from catalog import Catalog, CatalogError, buildfe_digest, wedge_outline
from delay_law import DelayLaw
from material import Material
from probe import create_probe_assembly
from wedge import Wedge

# Values and stamped hash of buildFE catalog/wedges.json entry "evident-SA2-N55S"
# (aledtdavies/buildFE master 4232624). The hash was computed by buildFE's MATLAB
# buildfe.asset.digest, so it is an independent check of the Python digest here.
SA2_STAMP = "17cd47f02522cfd59ecbd5d2a665c1bcb4261f1d468e246bb3cfef5b403268a6"
SRC = {"S": {"status": "datasheet", "document": "test"},
       "P": {"status": "provisional", "document": "test"}}


def v(value, source="S"):
    return {"value": value, "source": source}


SA2 = {"id": "sa2", "sha256": SA2_STAMP, "manufacturer": "Evident (Olympus)", "model": "SA2-N55S",
       "material": {"name": v("Rexolite"), "density": v(1049), "longitudinalSpeed": v(2337),
                    "shearSpeed": v(1157)},
       "outline": {"type": v("simple", "P"), "contactLength": v(0.069), "height": v(0.043),
                   "faceAngleDeg": v(36, "P"), "firstElement": v([0.004, 0.005], "P")},
       "nominal": {"refractedAngleDeg": v(55), "mode": v("shear")},
       "sources": SRC}
L64 = {"id": "l64", "manufacturer": "Evident (Olympus)", "model": "2.25L64-48X12-A2",
       "type": "linear-array",
       "parameters": {"nElements": v(64), "pitch": v(0.00075), "elementWidth": v(0.00055, "P"),
                      "elevation": v(0.012), "centreFrequency": v(2250000.0)},
       "sources": SRC}


class CatalogFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def write(self, name, data):
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path


class TestBuildfeFormat(CatalogFiles):
    def test_digest_matches_buildfe_stamp(self):
        c = Catalog(self.write("w.json", {"catalogVersion": "0.1", "wedges": [SA2]}))
        w = c.wedge("sa2")
        self.assertEqual(c.format, "buildfe-0.1")
        self.assertEqual(w.ref.sha256, SA2_STAMP)
        self.assertEqual(w.ref.stamp, "ok")

    def test_nominal_and_text_do_not_enter_the_hash_but_values_do(self):
        e = json.loads(json.dumps(SA2))
        e["id"], e["model"], e["nominal"]["refractedAngleDeg"]["value"] = "other", "x", 60
        e["sources"]["S"]["document"] = "new citation"
        c = Catalog(self.write("w.json", {"catalogVersion": "0.1", "wedges": [e]}))
        self.assertEqual(c.wedge("other").ref.stamp, "ok")
        e["material"]["longitudinalSpeed"]["value"] = 2330
        c = Catalog(self.write("w2.json", {"catalogVersion": "0.1", "wedges": [e]}))
        self.assertEqual(c.wedge("other").ref.stamp, "changed")
        del e["sha256"]
        c = Catalog(self.write("w3.json", {"catalogVersion": "0.1", "wedges": [e]}))
        self.assertEqual(c.wedge("other").ref.stamp, "unstamped")

    def test_polygon_digest_matches_buildfe(self):
        """A non-square vertex matrix: buildFE flattens numeric matrices column-major."""
        # Stamp computed by buildFE's MATLAB buildfe.array.catalogEntry + buildfe.asset.digest
        # (buildFE 376c414) for exactly this entry; its canonical outline is
        # {"faceEdge":[5,4],...,"vertices":[0,0.05,0.05,0.02,0,0,0,0.03,0.03,0.002]}.
        stamp = "6f2174fc617ab754c5cd303b37ae4dd56c4939d2a6ad6ca6559c0edc8a048eb5"
        e = {"id": "poly", "sha256": stamp, "manufacturer": "T", "model": "T",
             "material": {"name": v("Rexolite"), "density": v(1049), "longitudinalSpeed": v(2337),
                          "shearSpeed": v(1157)},
             "outline": {"type": v("polygon"),
                         "vertices": v([[0, 0], [0.05, 0], [0.05, 0.03], [0.02, 0.03], [0, 0.002]]),
                         "faceEdge": v([5, 4]), "firstElementAlong": v(0.01)},
             "sources": SRC}
        w = Catalog(self.write("w.json", {"catalogVersion": "0.1", "wedges": [e]})).wedge("poly")
        self.assertEqual(w.ref.sha256, stamp)
        self.assertEqual(w.ref.stamp, "ok")
        # A changed vertex is a different asset.
        e["outline"]["vertices"]["value"][3] = [0.021, 0.03]
        w = Catalog(self.write("w2.json", {"catalogVersion": "0.1", "wedges": [e]})).wedge("poly")
        self.assertEqual(w.ref.stamp, "changed")

    def test_canonical_follows_jsondecode_shapes(self):
        from catalog import _canonical
        self.assertEqual(_canonical([[1, 2, 3], [4, 5, 6]]), "[1,4,2,5,3,6]")  # column-major
        self.assertEqual(_canonical([0.5]), "0.5")                            # 1-element: scalar
        self.assertEqual(_canonical([[1, 2], [3]]), "[[1,2],3]")               # ragged: cell array
        self.assertEqual(_canonical(["a", "b"]), '["a","b"]')

    def test_canonical_form(self):
        self.assertEqual(buildfe_digest({"b": -0.0, "a": [1, 0.1]}, "probe"),
                         buildfe_digest({"a": [1.0, 0.1], "b": 0}, "probe"))

    def test_unsourced_value_is_refused(self):
        e = json.loads(json.dumps(L64))
        e["parameters"]["pitch"] = {"value": 0.00075, "source": "nowhere"}
        c = Catalog(self.write("p.json", {"catalogVersion": "0.1", "probes": [e]}))
        with self.assertRaises(CatalogError):
            c.probe("l64")

    def test_probe_values_and_provisional_note(self):
        p = Catalog(self.write("p.json", {"catalogVersion": "0.1", "probes": [L64]})).probe("l64")
        self.assertEqual((p.probe_type, p.num_elements, p.pitch, p.frequency),
                         ("Linear", 64, 0.00075, 2250000.0))
        self.assertEqual(p.panel_values()["pitch_mm"], 0.75)
        self.assertTrue(any("elementWidth" in n for n in p.notes))
        self.assertEqual(p.ref.stamp, "unstamped")

    def test_wedge_maps_onto_the_calculator_frame(self):
        """Element 1 at the catalogue seat, elements up the face, the beam towards +x."""
        w = Catalog(self.write("w.json", {"catalogVersion": "0.1", "wedges": [SA2]})).wedge("sa2")
        self.assertEqual((w.angle_deg, w.probe_offset_x, w.height_at_element1, w.velocity),
                         (36, 0.004, 0.005, 2337))
        wedge = Wedge(w.angle_deg, w.height_at_element1, w.velocity, w.probe_offset_x)
        probe = create_probe_assembly("Linear", 16, 0.0006, 5e6)
        el = wedge.get_transformed_elements(probe)
        np.testing.assert_allclose(el[0], [0.004, 0, -0.005], atol=1e-15)
        # Every element lies on the catalogue probe face (global Z = -y), rising towards +x.
        toe = w.outline[-1][1]
        np.testing.assert_allclose(-el[:, 2], toe + el[:, 0] * math.tan(math.radians(36)), atol=1e-12)
        self.assertTrue(np.all(np.diff(el[:, 0]) > 0) and np.all(np.diff(el[:, 2]) < 0))
        # A forward focus is reached through interface points ahead (+x) of each element.
        law = DelayLaw(probe, wedge, Material(5920, 3240))
        cx, _, cz = law.aperture_centre()
        pts = law.calculate_law(cx + 0.05, 0, 0.05)['interface_points']
        self.assertTrue(np.all(pts[:, 0] > el[:, 0]))
        # Outline: closed, anticlockwise, base on y = 0 from 0 to the contact length.
        V = w.outline
        area = 0.5 * sum(V[k][0] * V[(k + 1) % len(V)][1] - V[(k + 1) % len(V)][0] * V[k][1]
                         for k in range(len(V)))
        self.assertGreater(area, 0)   # anticlockwise in the wedge frame (y up)
        self.assertEqual(V[:2], [(0.0, 0.0), (0.069, 0.0)])
        self.assertEqual(w.outline_global_mm()[2], (69.0, -43.0))

    def test_simple_outline_that_misses_element_1_is_refused(self):
        with self.assertRaises(CatalogError):
            wedge_outline({"type": "simple", "contactLength": 0.02, "height": 0.043,
                           "faceAngleDeg": 36, "firstElement": [0.004, 0.005]})

    def test_polygon_outline(self):
        g = wedge_outline({"type": "polygon",
                           "vertices": [[0, 0], [0.05, 0], [0.05, 0.03], [0, 0.002]],
                           "faceEdge": [4, 3], "firstElementAlong": 0.01})
        a = math.atan2(0.028, 0.05)
        self.assertAlmostEqual(g["angle_deg"], math.degrees(a))
        np.testing.assert_allclose(g["first_element"], [0.01 * math.cos(a), 0.002 + 0.01 * math.sin(a)])
        with self.assertRaises(CatalogError):   # face descending towards +x: not this frame
            wedge_outline({"type": "polygon",
                           "vertices": [[0, 0], [0.05, 0], [0.05, 0.002], [0, 0.03]],
                           "faceEdge": [3, 4], "firstElementAlong": 0.01})


class TestNdeKnowledgeFormat(CatalogFiles):
    def catalog(self):
        probes = [
            {"id": "lin", "manufacturer": "M", "model": "x", "type": "linear-array",
             "nElements": 16, "activeAperture": 0.0448, "centreFrequency": 5e5},
            {"id": "mat", "manufacturer": "M", "model": "y", "type": "dual-matrix-array",
             "nElements": 7, "nElementsSecondary": 4, "activeAperture": 0.0189,
             "activeApertureSecondary": 0.012, "centreFrequency": 1.5e6},
            {"id": "odd", "manufacturer": "M", "model": "z", "type": "linear-array",
             "nElements": 64, "pitch": 0.00075, "activeAperture": 0.0384, "centreFrequency": 2.25e6,
             "sourceInconsistency": "pitch values appear swapped"},
            {"id": "ut", "manufacturer": "M", "model": "w", "type": "single-element"},
        ]
        wedges = [{"id": "w1", "manufacturer": "M", "model": "w1", "wedgeAngleDeg": 22.0,
                   "curvature": "AOD 1.0 in."}]
        return Catalog(self.write("p.json", {"catalogVersion": "1", "probes": probes,
                                             "wedges": wedges}))

    def test_format_and_derived_pitch(self):
        c = self.catalog()
        self.assertEqual(c.format, "nde-knowledge-1")
        p = c.probe("lin")
        self.assertAlmostEqual(p.pitch, 0.0028)
        self.assertTrue(any("derived" in n for n in p.notes))
        self.assertIsNone(p.ref.sha256)
        self.assertEqual(len(p.ref.file_sha256), 64)

    def test_dual_matrix_needs_separation(self):
        p = self.catalog().probe("mat")
        self.assertEqual((p.probe_type, p.num_elements, p.num_elements_y), ("Dual Matrix", 7, 4))
        self.assertAlmostEqual(p.pitch_y, 0.003)
        self.assertTrue(any("separation" in m for m in p.missing))

    def test_invalid_element_counts_are_refused(self):
        base = {"manufacturer": "M", "model": "m", "centreFrequency": 1e6, "nElements": 8,
                "activeAperture": 0.008, "activeApertureSecondary": 0.004}
        probes, bad = [], []
        for k, (ptype, field, value) in enumerate(
                [(t, "nElementsSecondary", v) for t in ("matrix-array", "dual-matrix-array")
                 for v in (2.5, 0, -1, None, True)] +
                [("linear-array", "nElements", v) for v in (2.5, 0, None, True)]):
            e = dict(base, id=f"bad{k}", type=ptype)
            e["nElementsSecondary"] = 4
            e[field] = value
            probes.append(e)
            bad.append(e["id"])
        probes.append(dict(base, id="good", type="matrix-array", nElementsSecondary=4))
        c = Catalog(self.write("bad.json", {"catalogVersion": "1", "probes": probes}))
        for id_ in bad:
            with self.assertRaises(CatalogError, msg=id_):
                c.probe(id_)
        rows = {r[0]: r[4] for r in c.summary("probe")}
        self.assertFalse(any(rows[i] for i in bad))
        self.assertTrue(rows["good"])
        self.assertEqual(c.probe("good").num_elements_y, 4)

    def test_inconsistency_is_reported_not_corrected(self):
        p = self.catalog().probe("odd")
        self.assertEqual(p.pitch, 0.00075)
        self.assertTrue(any("swapped" in n for n in p.notes))
        self.assertTrue(any("differs" in n for n in p.notes))

    def test_unsupported_types_are_refused_and_listed(self):
        c = self.catalog()
        with self.assertRaises(CatalogError):
            c.probe("ut")
        rows = {r[0]: r for r in c.summary("probe")}
        self.assertFalse(rows["ut"][4])
        self.assertTrue(rows["lin"][4])

    def test_wedge_without_seat_lists_what_is_missing(self):
        w = self.catalog().wedge("w1")
        self.assertEqual(w.panel_values(), {"angle_deg": 22.0})
        self.assertIn("height at element 1", w.missing)
        self.assertTrue(any("curved" in n for n in w.notes))


class TestLiveBuildfeCatalogue(unittest.TestCase):
    """Every entry of a sibling buildFE checkout's catalogue verifies (skipped when absent)."""

    def test_sibling_catalogue_stamps(self):
        here = os.path.dirname(os.path.abspath(__file__))
        d = os.path.normpath(os.path.join(here, "..", "..", "buildFE", "catalog"))
        if not os.path.isdir(d):
            self.skipTest("no sibling buildFE checkout")
        for name, kind in (("probes.json", "probe"), ("wedges.json", "wedge")):
            c = Catalog(os.path.join(d, name))
            for e in c.entries(kind):
                asset = c.probe(e["id"]) if kind == "probe" else c.wedge(e["id"])
                self.assertEqual(asset.ref.stamp, "ok", e["id"])


if __name__ == "__main__":
    unittest.main()
