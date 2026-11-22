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
read; curves are flattened from the exact curve (vertices on it) to within FLATTEN_MM, and
polylines are split into their lines and arcs first. A self-crossing outline is refused. Units follow $INSUNITS (unset: millimetres)
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
PLANAR_TOL_MM = 1e-6      # DXF outline points must share one Z (the drawing plane) to this
SAMPLE_MM = 0.05          # fusion faces are tested for coverage at this spacing
EDGE_TOL_MM = 1e-6        # a face point this close to a fan's edge is inside the fan
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
GEOM_TOL_MM = 1e-7        # outline vertices and edges closer than this coincide


def _clean(poly, tol=GEOM_TOL_MM):
    """
    The outline without degenerate vertices, repeated until none is left: repeats, vertices on
    the straight line through their neighbours (a straight run split in two, or a zero-width
    spike that doubles back, as a closed root leaves), and a repeated closing vertex.
    """
    p = [tuple(v) for v in np.asarray(poly, dtype=float)]
    changed = True
    while changed and len(p) >= 3:
        changed = False
        n = len(p)
        for k in range(n):
            a, m, c = np.array(p[k - 1]), np.array(p[k]), np.array(p[(k + 1) % n])
            ac = c - a
            L = float(np.hypot(*ac))
            if np.hypot(*(m - a)) <= tol:
                drop = True
            elif L <= tol:                      # neighbours coincide: m is a spike's tip
                drop = True
            else:
                drop = abs(_cross2(ac, m - a)) / L <= tol
            if drop:
                del p[k]
                changed = True
                break
    return np.array(p, dtype=float)


def _cross2(u, v):
    return float(u[0] * v[1] - u[1] * v[0])


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


def _angle_of(v):
    return math.atan2(v[1], v[0]) % (2 * math.pi)


def _passes_cross(p, a1, a2, b1, b2):
    """Two boundary passes through point p (each from a neighbour to a neighbour) cross there."""
    t1, t2 = _angle_of(a1 - p), _angle_of(a2 - p)
    sweep = (t2 - t1) % (2 * math.pi)
    inside = [0 < (_angle_of(q - p) - t1) % (2 * math.pi) < sweep for q in (b1, b2)]
    return inside[0] != inside[1]


def split_lobes(poly, tol=GEOM_TOL_MM):
    """
    A simple outline that touches itself at points (a pinch: a closed-root double-V's two Vs)
    as its separate lobes, each a simple polygon; an outline without a pinch as [itself].
    """
    n = len(poly)
    for i in range(n):
        for j in range(i + 2, n):
            if np.hypot(*(poly[i] - poly[j])) <= tol:
                return split_lobes(poly[i:j], tol) + split_lobes(np.vstack([poly[j:], poly[:i]]), tol)
    return [poly]


def outline_fault(poly, tol=GEOM_TOL_MM):
    """
    Why a closed outline (cleaned, see _clean) is not a simple polygon, or None: two edges
    crossing, a crossing through a vertex, or edges overlapping. Two lobes touching at one point
    without crossing (a pinch) are allowed.
    """
    n = len(poly)
    nxt = lambda k: poly[(k + 1) % n]
    prv = lambda k: poly[k - 1]
    for i in range(n):
        a, b = poly[i], nxt(i)
        ab = b - a
        Li = float(np.hypot(*ab))
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue                              # neighbouring edges share a vertex
            c, d = poly[j], nxt(j)
            cd = d - c
            Lj = float(np.hypot(*cd))
            sc, sd = _cross2(ab, c - a) / Li, _cross2(ab, d - a) / Li     # distances from line i
            sa, sb = _cross2(cd, a - c) / Lj, _cross2(cd, b - c) / Lj     # distances from line j
            where = f"near X {a[0]:.3f}, Z {a[1]:.3f} mm"
            if (sc * sd < 0 and abs(sc) > tol and abs(sd) > tol and
                    sa * sb < 0 and abs(sa) > tol and abs(sb) > tol):
                return f"two edges cross ({where})"
            if abs(sc) <= tol and abs(sd) <= tol:     # collinear: overlap of positive length?
                t = sorted([float(np.dot(c - a, ab)) / Li, float(np.dot(d - a, ab)) / Li])
                if min(t[1], Li) - max(t[0], 0.0) > tol:
                    return f"two edges overlap ({where})"
                continue
            # a vertex of one edge on the other edge (or on its vertex): a touch; crossing?
            for k, q, (e0, e1), s_q in ((j, c, (a, b), sc), ((j + 1) % n, d, (a, b), sd),
                                        (i, a, (c, d), sa), ((i + 1) % n, b, (c, d), sb)):
                if abs(s_q) > tol:
                    continue
                L = float(np.hypot(*(e1 - e0)))
                t = float(np.dot(q - e0, e1 - e0)) / L
                if t < -tol or t > L + tol:
                    continue
                if t <= tol or t >= L - tol:          # on a vertex of the other edge
                    m = i if (e0 is a) else j
                    m = m if t <= tol else (m + 1) % n
                    if m == k:
                        continue
                    b1, b2 = prv(m), nxt(m)
                else:                                 # inside the other edge
                    b1, b2 = e0, e1
                if _passes_cross(q, prv(k), nxt(k), b1, b2):
                    return f"the outline crosses itself at a vertex (X {q[0]:.3f}, Z {q[1]:.3f} mm)"
    return None


