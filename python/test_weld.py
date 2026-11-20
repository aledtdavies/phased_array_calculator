"""Weld templates, DXF cross-sections and fusion-face coverage (plan step 5b)."""
import math
import os
import random
import tempfile
import unittest

import numpy as np

import weld
from weld import (boundary_distance, dxf_profile, fusion_coverage, polygon_area, template_profile)

try:
    import ezdxf
except ImportError:          # pragma: no cover
    ezdxf = None

# Stated before the comparison was written (plan step 5b finish criterion): a template and a
# DXF of the same weld agree to 0.01 mm on the boundary (curves flattened to 0.002 mm both ways).
TOL_MM = 0.01
T = 25.0


def _corners(kind, g, r, a_deg, a2_deg=None, d=None):
    """Independent corner formulas (local x, z down) for the V preparations."""
    a = math.radians(a_deg)
    if kind == "single-V":
        w = g / 2 + (T - r) * math.tan(a)
        return [(-w, 0), (w, 0), (g / 2, T - r), (g / 2, T), (-g / 2, T), (-g / 2, T - r)]
    a2 = math.radians(a2_deg)
    z1, z2 = d - r / 2, d + r / 2
    wt, wb = g / 2 + z1 * math.tan(a), g / 2 + (T - z2) * math.tan(a2)
    return [(-wt, 0), (wt, 0), (g / 2, z1), (g / 2, z2), (wb, T), (-wb, T), (-g / 2, z2), (-g / 2, z1)]


