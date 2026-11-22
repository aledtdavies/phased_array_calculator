"""
Renderer-independent scene: what the views show, as primitives in the global frame.

Frame and units: the calculator's global frame in millimetres. X along the wedge, Y across,
Z down into the component (Z = 0 the wedge-component interface, Z < 0 in the wedge).

A Scene is a flat list of Prim. Each has a kind (points, segments, polygon, polyline, text),
coordinates (N, 3) in mm, a role that renderers style by, and metadata (law index, array,
active flag, ...). Renderers (scene.py's matplotlib views today; Qt/PyVista views later)
only draw primitives: geometry is decided here once, so every view shows the same thing
and it can be tested without a GUI.

Roles:
  element          points; meta array ('single', 'tx', 'rx'), active (bool), indices
  element-face     quads (4 corners per element, in index order) of the element footprints on
                   the probe face; meta array, active, indices, size_mm (width, length) and
                   schematic (True when the size is not the probe's own, see element_size)
  wedge            polygon in the X-Z plane (Y = 0); meta source ('catalogue' | 'schematic'),
                   angle_deg, y0/y1 (the extrusion across Y used by 3D views)
  probe-body       polygon in the X-Z plane: a schematic housing on the element plane
  dimension        polyline: element 1's height drop line; meta text, text_at (x, z)
  wedge-angle      text; meta text
  contact          text, when the elements sit on the interface (no wedge body)
  envelope-ray     segments element -> interface -> focus for the first and last active
                   element of each array; meta law, array, element
  focus            points, one law's focus; meta law
  ray              segments element -> interface -> focus, all active elements of the
                   current law (an even subset of at most max_rays); meta law, array
  interface-point  points where those rays cross the interface; meta law
  interface-point-all  points where every active element's ray of the current law crosses
                   the interface (for framing views); meta law
  focus-sweep      points, the focus of every law; meta law (array of indices)
  coverage         quads (4 corners each) of the sweep's coverage fan for one leg (see
                   coverage.py); meta leg (1 = direct, 2 = first skip, ...)
  central-ray      polyline, the current law's (or dragged focus's) central ray with its skips;
                   meta legs
  coverage-extent  points, every law's central-ray path: for framing only, never drawn
  weld             polygon in the X-Z plane, the weld region's outline (weld.py; extruded
                   along Y by 3D views); meta source
  fusion-face      polyline, a fusion face when no coverage is shown; meta name
  fusion-covered   polyline, a run of a fusion face reached by the coverage fans; meta name
  fusion-gap       polyline, a run of a fusion face no fan reaches; meta name
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np

CONTACT_TOL_MM = 1e-3   # elements closer than this to Z = 0 count as contact


@dataclass
class Prim:
    kind: str
    coords: np.ndarray
    role: str
    meta: dict = field(default_factory=dict)


@dataclass
class Scene:
    prims: list
    contact: bool

    def find(self, role, **meta):
        """Primitives with this role whose metadata matches every given key."""
        return [p for p in self.prims
                if p.role == role and all(p.meta.get(k) == v for k, v in meta.items())]

    def one(self, role, **meta):
        hits = self.find(role, **meta)
        if len(hits) != 1:
            raise LookupError(f"{len(hits)} primitives with role {role!r} and {meta}")
        return hits[0]


# ---------------------------------------------------------------------------
# Element groups
# ---------------------------------------------------------------------------
def is_dual(probe) -> bool:
    return hasattr(probe, "array_separation")


def array_of(probe):
    """Per element (internal order): 'single', or 'tx' / 'rx' for the two arrays of a dual."""
    n = probe.total_elements
    if not is_dual(probe):
        return np.array(["single"] * n)
    return np.where(np.arange(n) < n // 2, "tx", "rx")


def envelope_indices(probe):
    """
    [(array, first, last)] active elements bounding each array's aperture (internal
    indices). An array with no active element is left out.
    """
    act = np.asarray(probe.get_active_element_indices())
    if act.size == 0:
        return []
    arrays = array_of(probe)
    out = []
    for name in (("tx", "rx") if is_dual(probe) else ("single",)):
        sel = act[arrays[act] == name]
        if sel.size:
            out.append((name, int(sel[0]), int(sel[-1])))
    return out


def decimate_rays(active, max_rays):
    """Active element indices to draw rays from: all, or an even subset that keeps both ends."""
    active = np.asarray(active)
    if max_rays is None or max_rays <= 0 or active.size <= max_rays:
        return active
    pick = np.unique(np.round(np.linspace(0, active.size - 1, max_rays)).astype(int))
    return active[pick]


def user_element_numbers(probe):
    """
    1-based element numbers in the user's numbering convention, indexed by internal storage
    position (internal index = block*Nx*Ny + ix*Ny + iy). column-first: Y varies fastest
    (number = ix*Ny + iy + 1); row-first: X varies fastest (number = iy*Nx + ix + 1); dual
    probes number the second array after the first.
    """
    nx, ny = probe.num_elements, probe.num_elements_y
    per = nx * ny
    internal = np.arange(probe.total_elements)
    block, local = internal // per, internal % per
    ix, iy = local // ny, local % ny
    if probe.element_order == "row-first" and ny > 1:
        local_user = iy * nx + ix
    else:
        local_user = local
    return block * per + local_user + 1


def element_size(probe, width_m=None, length_m=None):
    """
    Element footprint (width along the primary axis, length along the passive axis), metres,
    and whether it is schematic (not the probe's own size).

    Linear arrays: the given width (a catalogue's elementWidth) and length (its elevation);
    a missing one is drawn as 0.9 x pitch or 10 mm. Matrix arrays: the given width, else
    0.9 x pitch; the length is always 0.9 x passive pitch, since catalogues do not give a
    matrix element's passive size. Schematic whenever a drawn size is not given.
    """
    w = width_m if width_m is not None else 0.9 * probe.pitch
    if probe.num_elements_y > 1:
        return float(w), float(0.9 * probe.pitch_y), True
    l = length_m if length_m is not None else 0.010
    return float(w), float(l), bool(width_m is None or length_m is None)


def element_faces_mm(solver, width_m, length_m):
    """(4N, 3) mm: the corners of every element's footprint, transformed like the centres."""
    probe, wedge = solver.probe, solver.wedge
    local = probe.get_element_positions(center_at_origin=False)
    signs = wedge.roof_signs(probe)
    offs = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]]) * 0.5 * np.array([width_m, length_m])
    corners = np.repeat(local, 4, axis=0)
    corners[:, :2] += np.tile(offs, (len(local), 1))
    return wedge.transform_points(corners, np.repeat(signs, 4)) * 1000