def _profile(poly, thickness_mm, centre_x_mm, source, notes=()):
    poly = _clean(poly)
    if len(poly) < 3 or abs(polygon_area(poly)) < 1e-9:
        raise ValueError("the weld outline encloses no area")
    fault = outline_fault(poly)
    if fault is not None:
        raise ValueError(f"the weld outline crosses itself: {fault}")
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
        if g == 0 and r > 0:
            raise ValueError("a double-V with no root gap and a root face is two separate weld regions; "
                             "set a root gap, or a root face of 0")
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
        if e.dxftype() == "POLYLINE" and (e.is_polygon_mesh or e.is_poly_face_mesh):
            continue        # surface meshes are not cross-section outlines
        lay = e.dxf.get("layer", "0")
        layers.add(lay)
        if layer is not None and lay != layer:
            continue
        # A polyline is judged part by part (its lines by their points, its arcs by their plane).
        parts = ([s for s in e.virtual_entities() if s.dxftype() in ("LINE", "ARC")]
                 if e.dxftype() in ("LWPOLYLINE", "POLYLINE") else [e])
        for part in parts:
            tilted, z_extra = _entity_plane(part)
            for pts in _entity_points(part, FLATTEN_MM / scale):
                if len(pts) >= 2:
                    z = np.concatenate([pts[:, 2], z_extra]) * scale
                    pieces.append((lay, pts[:, :2] * scale, (float(z.min()), float(z.max()), tilted)))
    return pieces, sorted(layers), units, scale


def _entity_plane(e):
    """
    (tilted, extra Z values) of an entity, in drawing units: tilted when its own plane (the
    extrusion of an arc, circle or ellipse, including a polyline's arcs) is not parallel to X-Y,
    whatever its sampled vertices show (a straight line is judged by its end points); extra Z from a spline's control and fit points, which its flattened
    vertices may not reach.
    """
    t = e.dxftype()
    tilted = False
    if t in ("ARC", "CIRCLE", "ELLIPSE"):
        ext = np.asarray(tuple(e.dxf.get("extrusion", (0.0, 0.0, 1.0))), dtype=float)
        n = np.linalg.norm(ext)
        tilted = not (n > 0 and abs(abs(ext[2]) / n - 1.0) <= 1e-12)
    z = []
    if t == "SPLINE":
        z = [p[2] for p in e.control_points] + [p[2] for p in e.fit_points]
    return tilted, np.asarray(z, dtype=float)


def _outline_is_flat(name, zinfo):
    """Refuse an outline (its entities' (zmin, zmax, tilted)) that is not in one X-Y plane."""
    if any(t for _, _, t in zinfo):
        raise ValueError(f"{name}: the outline is not drawn in one X-Y plane (an entity lies in a tilted "
                         "plane); draw the cross-section flat")
    lo, hi = min(z for z, _, _ in zinfo), max(z for _, z, _ in zinfo)
    if hi - lo > PLANAR_TOL_MM:
        raise ValueError(f"{name}: the outline is not drawn in one X-Y plane (Z spans {lo:g} to {hi:g} mm); "
                         "draw the cross-section flat")


def _entity_points(e, tol):
    """
    Polylines (drawing units, world X, Y, Z) of one entity, every vertex on the exact curve: lines by their
    ends, arcs, circles, ellipses and splines by ezdxf's own curve flattening (chord deviation
    <= tol), polylines split into their lines and arcs (bulges) first. Not through ezdxf.path,
    whose cubic approximation of arcs adds an error the tolerance would not bound.
    """
    t = e.dxftype()
    if t == "LINE":
        return [np.array([tuple(e.dxf.start), tuple(e.dxf.end)], dtype=float)]
    if t in ("LWPOLYLINE", "POLYLINE"):
        out = []
        for sub in e.virtual_entities():
            if sub.dxftype() in ("LINE", "ARC"):     # a 2D/3D polyline's parts; nothing else is an outline
                out += _entity_points(sub, tol)
        return out
    pts = list(e.flattening(tol))                # ARC, CIRCLE, ELLIPSE, SPLINE: exact-curve vertices (WCS)
    return [np.array([(v.x, v.y, v.z) for v in pts], dtype=float)]