def _write_dxf(path, segments, arcs=(), units=4, scale=1.0, layer="WELD", extra=()):
    """segments [(x0, y0, x1, y1)] and arcs [(cx, cy, r, a0_deg, a1_deg)] in CAD mm."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = units
    msp = doc.modelspace()
    items = [("L", s) for s in segments] + [("A", a) for a in arcs]
    random.Random(7).shuffle(items)          # CAD files hold entities in any order and sense
    for k, (t, v) in enumerate(items):
        if t == "L":
            x0, y0, x1, y1 = [c / scale for c in v]
            if k % 2:
                x0, y0, x1, y1 = x1, y1, x0, y0
            msp.add_line((x0, y0), (x1, y1), dxfattribs={"layer": layer})
        else:
            cx, cy, r, a0, a1 = v
            msp.add_arc((cx / scale, cy / scale), r / scale, a0, a1, dxfattribs={"layer": layer})
    for e in extra:
        e(msp)
    doc.saveas(path)


def _loop_segments(pts, datum="surface"):
    """Closed corner loop (x, z down) -> CAD line segments, y = -z or y = T - z."""
    y = (lambda z: -z) if datum == "surface" else (lambda z: T - z)
    out = []
    for (x0, z0), (x1, z1) in zip(pts, pts[1:] + pts[:1]):
        if (x0, z0) != (x1, z1):
            out.append((x0, y(z0), x1, y(z1)))
    return out


@unittest.skipIf(ezdxf is None, "ezdxf not installed")
class TemplateMatchesDXF(unittest.TestCase):
    """The plan's finish criterion: template and DXF of one weld give the same polygon."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def check(self, prof, dxf_path, **kw):
        d = dxf_profile(dxf_path, T, centre_x_mm=prof.centre_x_mm, **kw)
        self.assertLessEqual(boundary_distance(prof.polygon, d.polygon), TOL_MM)
        self.assertAlmostEqual(polygon_area(d.polygon), polygon_area(prof.polygon), delta=0.01)
        self.assertEqual([n for n, _ in d.faces], [n for n, _ in prof.faces])
        for (_, f1), (_, f2) in zip(prof.faces, d.faces):
            self.assertLessEqual(boundary_distance(f1, f2) if len(f1) > 2 else
                                 np.max(np.abs(f1[[0, -1]][np.argsort(f1[[0, -1], 1])] -
                                               f2[[0, -1]][np.argsort(f2[[0, -1], 1])])), TOL_MM)
        return d

    def test_single_v(self):
        for g, r, a in ((2.0, 1.5, 30.0), (0.0, 0.0, 30.0), (3.0, 2.0, 37.5)):
            for datum in ("surface", "backwall"):
                with self.subTest(g=g, r=r, a=a, datum=datum):
                    prof = template_profile("single-V", T, 40.0, bevel_deg=a, root_gap_mm=g, root_face_mm=r)
                    p = os.path.join(self.dir, f"v_{g}_{r}_{datum}.dxf")
                    _write_dxf(p, _loop_segments(_corners("single-V", g, r, a), datum))
                    self.check(prof, p, datum=datum)

    def test_double_v_in_inches(self):
        prof = template_profile("double-V", T, -5.0, bevel_deg=30, bevel2_deg=45, root_gap_mm=2,
                                root_face_mm=2, root_depth_mm=15)
        p = os.path.join(self.dir, "x.dxf")
        _write_dxf(p, _loop_segments(_corners("double-V", 2, 2, 30, 45, 15)), units=1, scale=25.4)
        self.check(prof, p)

    def test_single_j_with_an_arc_entity(self):
        g, r, R, b = 2.0, 1.5, 6.0, 10.0
        for side in ("near", "far"):
            with self.subTest(side=side):
                prof = template_profile("single-J", T, 30.0, bevel_deg=b, root_gap_mm=g, root_face_mm=r,
                                        root_radius_mm=R, side=side)
                te = math.radians(90 - b)
                cz = T - r - R
                ex, ez = -g / 2 - R * math.sin(te), cz + R * math.cos(te)
                tx = ex - ez * math.tan(math.radians(b))
                s = 1 if side == "near" else -1
                segs = [(s * g / 2, 0, s * g / 2, -T), (s * g / 2, -T, -s * g / 2, -T),
                        (-s * g / 2, -T, -s * g / 2, -(T - r)), (s * ex, -ez, s * tx, 0), (s * tx, 0, s * g / 2, 0)]
                # the J radius as a DXF ARC (CCW, degrees), centre above the root face top
                arc = ((-g / 2, -cz, R, 270 - math.degrees(te), 270.0) if side == "near"
                       else (g / 2, -cz, R, -90.0, -90 + math.degrees(te)))
                p = os.path.join(self.dir, f"j_{side}.dxf")
                _write_dxf(p, segs, [arc])
                self.check(prof, p)

    def test_large_radius_j_and_circle_vertices(self):
        """Review of PR #29: arcs are flattened from the exact curve, so large radii meet the tolerance."""
        g, r, R, b, TT = 2.0, 1.5, 100.0, 10.0, 400.0
        prof = template_profile("single-J", TT, 0.0, bevel_deg=b, root_gap_mm=g, root_face_mm=r, root_radius_mm=R)
        te = math.radians(90 - b)
        cz = TT - r - R
        ex, ez = -g / 2 - R * math.sin(te), cz + R * math.cos(te)
        tx = ex - ez * math.tan(math.radians(b))
        segs = [(g / 2, 0, g / 2, -TT), (g / 2, -TT, -g / 2, -TT), (-g / 2, -TT, -g / 2, -(TT - r)),
                (ex, -ez, tx, 0), (tx, 0, g / 2, 0)]
        p = os.path.join(self.dir, "bigj.dxf")
        _write_dxf(p, segs, [(-g / 2, -cz, R, 270 - math.degrees(te), 270.0)])
        d = dxf_profile(p, TT)
        self.assertLessEqual(boundary_distance(prof.polygon, d.polygon), TOL_MM)
        # every imported vertex of the radius lies on the analytic circle
        on_arc = np.abs(np.hypot(d.polygon[:, 0] + g / 2, d.polygon[:, 1] - cz) - R) < 1.0
        np.testing.assert_allclose(np.hypot(d.polygon[on_arc, 0] + g / 2, d.polygon[on_arc, 1] - cz), R, atol=1e-9)
        self.assertGreater(on_arc.sum(), 20)
        # a CIRCLE and a bulged LWPOLYLINE (a semicircle cap): vertices on the curve, chords within tolerance
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 4
        doc.modelspace().add_circle((0, -200), 100)
        p2 = os.path.join(self.dir, "circle.dxf")
        doc.saveas(p2)
        c = dxf_profile(p2, TT)
        rad = np.hypot(c.polygon[:, 0], c.polygon[:, 1] - 200)
        np.testing.assert_allclose(rad, 100, atol=1e-9)
        mids = 0.5 * (c.polygon + np.roll(c.polygon, -1, axis=0))
        self.assertLessEqual(100 - np.hypot(mids[:, 0], mids[:, 1] - 200).min(), weld.FLATTEN_MM + 1e-9)
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 4
        doc.modelspace().add_lwpolyline([(-50, 0, 0, 0, 0), (50, 0, 0, 0, -1.0)], format="xyseb", close=True)
        p3 = os.path.join(self.dir, "bulge.dxf")
        doc.saveas(p3)
        h = dxf_profile(p3, TT)
        self.assertAlmostEqual(polygon_area(h.polygon), math.pi * 50 ** 2 / 2, delta=0.5)
        below = h.polygon[h.polygon[:, 1] > 1e-9]
        np.testing.assert_allclose(np.hypot(below[:, 0], below[:, 1]), 50, atol=1e-9)

    def test_self_crossing_outline_is_refused(self):
        p = os.path.join(self.dir, "cross.dxf")
        pts = [(0, 0), (10, -20), (0, -20), (20, 0)]
        _write_dxf(p, [(*a, *b) for a, b in zip(pts, pts[1:] + pts[:1])])
        with self.assertRaisesRegex(ValueError, "crosses itself"):
            dxf_profile(p, T)

    def test_hand_written_r12_file(self):
        """An ASCII DXF written without ezdxf: LINE entities only, no header, mm assumed."""
        pts = _corners("single-V", 2.0, 1.5, 30.0)
        body = ["0", "SECTION", "2", "ENTITIES"]
        for x0, y0, x1, y1 in _loop_segments(pts):
            body += ["0", "LINE", "8", "0", "10", repr(x0), "20", repr(y0), "30", "0.0",
                     "11", repr(x1), "21", repr(y1), "31", "0.0"]
        body += ["0", "ENDSEC", "0", "EOF"]
        p = os.path.join(self.dir, "r12.dxf")
        with open(p, "w") as f:
            f.write("\n".join(body) + "\n")
        prof = template_profile("single-V", T, 0.0, bevel_deg=30, root_gap_mm=2, root_face_mm=1.5)
        d = self.check(prof, p)
        self.assertIn("unset", d.notes[0])

    def test_layer_choice_and_refusals(self):
        pts = _corners("single-V", 2.0, 1.5, 30.0)
        plate = lambda msp: msp.add_lwpolyline([(-60, 0), (60, 0), (60, -T), (-60, -T)], close=True,
                                               dxfattribs={"layer": "PLATE"})
        p = os.path.join(self.dir, "two.dxf")
        _write_dxf(p, _loop_segments(pts), extra=[plate])
        with self.assertRaisesRegex(ValueError, "2 closed outlines"):
            dxf_profile(p, T)
        self.check(template_profile("single-V", T, 0.0, bevel_deg=30, root_gap_mm=2, root_face_mm=1.5),
                   p, layer="WELD")
        with self.assertRaisesRegex(ValueError, "no layer 'NOPE'"):
            dxf_profile(p, T, layer="NOPE")
        p2 = os.path.join(self.dir, "open.dxf")
        _write_dxf(p2, _loop_segments(pts)[:-1])
        with self.assertRaisesRegex(ValueError, "not closed"):
            dxf_profile(p2, T)
        # drawn above y = 0 but read with the surface datum: outside the component
        p3 = os.path.join(self.dir, "up.dxf")
        _write_dxf(p3, _loop_segments(pts, "backwall"))
        with self.assertRaisesRegex(ValueError, "outside the component"):
            dxf_profile(p3, T, datum="surface")
        # units: a file stamped inches holding mm coordinates is refused, then read with an override
        p4 = os.path.join(self.dir, "stamped.dxf")
        _write_dxf(p4, _loop_segments(pts), units=1)
        with self.assertRaisesRegex(ValueError, "outside the component"):
            dxf_profile(p4, T)
        self.assertEqual(dxf_profile(p4, T, units="mm").notes[0], "units: mm")
        with self.assertRaisesRegex(ValueError, "not one of"):
            dxf_profile(p4, T, units="furlong")
        with self.assertRaisesRegex(ValueError, "cannot read"):
            dxf_profile(os.path.join(self.dir, "missing.dxf"), T)