# ---------------------------------------------------------------------------
# Wedge geometry
# ---------------------------------------------------------------------------
def wedge_silhouette_xz(elements_mm, wedge):
    """
    Schematic X-Z wedge silhouette (mm, Z down) under the element footprint, derived from
    the wedge angle and the transformed element positions, or None for a contact setup.
    Used when no catalogue outline is known. Returns [(x, z), ...].
    """
    ec = elements_mm[:, 0]
    ez = elements_mm[:, 2]
    if float(np.max(np.abs(ez))) < CONTACT_TOL_MM:
        return None
    span = float(np.max(ec) - np.min(ec))
    margin = max(2.0, 0.15 * span)
    tan_a = float(np.tan(wedge.angle_rad))
    if tan_a > 1e-6:
        # Top-face silhouette line z(x) = -tan_a * x + c through the highest elements
        # (covers roof-angled duals too).
        c = float(np.min(ez + tan_a * ec))
        x_toe = c / tan_a       # z = 0 crossing of the top-face line
        x_back = float(np.max(ec)) + margin
        z_back = -tan_a * x_back + c
        # Cap a very long toe with a vertical end face so a shallow wedge doesn't
        # dominate the frame.
        x_front_cap = float(np.min(ec)) - 4.0 * margin
        if x_toe < x_front_cap:
            z_front = -tan_a * x_front_cap + c
            return [(x_front_cap, 0.0), (x_back, 0.0),
                    (x_back, z_back), (x_front_cap, z_front)]
        return [(x_toe, 0.0), (x_back, 0.0), (x_back, z_back)]
    # Flat wedge (delay line): rectangle
    z_top = float(np.min(ez))
    return [(np.min(ec) - margin, 0.0), (np.max(ec) + margin, 0.0),
            (np.max(ec) + margin, z_top), (np.min(ec) - margin, z_top)]


def wedge_yz_rect(scene):
    """
    The wedge's Y-Z silhouette (mm, [(y, z), ...]): a rectangle over the element footprint in
    Y (margin max(2 mm, 15 % of the footprint)) up to the tallest of the elements and, for a
    catalogue outline, the outline's top. None for a contact setup.
    """
    if scene.contact:
        return None
    el = np.vstack([p.coords for p in scene.find("element")])
    ec, ez = el[:, 1], el[:, 2]
    span = float(np.max(ec) - np.min(ec))
    margin = max(2.0, 0.15 * span)
    z_top = float(np.min(ez))
    wedge = scene.one("wedge")
    if wedge.meta["source"] == "catalogue":
        z_top = min(z_top, float(np.min(wedge.coords[:, 2])))
    return [(np.min(ec) - margin, 0.0), (np.max(ec) + margin, 0.0),
            (np.max(ec) + margin, z_top), (np.min(ec) - margin, z_top)]