def _dedupe(poly, tol):
    """Drop consecutive repeated vertices (and a repeated closing vertex) only."""
    keep = [poly[0]]
    for v in poly[1:]:
        if np.hypot(*(v - keep[-1])) > tol:
            keep.append(v)
    if len(keep) > 1 and np.hypot(*(keep[0] - keep[-1])) <= tol:
        keep.pop()
    return np.array(keep, dtype=float)


def _join_touching(loops, tol=JOIN_TOL_MM):
    """
    Closed loops that touch at a shared vertex, joined into one pinched outline (the lobes of a
    closed-root double-V, whichever order the file's entities came in), when the joined
    outline is simple apart from the pinch (a loop inside another sharing a vertex is not).
    """
    # A loop that passes a point twice (chaining can walk a pinch as a figure-eight) is split
    # into its lobes first, so every lobe takes one orientation before they are rejoined.
    # (Split before _clean: walked as a figure-eight, the pinch can sit on the straight line
    # through its neighbours, and _clean would drop it.)
    loops = [_clean(lobe) for l in loops for lobe in split_lobes(_dedupe(l, tol), tol)]
    loops = [l if polygon_area(l) > 0 else l[::-1] for l in loops if len(l) >= 3]
    merged = True
    while merged and len(loops) > 1:
        merged = False
        for a in range(len(loops)):
            for b in range(a + 1, len(loops)):
                A, B = loops[a], loops[b]
                d = np.hypot(A[:, None, 0] - B[None, :, 0], A[:, None, 1] - B[None, :, 1])
                ia, ib = np.unravel_index(np.argmin(d), d.shape)
                if d[ia, ib] > tol:
                    continue
                # A up to the shared vertex, all of B round from it, then the rest of A
                joined = np.vstack([A[:ia + 1], B[ib:], B[:ib], A[ia:]])
                joined = _clean(joined)
                if outline_fault(joined) is None:
                    loops = [l for k, l in enumerate(loops) if k not in (a, b)] + [joined]
                    merged = True
                    break
            if merged:
                break
    return loops


def _chain(pieces, tol=JOIN_TOL_MM, members=None):
    """
    Join polylines end to end into closed loops; returns (loops, open chains). If members is a
    list, the indices (into pieces) of the polylines in each closed loop are appended to it.
    """
    todo = [p for p in pieces]
    ids = list(range(len(pieces)))
    loops, open_ = [], []
    while todo:
        cur = todo.pop(0)
        used = [ids.pop(0)]
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
                used.append(ids.pop(i))
                grown = True
                break
        if np.hypot(*(cur[0] - cur[-1])) <= tol and len(cur) > 3:
            loops.append(cur[:-1])          # closed: the end point repeats the start
            if members is not None:
                members.append(used)
        else:
            open_.append(cur)
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
    members = []
    loops, open_ = _chain([p for _, p, _ in pieces], members=members)
    loops = _join_touching(loops)
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
    # The cross-section is read in the drawing's X-Y plane: the entities that make the outline
    # (every closed loop, joined into the one outline) must lie in one such plane; open entities
    # elsewhere in the file do not matter.
    _outline_is_flat(name, [pieces[i][2] for m in members for i in m])
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
def _inside(pts, poly, tol=EDGE_TOL_MM):
    """
    Points (N, 2) inside or on the edge (within tol) of polygon (K, 2): (N,) bool. Even-odd
    test for the interior; a point on an edge counts, so a face lying on a fan's outer ray is
    covered whichever side the edge falls.
    """
    pc = np.vstack([poly, poly[:1]])
    on_edge = _point_to_segments(pts, pc[:-1], pc[1:]) <= tol
    x, z = pts[:, 0][:, None], pts[:, 1][:, None]
    ax, az = poly[:, 0][None], poly[:, 1][None]
    bx, bz = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    cross = (az > z) != (bz > z)
    with np.errstate(divide="ignore", invalid="ignore"):
        xi = ax + (z - az) * (bx - ax) / (bz - az)
    return on_edge | (np.count_nonzero(cross & (x < xi), axis=1) % 2 == 1)


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