class Templates(unittest.TestCase):
    def test_areas_and_faces(self):
        a = math.radians(30)
        p = template_profile("single-V", T, 0.0, bevel_deg=30, root_gap_mm=2, root_face_mm=1.5)
        w = 1 + 23.5 * math.tan(a)
        self.assertAlmostEqual(polygon_area(p.polygon), (2 * w + 2) / 2 * 23.5 + 2 * 1.5, places=9)
        self.assertEqual([n for n, _ in p.faces], ["Fusion face, -X side", "Fusion face, +X side"])
        for _, f in p.faces:      # each face runs from the surface to the backwall
            self.assertEqual(sorted([f[0, 1], f[-1, 1]]), [0.0, T])
        # a J: one curved face on the J plate, a straight square face on the other
        j = template_profile("single-J", T, 10.0, bevel_deg=10, root_gap_mm=2, root_face_mm=1.5, root_radius_mm=6)
        faces = dict(j.faces)
        self.assertEqual(len(faces["Fusion face, +X side"]), 2)
        np.testing.assert_allclose(faces["Fusion face, +X side"][:, 0], 11.0)
        self.assertGreater(len(faces["Fusion face, -X side"]), 10)

    def test_bevel_angle_is_from_the_vertical(self):
        p = template_profile("single-V", T, 0.0, bevel_deg=30)
        _, f = p.faces[0]
        d = f[-1] - f[0]
        self.assertAlmostEqual(math.degrees(math.atan2(abs(d[0]), abs(d[1]))), 30.0, places=9)

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, "root face"):
            template_profile("single-V", T, bevel_deg=30, root_face_mm=T)
        with self.assertRaisesRegex(ValueError, "Bevel angle"):
            template_profile("single-V", T, bevel_deg=90)
        with self.assertRaisesRegex(ValueError, "within the thickness"):
            template_profile("double-V", T, root_face_mm=4, root_depth_mm=1)
        with self.assertRaisesRegex(ValueError, "leave no bevel"):
            template_profile("single-J", T, root_face_mm=20, root_radius_mm=10)
        with self.assertRaisesRegex(ValueError, "unknown weld template"):
            template_profile("U", T)
        with self.assertRaisesRegex(ValueError, "Thickness"):
            template_profile("single-V", 0.0)