def _xz(verts):
    """[(x, z), ...] -> (N, 3) with Y = 0."""
    v = np.asarray(verts, dtype=float)
    return np.c_[v[:, 0], np.zeros(len(v)), v[:, 1]]


def _setup_prims(solver, outline_mm, element_size_m=None):
    probe, wedge = solver.probe, solver.wedge
    el = wedge.get_transformed_elements(probe) * 1000
    act = np.asarray(probe.get_active_element_indices())
    on = np.zeros(len(el), dtype=bool)
    on[act] = True
    arrays = array_of(probe)
    prims = []
    for name in (("tx", "rx") if is_dual(probe) else ("single",)):
        for active in (True, False):
            sel = (arrays == name) & (on if active else ~on)
            if sel.any():
                prims.append(Prim("points", el[sel], "element",
                                  {"array": name, "active": active,
                                   "indices": np.flatnonzero(sel)}))
    if element_size_m is not None:
        w, l, schematic = element_size(probe, *element_size_m)
        faces = element_faces_mm(solver, w, l).reshape(-1, 4, 3)
        for p in [p for p in prims if p.role == "element"]:
            idx = p.meta["indices"]
            prims.append(Prim("quads", faces[idx].reshape(-1, 3), "element-face",
                              dict(p.meta, size_mm=(w * 1e3, l * 1e3), schematic=schematic)))

    ez = el[:, 2]
    contact = float(np.max(np.abs(ez))) < CONTACT_TOL_MM
    if contact:
        # Placed at the element footprint's lowest X and lowest Y, just above the interface,
        # so either projection can show it.
        prims.append(Prim("text", np.array([[float(np.min(el[:, 0])), float(np.min(el[:, 1])), -1.2]]),
                          "contact", {"text": "Contact"}))
        return prims, contact, el

    if outline_mm is not None:
        verts, source = [tuple(v) for v in outline_mm], "catalogue"
    else:
        verts, source = wedge_silhouette_xz(el, wedge), "schematic"
    # 3D extrusion across Y: the wedge width is not modelled, so a little wider than the
    # element footprint (at least 15 % of the aperture length) so it reads as a body.
    y_margin = max(3.0, 0.2 * float(np.ptp(el[:, 1])), 0.15 * float(np.ptp(el[:, 0])))
    prims.append(Prim("polygon", _xz(verts), "wedge",
                      {"source": source, "angle_deg": wedge.angle_degrees,
                       "y0": float(np.min(el[:, 1])) - y_margin,
                       "y1": float(np.max(el[:, 1])) + y_margin}))

    # Schematic probe body on the element plane over the element extent
    ec = el[:, 0]
    tan_a = float(np.tan(wedge.angle_rad))
    if tan_a > 1e-6:
        c_line = float(np.min(ez + tan_a * ec))
        z_at = lambda x: -tan_a * x + c_line
    else:
        z_top = float(np.min(ez))
        z_at = lambda x: z_top
    hp = max(3.0, 0.25 * abs(float(np.min(ez))))
    x0, x1 = float(np.min(ec)), float(np.max(ec))
    prims.append(Prim("polygon", _xz([(x0, z_at(x0)), (x1, z_at(x1)),
                                     (x1, z_at(x1) - hp), (x0, z_at(x0) - hp)]),
                      "probe-body"))

    # Dimensions: element 1's height drop line, and the wedge angle over the body
    x_el1, z_el1 = float(ec[0]), float(ez[0])
    prims.append(Prim("polyline", _xz([(x_el1, 0.0), (x_el1, z_el1)]), "dimension",
                      {"text": f"h1={abs(z_el1):.1f} mm",
                       "text_at": (x_el1 + 0.8, z_el1 * 0.5)}))
    x_mid = 0.5 * (min(v[0] for v in verts) + max(v[0] for v in verts))
    z_top_wedge = min(v[1] for v in verts)
    prims.append(Prim("text", _xz([(x_mid, z_top_wedge - 1.0)]), "wedge-angle",
                      {"text": f"angle={wedge.angle_degrees:.1f}°"}))
    return prims, contact, el


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
def build_scene(solver, get_law: Callable, indices: Sequence[int], *,
                outline_mm=None, current: Optional[int] = None, max_rays: Optional[int] = None,
                sweep_focal_mm=None, element_size_m=None) -> Scene:
    """
    The scene for the laws in `indices`. get_law(i) returns (interface_points_mm (N, 3),
    target_mm (3,)) for law i. Every listed law gets its envelope rays and focus; the
    `current` law also gets its rays from every active element (decimated to max_rays)
    and interface points. sweep_focal_mm: (M, 3) foci of the whole sweep, drawn as the
    focus-sweep. outline_mm: a catalogue wedge outline [(x, z), ...] in the X-Z plane.
    element_size_m: (width, length) in metres, either may be None, to add element-face
    footprints (see element_size); None adds none.
    """
    probe = solver.probe
    prims, contact, el = _setup_prims(solver, outline_mm, element_size_m)
    arrays = array_of(probe)
    env = envelope_indices(probe)
    laws = {}
    for idx in indices:
        int_pts, target = get_law(idx)
        int_pts = np.asarray(int_pts, dtype=float)
        target = np.asarray(target, dtype=float)
        laws[idx] = (int_pts, target)
        for name, i0, i1 in env:
            for i in (i0, i1):
                prims.append(Prim("segments", np.array([el[i], int_pts[i], int_pts[i], target]),
                                  "envelope-ray", {"law": idx, "array": name, "element": i}))
        prims.append(Prim("points", target[None, :], "focus", {"law": idx}))
    if current is not None:
        int_pts, target = laws[current] if current in laws else tuple(
            np.asarray(v, dtype=float) for v in get_law(current))
        act = np.asarray(probe.get_active_element_indices())
        pick = decimate_rays(act, max_rays)
        for name in (("tx", "rx") if is_dual(probe) else ("single",)):
            sel = pick[arrays[pick] == name]
            if sel.size:
                seg = np.empty((4 * sel.size, 3))
                seg[0::4], seg[1::4], seg[2::4], seg[3::4] = el[sel], int_pts[sel], int_pts[sel], target
                prims.append(Prim("segments", seg, "ray",
                                  {"law": current, "array": name, "elements": sel,
                                   "n_active": int(act.size)}))
        prims.append(Prim("points", int_pts[pick], "interface-point",
                          {"law": current, "elements": pick}))
        prims.append(Prim("points", int_pts[act], "interface-point-all",
                          {"law": current, "elements": act}))
        if current not in laws:
            prims.append(Prim("points", target[None, :], "focus", {"law": current}))
    if sweep_focal_mm is not None and len(sweep_focal_mm):
        fp = np.asarray(sweep_focal_mm, dtype=float)
        prims.append(Prim("points", fp, "focus-sweep", {"law": np.arange(len(fp))}))
    return Scene(prims, contact)


