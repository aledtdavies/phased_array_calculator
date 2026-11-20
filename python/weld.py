"""
Weld geometry (plan step 5b): weld-preparation templates and DXF cross-sections, read into one
profile, and the coverage of its fusion faces by a sweep's coverage fans.

Frame and units: the calculator's global frame in millimetres. The weld runs along Y (across
the probe), so its cross-section lies in the X-Z plane: X along the wedge, Z down into the
component, Z = 0 the scanning surface and Z = T the backwall. A profile is the closed outline
of the weld region (the fusion boundary of the preparation) at the weld's centre X.

Templates (flush cap and root: no reinforcement is modelled):
  single-V   bevel angle a (from the vertical, each side), root gap g, root face r:
             bevels from the surface down to Z = T - r, then root faces to the backwall.
  double-V   upper bevel a, lower bevel a2, root gap g, root face r centred at depth d
             (0: mid-thickness).
  single-J   a J on one plate (side 'near' = the -X plate, 'far' = the +X plate), the other
             plate square: root face r from the backwall, a root radius R starting at the root
             face's top with a horizontal tangent, then a straight bevel at angle a from the
             vertical to the surface (the ISO 9692-1 single-J shape), root gap g.

DXF (read with ezdxf): the closed outline of the weld region, drawn in CAD axes with x across
the weld (x = 0 the weld centreline) and y up. The datum says where y = 0 is: 'surface' (the
scanning surface, the part drawn below it, Z = -y) or 'backwall' (the part drawn above it,
Z = T - y). LINE, ARC, LWPOLYLINE (bulges included), POLYLINE, SPLINE, ELLIPSE and CIRCLE are
read; curves are flattened to within FLATTEN_MM. Units follow $INSUNITS (unset: millimetres)
unless given: files are often stamped with units their coordinates are not in.

Fusion faces are the boundary chains of the profile that lie on neither the surface nor the
backwall, split at vertices that do, so a template and a DXF of one weld give the same faces.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import numpy as np

FLATTEN_MM = 0.002        # largest chord deviation when an arc or curve is flattened
WALL_TOL_MM = 1e-6        # a vertex this close to Z = 0 or Z = T lies on that wall
JOIN_TOL_MM = 1e-3        # DXF entity ends this close together are joined
SAMPLE_MM = 0.05          # fusion faces are tested for coverage at this spacing
TEMPLATES = ("single-V", "double-V", "single-J")

_INSUNITS_MM = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 14: 100.0}
_INSUNITS_NAME = {0: "unset (read as mm)", 1: "inches", 2: "feet", 4: "mm", 5: "cm", 6: "m", 14: "dm"}
DXF_UNITS = {"mm": 4, "cm": 5, "m": 6, "inch": 1, "ft": 2}     # names for an override


@dataclass
class WeldProfile:
    polygon: np.ndarray            # (N, 2) X-Z, mm, closed implicitly (no repeated end point)
    faces: list                    # [(name, (M, 2) polyline), ...] the fusion faces
    source: str                    # what it was made from, for labels
    thickness_mm: float
    centre_x_mm: float
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Outline handling shared by templates and DXF
def _clean(poly):
    """Drop repeated consecutive vertices and a repeated closing vertex."""
    p = np.asarray(poly, dtype=float)
    keep = [0]
    for i in range(1, len(p)):
        if np.hypot(*(p[i] - p[keep[-1]])) > 1e-9:
            keep.append(i)
    p = p[keep]
    if len(p) > 1 and np.hypot(*(p[0] - p[-1])) <= 1e-9:
        p = p[:-1]
    return p


def polygon_area(poly):
    x, z = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))


def fusion_faces(poly, thickness_mm, centre_x_mm=0.0):
    """
    The fusion faces of a closed X-Z outline: chains of edges not lying on Z = 0 or Z = T,
    split at every vertex on either wall. Named by the side of the centreline they lie on.
    """
    n = len(poly)
    on_wall = (np.abs(poly[:, 1]) <= WALL_TOL_MM) | (np.abs(poly[:, 1] - thickness_mm) <= WALL_TOL_MM)

    def wall_edge(i):
        a, b = poly[i], poly[(i + 1) % n]
        return (abs(a[1]) <= WALL_TOL_MM and abs(b[1]) <= WALL_TOL_MM) or \
            (abs(a[1] - thickness_mm) <= WALL_TOL_MM and abs(b[1] - thickness_mm) <= WALL_TOL_MM)

    if not on_wall.any():                         # an outline clear of both walls: one face
        chains = [list(range(n)) + [0]]
    else:
        start = int(np.flatnonzero(on_wall)[0])
        order = [(start + k) % n for k in range(n + 1)]   # walk once round from a wall vertex
        chains, cur = [], None
        for a, b in zip(order[:-1], order[1:]):
            if wall_edge(a):
                cur = None
                continue
            if cur is None:
                cur = [a]
                chains.append(cur)
            cur.append(b)
            if on_wall[b]:
                cur = None
    faces = []
    chains.sort(key=lambda c: (float(np.mean(poly[c][:, 0])), float(np.mean(poly[c][:, 1]))))  # -X first
    for c in chains:
        pts = poly[c]
        mx = float(np.mean(pts[:, 0])) - centre_x_mm
        side = "-X side" if mx < -1e-9 else ("+X side" if mx > 1e-9 else "centre")
        faces.append([side, pts])
    names = [f[0] for f in faces]
    seen = {}
    out = []
    for name, pts in faces:                      # number repeated names
        if names.count(name) > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name} {seen[name]}"
        out.append((f"Fusion face, {name}", pts))
    return out


def _profile(poly, thickness_mm, centre_x_mm, source, notes=()):
    poly = _clean(poly)
    if len(poly) < 3 or abs(polygon_area(poly)) < 1e-9:
        raise ValueError("the weld outline encloses no area")
    if polygon_area(poly) < 0:                   # one orientation for every profile
        poly = poly[::-1]
    return WeldProfile(poly, fusion_faces(poly, thickness_mm, centre_x_mm), source,
                       float(thickness_mm), float(centre_x_mm), list(notes))


def _arc_points(centre, radius, a0, a1, tol=FLATTEN_MM):
    """Points on an arc from angle a0 to a1 (radians), chord deviation <= tol."""
    span = abs(a1 - a0)
    step = 2.0 * math.acos(max(-1.0, 1.0 - tol / radius)) if radius > tol else span
    n = max(1, int(math.ceil(span / max(step, 1e-9))))
    t = np.linspace(a0, a1, n + 1)
    return np.c_[centre[0] + radius * np.cos(t), centre[1] + radius * np.sin(t)]


# ---------------------------------------------------------------------------
# Templates
def _positive(name, v, allow_zero=True):
    v = float(v)
    if not math.isfinite(v) or v < 0 or (v == 0 and not allow_zero):
        raise ValueError(f"{name} must be {'>= 0' if allow_zero else '> 0'} (got {v:g})")
    return v


def _angle(name, a):
    a = float(a)
    if not (0.0 <= a < 89.0):
        raise ValueError(f"{name} must be from 0 to 89 degrees (got {a:g})")
    return math.radians(a)


def template_outline(kind, thickness_mm, *, bevel_deg=30.0, root_gap_mm=0.0, root_face_mm=0.0,
                     bevel2_deg=None, root_depth_mm=0.0, root_radius_mm=6.0, side="near"):
    """The local outline (x about the centreline, z down), (N, 2) mm, of a template preparation."""
    T = _positive("Thickness", thickness_mm, allow_zero=False)
    g = _positive("Root gap", root_gap_mm)
    r = _positive("Root face", root_face_mm)
    a = _angle("Bevel angle", bevel_deg)
    if kind == "single-V":
        if r >= T:
            raise ValueError(f"the root face ({r:g} mm) must be less than the thickness ({T:g} mm)")
        w = g / 2 + (T - r) * math.tan(a)
        return np.array([(-w, 0.0), (w, 0.0), (g / 2, T - r), (g / 2, T), (-g / 2, T), (-g / 2, T - r)])
    if kind == "double-V":
        a2 = _angle("Lower bevel angle", bevel_deg if bevel2_deg is None else bevel2_deg)
        d = _positive("Root depth", root_depth_mm) or T / 2
        z1, z2 = d - r / 2, d + r / 2
        if z1 < 0 or z2 > T:
            raise ValueError(f"the root face ({r:g} mm at depth {d:g} mm) must lie within the thickness ({T:g} mm)")
        wt, wb = g / 2 + z1 * math.tan(a), g / 2 + (T - z2) * math.tan(a2)
        return np.array([(-wt, 0.0), (wt, 0.0), (g / 2, z1), (g / 2, z2), (wb, T), (-wb, T),
                         (-g / 2, z2), (-g / 2, z1)])
    if kind == "single-J":
        R = _positive("Root radius", root_radius_mm, allow_zero=False)
        if side not in ("near", "far"):
            raise ValueError("the J side is 'near' (the -X plate) or 'far' (the +X plate)")
        cz = T - r - R                        # the radius's centre, above the root face top
        te = math.pi / 2 - a                  # arc turn from horizontal to the bevel
        ex, ez = -g / 2 - R * math.sin(te), cz + R * math.cos(te)
        if r >= T or ez <= 0:
            raise ValueError(f"the root face ({r:g} mm) and radius ({R:g} mm) leave no bevel "
                             f"in {T:g} mm")
        # The arc in angle about (x0, cz) with z down: point = c + R(-sin t, cos t), t 0 -> te.
        arc = _arc_points((0.0, 0.0), R, math.pi / 2, math.pi / 2 + te)   # (cos, sin) = (-sin t, cos t)
        arc = np.c_[-g / 2 + arc[:, 0], cz + arc[:, 1]]
        top = (ex - ez * math.tan(a), 0.0)
        out = np.vstack([[(g / 2, 0.0), (g / 2, T), (-g / 2, T)], arc, [top]])
        if side == "far":
            out[:, 0] *= -1
        return out
    raise ValueError(f"unknown weld template {kind!r} (one of {', '.join(TEMPLATES)})")


def template_profile(kind, thickness_mm, centre_x_mm=0.0, **params):
    local = template_outline(kind, thickness_mm, **params)
    desc = ", ".join(f"{k.replace('_mm', '').replace('_deg', '')} {v:g}" for k, v in sorted(params.items())
                     if isinstance(v, (int, float)))
    return _profile(local + [centre_x_mm, 0.0], thickness_mm, centre_x_mm,
                    f"{kind} template" + (f" ({desc})" if desc else ""))


# ---------------------------------------------------------------------------
# DXF
def _dxf_pieces(path, layer, units=None):
    try:
        import ezdxf
        from ezdxf import path as ezpath
    except ImportError as e:      # pragma: no cover - a dependency of the window
        raise ValueError("reading DXF needs the ezdxf package (pip install ezdxf)") from e
    try:
        doc = ezdxf.readfile(path)
    except (OSError, ezdxf.DXFError) as e:
        raise ValueError(f"cannot read {os.path.basename(path)}: {e}") from None
    # R12 and older files have no $INSUNITS (ezdxf then reports its own default): unset.
    if units is not None:
        if units not in DXF_UNITS:
            raise ValueError(f"DXF units {units!r} are not one of {', '.join(DXF_UNITS)}")
        units = DXF_UNITS[units]
    elif doc.dxfversion <= "AC1009" or "$INSUNITS" not in doc.header:
        units = 0
    else:
        units = int(doc.header["$INSUNITS"] or 0)
    if units not in _INSUNITS_MM:
        raise ValueError(f"{os.path.basename(path)}: drawing units code {units} is not supported "
                         "(use mm, cm, m, inches or feet)")
    scale = _INSUNITS_MM[units]
    types = ("LINE", "ARC", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE", "CIRCLE")
    pieces, layers = [], set()
    for e in doc.modelspace():
        if e.dxftype() not in types:
            continue
        lay = e.dxf.get("layer", "0")
        layers.add(lay)
        if layer is not None and lay != layer:
            continue
        p = ezpath.make_path(e)
        pts = np.array([(v.x, v.y) for v in p.flattening(FLATTEN_MM / scale)], dtype=float) * scale
        if len(pts) >= 2:
            pieces.append((lay, pts))
    return pieces, sorted(layers), units, scale


def _chain(pieces, tol=JOIN_TOL_MM):
    """Join polylines end to end into closed loops; returns (loops, open chains)."""
    todo = [p for p in pieces]
    loops, open_ = [], []
    while todo:
        cur = todo.pop(0)
        grown = True
        while grown and np.hypot(*(cur[0] - cur[-1])) > tol:
            grown = False
            for i, q in enumerate(todo):
                if np.hypot(*(cur[-1] - q[0])) <= tol:
                    cur = np.vstack([cur, q[1:]])
                elif np.hypot(*(cur[-1] - q[-1])) <= tol:
                    cur = np.vstack([cur, q[::-1][1:]])
                elif np.hypot(*(cur[0] - q[-1])) <= tol:
                    cur = np.vstack([q[:-1], cur])
                elif np.hypot(*(cur[0] - q[0])) <= tol:
                    cur = np.vstack([q[::-1][:-1], cur])
                else:
                    continue
                todo.pop(i)
                grown = True
                break
        (loops if np.hypot(*(cur[0] - cur[-1])) <= tol and len(cur) > 3 else open_).append(cur)
    return loops, open_


def dxf_profile(path, thickness_mm, centre_x_mm=0.0, datum="surface", layer=None, units=None):
    """
    A weld profile from the closed outline in a DXF cross-section (see the module notes).
    units: None to follow the file's $INSUNITS, or one of DXF_UNITS to override it.
    """
    T = _positive("Thickness", thickness_mm, allow_zero=False)
    if datum not in ("surface", "backwall"):
        raise ValueError("the DXF datum is 'surface' or 'backwall'")
    name = os.path.basename(path)
    pieces, layers, units, scale = _dxf_pieces(path, layer, units)
    if layer is not None and layer not in layers:
        raise ValueError(f"{name} has no layer {layer!r} with outline entities "
                         f"(layers: {', '.join(layers) or 'none'})")
    loops, open_ = _chain([p for _, p in pieces])
    if not loops:
        if open_:
            ends = open_[0][[0, -1]]
            raise ValueError(f"{name}: the outline is not closed (an end at x {ends[0, 0]:.3f}, "
                             f"y {ends[0, 1]:.3f} mm meets nothing within {JOIN_TOL_MM} mm)")
        raise ValueError(f"{name} has no outline entities" + (f" on layer {layer!r}" if layer else ""))
    if len(loops) > 1:
        raise ValueError(f"{name} has {len(loops)} closed outlines" +
                         (f" on layer {layer!r}" if layer else "") +
                         f"; put the weld region alone on one layer and name it (layers: {', '.join(layers)})")
    xy = loops[0]
    z = -xy[:, 1] if datum == "surface" else T - xy[:, 1]
    poly = np.c_[xy[:, 0] + centre_x_mm, z]
    zmin, zmax = float(poly[:, 1].min()), float(poly[:, 1].max())
    if zmin < -JOIN_TOL_MM or zmax > T + JOIN_TOL_MM:
        raise ValueError(f"{name}: the outline spans Z {zmin:.3f} to {zmax:.3f} mm, outside the "
                         f"component (0 to {T:g} mm); check the datum ({datum}) and the units "
                         f"({_INSUNITS_NAME[units]}; set them if the file's are wrong)")
    # Vertices within the join tolerance of a wall are put on it, so fusion faces split there.
    poly[np.abs(poly[:, 1]) <= JOIN_TOL_MM, 1] = 0.0
    poly[np.abs(poly[:, 1] - T) <= JOIN_TOL_MM, 1] = T
    notes = [f"units: {_INSUNITS_NAME[units]}"]
    if open_:
        notes.append(f"{len(open_)} open entity chain(s) not part of the outline were ignored")
    return _profile(poly, T, centre_x_mm, f"DXF {name}" + (f" (layer {layer})" if layer else ""), notes)


# ---------------------------------------------------------------------------
# Comparison
def _densify(poly, step=0.01, closed=True):
    pts = np.vstack([poly, poly[:1]]) if closed else poly
    out = [pts[:1]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(np.hypot(*(b - a)) / step)))
        out.append(a + (b - a) * (np.arange(1, n + 1)[:, None] / n))
    return np.vstack(out)


def _point_to_segments(p, a, b):
    """Distance from each point p (N, 2) to the nearest of segments a -> b (M, 2)."""
    ab = b - a
    L2 = np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-30)
    t = np.clip(np.einsum("nmj,mj->nm", p[:, None, :] - a[None], ab) / L2, 0.0, 1.0)
    proj = a[None] + t[..., None] * ab[None]
    return np.min(np.linalg.norm(p[:, None, :] - proj, axis=2), axis=1)


def boundary_distance(p, q):
    """The symmetric Hausdorff distance (mm) between two closed outlines' boundaries."""
    def one_way(u, v):
        vc = np.vstack([v, v[:1]])
        return float(np.max(_point_to_segments(_densify(u), vc[:-1], vc[1:])))
    return max(one_way(p, q), one_way(q, p))