class _Cov:
    """A coverage.SweepCoverage stand-in: fans in metres."""
    def __init__(self, fans, legs):
        self.fans, self.legs = fans, legs


class FusionCoverage(unittest.TestCase):
    def test_a_fan_covering_part_of_a_face(self):
        p = template_profile("single-V", T, 0.0, bevel_deg=30)
        # leg-1 quad covering Z 5..15 mm across the whole width (X-Z; Y anything)
        q = np.array([[-50, 3, 5], [50, -3, 5], [50, 0, 15], [-50, 0, 15]]) * 1e-3
        fc = fusion_coverage(p, _Cov({1: [q], 2: []}, 2))
        L = 25 / math.cos(math.radians(30))
        self.assertAlmostEqual(fc.total_mm(), 2 * L, places=6)
        self.assertAlmostEqual(fc.covered_mm(), 2 * 10 / math.cos(math.radians(30)), delta=0.2)
        self.assertEqual(fc.covered_mm(2), 0.0)
        for f in fc.faces:
            runs = f.runs()
            self.assertEqual([c for _, c in runs], [False, True, False])
            z = runs[1][0][:, 1]
            np.testing.assert_allclose([z.min(), z.max()], [5, 15], atol=0.06)

    def test_a_real_sweep_reaches_more_with_skips(self):
        from coverage import SweepCoverage
        from session import build_solver, calculate
        pv = {"probe_type": "Linear", "num_elements": 32, "pitch_mm": 0.6, "freq_mhz": 5}
        wv = {"angle_deg": 36, "height_mm": 10, "velocity_ms": 2330, "offset_mm": 0}
        mv = {"vel_long_ms": 5920, "vel_shear_ms": 3240}
        sv = {"wave_type": "Shear", "focus_mode": "Constant Sound Path", "param_val": 40,
              "start_angle": 40, "end_angle": 70, "step_angle": 2}
        s = build_solver(pv, wv, mv, {"start_element": 1, "num_active_elements": 16})
        c = calculate(s, sv, "Linear")
        prof = template_profile("single-V", T, 45.0, bevel_deg=30, root_gap_mm=2, root_face_mm=1.5)
        got = []
        for legs in (1, 2):
            fc = fusion_coverage(prof, SweepCoverage(s, c.results, c.focal_points, T * 1e-3, legs, "shear"))
            got.append(fc.covered_mm())
            # every covered interval's midpoint lies inside one of the fan quads (X-Z)
            for f in fc.faces:
                mids = 0.5 * (f.points[:-1] + f.points[1:])
                quads = [np.asarray(q)[:, [0, 2]] * 1e3 for qs in fc_fans(s, c, legs) for q in qs]
                inside = np.zeros(len(mids), bool)
                for q in quads:
                    inside |= weld._inside(mids, q)
                np.testing.assert_array_equal(inside, f.covered)
        self.assertGreater(got[1], got[0])
        self.assertGreater(got[0], 0.0)

    def test_inside(self):
        sq = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
        np.testing.assert_array_equal(weld._inside(np.array([[0.5, 0.5], [1.5, 0.5], [0.5, -0.1]]), sq),
                                      [True, False, False])


def fc_fans(s, c, legs):
    from coverage import SweepCoverage
    return SweepCoverage(s, c.results, c.focal_points, T * 1e-3, legs, "shear").fans.values()


if __name__ == "__main__":
    unittest.main()