def coverage_prims(cov, path_mm=None):
    """
    Coverage primitives from a coverage.SweepCoverage (metres) in mm: one 'coverage' prim per
    leg holding that leg's fan quads, and, given path_mm (legs + 1, 3), the 'central-ray'.
    """
    prims = []
    for leg, quads in sorted(cov.fans.items()):
        if quads:
            prims.append(Prim("quads", np.vstack(quads) * 1000, "coverage", {"leg": leg}))
    if path_mm is not None:
        prims.append(Prim("polyline", np.asarray(path_mm, dtype=float), "central-ray", {"legs": cov.legs}))
    # Not drawn: every law's path, so views frame all skips (a sweep with no fans included).
    prims.append(Prim("points", np.vstack(cov.paths) * 1000, "coverage-extent", {}))
    return prims


def weld_prims(profile, fusion=None):
    """
    Weld primitives (mm) from a weld.WeldProfile: its outline, and its fusion faces, split into
    covered and gap runs when fusion (a weld.FusionCoverage) is given.
    """
    prims = [Prim("polygon", _xz(profile.polygon), "weld", {"source": profile.source})]
    if fusion is None:
        for name, face in profile.faces:
            prims.append(Prim("polyline", _xz(face), "fusion-face", {"name": name}))
    else:
        for f in fusion.faces:
            for run, covered in f.runs():
                prims.append(Prim("polyline", _xz(run), "fusion-covered" if covered else "fusion-gap",
                                  {"name": f.name}))
    return prims


# ---------------------------------------------------------------------------
# 3D framing, section plane and solids (renderer independent: the Qt/VTK view and the browser's
# 3D view both use these, so they frame, cut and fill the same way)
# ---------------------------------------------------------------------------
def scene_bounds(scene, component_thickness_mm=0.0):
    """(lo, hi) mm over every primitive (and the wedge's Y extent and the backwall), padded."""
    prims = scene.prims if isinstance(scene, Scene) else scene
    pts = [np.asarray(p.coords, dtype=float).reshape(-1, 3) for p in prims if p.kind != "text"]
    allp = np.vstack(pts)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    for w in [p for p in prims if p.role == "wedge"][:1]:
        lo[1] = min(lo[1], w.meta["y0"])
        hi[1] = max(hi[1], w.meta["y1"])
    if component_thickness_mm > 0:
        hi[2] = max(hi[2], component_thickness_mm)
    pad = np.maximum(2.0, 0.06 * (hi - lo))
    return lo - pad, hi + pad