# ---------------------------------------------------------------------------
# Fusion-face coverage
def _inside(pts, poly):
    """Even-odd point-in-polygon test, (N,) bool, for points (N, 2) and polygon (K, 2)."""
    x, z = pts[:, 0][:, None], pts[:, 1][:, None]
    ax, az = poly[:, 0][None], poly[:, 1][None]
    bx, bz = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    cross = (az > z) != (bz > z)
    with np.errstate(divide="ignore", invalid="ignore"):
        xi = ax + (z - az) * (bx - ax) / (bz - az)
    return np.count_nonzero(cross & (x < xi), axis=1) % 2 == 1


@dataclass
class FaceCoverage:
    name: str
    points: np.ndarray        # (N + 1, 2) mm: the face sampled along its length
    legs: np.ndarray          # (N, L) bool: interval k (points k..k+1) covered by leg l + 1

    @property
    def covered(self):
        return self.legs.any(axis=1)

    def lengths(self):
        return np.hypot(*np.diff(self.points, axis=0).T)

    def runs(self):
        """[(polyline (k, 2), covered), ...]: the face split into covered and uncovered runs."""
        c = self.covered
        out, start = [], 0
        for k in range(1, len(c) + 1):
            if k == len(c) or c[k] != c[start]:
                out.append((self.points[start:k + 1], bool(c[start])))
                start = k
        return out


@dataclass
class FusionCoverage:
    faces: list               # [FaceCoverage, ...]
    legs: int

    def total_mm(self):
        return float(sum(f.lengths().sum() for f in self.faces))

    def covered_mm(self, leg=None):
        tot = 0.0
        for f in self.faces:
            c = f.covered if leg is None else f.legs[:, leg - 1]
            tot += float(f.lengths()[c].sum())
        return tot

    def summary(self):
        tot = self.total_mm()
        if tot <= 0:
            return "Fusion faces: none"
        cov = self.covered_mm()
        return (f"Fusion faces {100 * cov / tot:.0f} % covered, gaps {tot - cov:.1f} mm of {tot:.1f} mm")


def _sample(poly, step):
    pts = [poly[:1]]
    for a, b in zip(poly[:-1], poly[1:]):
        n = max(1, int(math.ceil(np.hypot(*(b - a)) / step)))
        pts.append(a + (b - a) * (np.arange(1, n + 1)[:, None] / n))
    return np.vstack(pts)


def fusion_coverage(profile, cov, step_mm=SAMPLE_MM):
    """
    Which parts of each fusion face the sweep's coverage fans reach, leg by leg. The weld runs
    along Y, so a fan quad (metres, 3D) covers a face point when the quad's X-Z projection
    contains it: a central ray crossing the face's X-Z trace meets the extruded face at some Y.
    Each face is tested at interval midpoints step_mm apart; cov is a coverage.SweepCoverage.
    """
    quads = {leg: [np.asarray(q)[:, [0, 2]] * 1e3 for q in qs] for leg, qs in cov.fans.items()}
    out = []
    for name, face in profile.faces:
        pts = _sample(face, step_mm)
        mids = 0.5 * (pts[:-1] + pts[1:])
        legs = np.zeros((len(mids), cov.legs), dtype=bool)
        for leg, qs in quads.items():
            for q in qs:
                legs[:, leg - 1] |= _inside(mids, q)
        out.append(FaceCoverage(name, pts, legs))
    return FusionCoverage(out, cov.legs)