def section_y(scene):
    """Y (mm) of the 3D views' section: the vertical X-Z plane through the active aperture's centre."""
    prims = scene.prims if isinstance(scene, Scene) else scene
    els = [p for p in prims if p.role == "element"]
    act = [p for p in els if p.meta["active"]] or els
    return float(np.mean(np.vstack([p.coords for p in act])[:, 1]))


def triangulate_polygon(xy):
    """
    Triangles (M, 3) of vertex indices filling a simple polygon (N, 2), by ear clipping. The
    polygon may be concave and either orientation. An ear is cut only when no other vertex lies in
    its triangle or on its boundary (so a diagonal never passes through a vertex); a collinear
    vertex between its neighbours is cut as a zero-area ear. Repeated vertices are allowed.
    """
    p = np.asarray(xy, dtype=float)
    n = len(p)
    if n < 3:
        return np.zeros((0, 3), dtype=int)
    area2 = float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))
    idx = list(range(n)) if area2 >= 0 else list(range(n - 1, -1, -1))     # counter-clockwise
    scale = float(np.ptp(p, axis=0).max()) or 1.0
    eps = 1e-12 * scale * scale

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def blocks(q, a, b, c):
        """q (not one of the corners) in the closed triangle a, b, c (counter-clockwise)."""
        if any(abs(q[0] - v[0]) <= 1e-12 * scale and abs(q[1] - v[1]) <= 1e-12 * scale for v in (a, b, c)):
            return False
        return cross(a, b, q) >= -eps and cross(b, c, q) >= -eps and cross(c, a, q) >= -eps

    def is_ear(k, convex):
        m = len(idx)
        i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % m]
        a, b, c = p[i0], p[i1], p[i2]
        turn = cross(a, b, c)
        if convex:
            return turn > eps and not any(blocks(p[j], a, b, c) for j in idx if j not in (i0, i1, i2))
        # a collinear vertex lying between its neighbours: removing it leaves the outline unchanged
        return abs(turn) <= eps and (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) >= 0

    tris = []
    while len(idx) > 3:
        ear = next((k for convex in (True, False) for k in range(len(idx)) if is_ear(k, convex)), None)
        if ear is None:              # not simple: fan the rest rather than fail
            tris += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
            idx = []
            break
        m = len(idx)
        tris.append((idx[ear - 1], idx[ear], idx[(ear + 1) % m]))
        del idx[ear]
    if len(idx) == 3:
        tris.append(tuple(idx))
    return np.asarray(tris, dtype=int).reshape(-1, 3)


def solid_prims(scene, component_thickness_mm=0.0, lobes=None):
    """
    The 3D views' solids as X-Z cross-sections extruded across Y: [{role, xz (N, 2), tris (M, 3),
    y0, y1}], mm. The component (a plate to the backwall, when its thickness is known), the wedge
    (its own Y extent) and each weld lobe (the view's whole Y extent). lobes: a function splitting
    a weld outline into simple polygons (weld.split_lobes); the outline itself when None.
    """
    lo, hi = scene_bounds(scene, component_thickness_mm)
    prims = scene.prims if isinstance(scene, Scene) else scene
    out = []
    if component_thickness_mm > 0:
        xz = np.array([[lo[0], 0.0], [hi[0], 0.0], [hi[0], component_thickness_mm], [lo[0], component_thickness_mm]])
        out.append(dict(role="component", xz=xz, tris=triangulate_polygon(xz), y0=float(lo[1]), y1=float(hi[1])))
    for w in [p for p in prims if p.role == "wedge"]:
        xz = np.asarray(w.coords, dtype=float)[:, [0, 2]]
        out.append(dict(role="wedge", xz=xz, tris=triangulate_polygon(xz), y0=w.meta["y0"], y1=w.meta["y1"],
                        source=w.meta.get("source")))
    for w in [p for p in prims if p.role == "weld"]:
        xz = np.asarray(w.coords, dtype=float)[:, [0, 2]]
        for part in (lobes(xz) if lobes else [xz]):
            out.append(dict(role="weld", xz=np.asarray(part, dtype=float), tris=triangulate_polygon(part),
                            y0=float(lo[1]), y1=float(hi[1])))
    return out
