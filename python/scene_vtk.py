"""
PyVista/VTK renderer of the scene model (scene_model.py): the 3D view of plan step 3.

Draws a Scene on any pyvista Plotter (a pyvistaqt QtInteractor in the Qt window, an off-screen
Plotter in tests and exports). Global frame in millimetres, Z down into the component; the
camera keeps -Z up, so depth is drawn downward.

Actors are named: setup actors once per calculation ('setup:...'), the selected law's
actors ('law:...') replaced in place when the law changes, the picked element ('pick:...').
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from scene import (COLOR_BACKWALL, COLOR_ELEMENT_ACTIVE, COLOR_ELEMENT_INACTIVE, COLOR_ELEMENT_TX,
                   COLOR_MATERIAL, COLOR_WEDGE_EDGE, COLOR_WEDGE_FACE, LAW_CMAP)

ELEMENT_COLOUR = {"single": COLOR_ELEMENT_ACTIVE, "tx": COLOR_ELEMENT_TX, "rx": COLOR_ELEMENT_ACTIVE}
COVERAGE_COLOUR = {1: "#2563eb", 2: "#7c3aed", 3: "#db2777"}
WELD_FACE, WELD_EDGE = "#fcd34d", "#92400e"
FUSION_STYLE = {"fusion-face": ("#92400e", "Fusion faces"), "fusion-covered": ("#16a34a", "Fusion face, covered"),
                "fusion-gap": ("#dc2626", "Fusion face, gap")}
RAY_COLOUR = {"single": "#2563eb", "tx": "#1d4ed8", "rx": "#dc2626"}

# Camera presets: (azimuth, elevation) in degrees of the view direction; see set_camera.
VIEWS = {"Iso": (-35.0, 28.0), "X-Z": (0.0, 0.0), "Y-Z": (-90.0, 0.0), "Top": (0.0, 89.9)}


def scene_bounds(scene, component_thickness_mm=0.0):
    """(lo, hi) mm over every primitive (and the backwall), padded."""
    pts = [p.coords for p in scene.prims if p.kind != "text"]
    allp = np.vstack(pts)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    w = scene.find("wedge")
    if w:
        lo[1] = min(lo[1], w[0].meta["y0"])
        hi[1] = max(hi[1], w[0].meta["y1"])
    if component_thickness_mm > 0:
        hi[2] = max(hi[2], component_thickness_mm)
    pad = np.maximum(2.0, 0.06 * (hi - lo))
    return lo - pad, hi + pad


def _prism(xz, y0, y1):
    """An X-Z polygon (N, 2) extruded across Y from y0 to y1."""
    pts = np.c_[xz[:, 0], np.full(len(xz), y0), xz[:, 1]]
    return pv.PolyData(pts, np.r_[len(pts), np.arange(len(pts))]).extrude((0, y1 - y0, 0), capping=True)


def _quads(coords):
    n = len(coords) // 4
    return pv.PolyData(coords, np.c_[np.full(n, 4), np.arange(4 * n).reshape(n, 4)].ravel())


def section_plane(scene):
    """(origin, normal): the vertical X-Z plane through the active aperture's centre Y."""
    act = [p for p in scene.find("element") if p.meta["active"]] or scene.find("element")
    y = float(np.mean(np.vstack([p.coords for p in act])[:, 1]))
    return (0.0, y, 0.0), (0.0, 1.0, 0.0)


def add_setup(pl, scene, component_thickness_mm=0.0, section=False):
    """Wedge, component, element faces (or markers) and the sweep's foci. Returns (lo, hi) bounds."""
    lo, hi = scene_bounds(scene, component_thickness_mm)
    origin, normal = section_plane(scene)
    pl._pac_law_meshes = None     # a fresh setup: law actors are added anew

    def clip(mesh):
        return mesh.clip(normal=normal, origin=origin, invert=False) if section else mesh

    # Component: a plate block to the backwall when its thickness is known, else the interface
    if component_thickness_mm > 0:
        plate = pv.Box(bounds=(lo[0], hi[0], lo[1], hi[1], 0.0, component_thickness_mm))
        pl.add_mesh(clip(plate), color=COLOR_MATERIAL, opacity=0.10, name="setup:component",
                    label="Component")
        pl.add_mesh(plate.extract_feature_edges(), color=COLOR_BACKWALL, line_width=1,
                    name="setup:component-edges")
    else:
        quad = pv.Rectangle([[lo[0], lo[1], 0.0], [hi[0], lo[1], 0.0], [hi[0], hi[1], 0.0]])
        pl.add_mesh(quad, color=COLOR_MATERIAL, opacity=0.15, name="setup:component",
                    label="Interface")
    for w in scene.find("wedge"):
        body = _prism(w.coords[:, [0, 2]], w.meta["y0"], w.meta["y1"])
        label = "Wedge (catalogue)" if w.meta["source"] == "catalogue" else "Wedge (schematic)"
        pl.add_mesh(clip(body), color=COLOR_WEDGE_FACE, opacity=0.15, name="setup:wedge", label=label)
        pl.add_mesh(body.extract_feature_edges(30), color=COLOR_WEDGE_EDGE, line_width=1,
                    name="setup:wedge-edges")

    faces = scene.find("element-face")
    if faces:
        for k, p in enumerate(faces):
            active = p.meta["active"]
            label = None
            if k == 0 or active:
                label = {"single": "Elements", "tx": "Tx elements", "rx": "Rx elements"}[p.meta["array"]] \
                    if active else "Inactive elements"
            if p.meta["schematic"] and active:
                label = (label or "") + " (schematic size)"
            pl.add_mesh(_quads(p.coords), color=ELEMENT_COLOUR[p.meta["array"]] if active else COLOR_ELEMENT_INACTIVE,
                        style="surface" if active else "wireframe", line_width=1,
                        name=f"setup:elements-{p.meta['array']}-{int(active)}", label=label)
    else:
        for p in scene.find("element"):
            pl.add_points(p.coords, color=ELEMENT_COLOUR[p.meta["array"]] if p.meta["active"] else COLOR_ELEMENT_INACTIVE,
                          point_size=8, render_points_as_spheres=True,
                          name=f"setup:elements-{p.meta['array']}-{int(p.meta['active'])}")
    for p in scene.find("weld"):
        # The weld runs along Y through the component: its outline extruded across the view.
        xz = p.coords[:, [0, 2]]
        pts = np.c_[xz[:, 0], np.full(len(xz), lo[1]), xz[:, 1]]
        face = pv.PolyData(pts, np.r_[len(pts), np.arange(len(pts))]).triangulate()
        body = face.extrude((0, hi[1] - lo[1], 0), capping=True)
        pl.add_mesh(clip(body), color=WELD_FACE, opacity=0.30, name="setup:weld", label="Weld")
        pl.add_mesh(body.extract_feature_edges(30), color=WELD_EDGE, line_width=1, name="setup:weld-edges")
    for role, (col, label) in FUSION_STYLE.items():
        runs = scene.find(role)
        if not runs:
            continue
        strips = []
        for p in runs:      # each run of a face as a strip along Y, lifted to the weld's ends
            c = p.coords
            for a, b in zip(c[:-1], c[1:]):
                strips.append([[a[0], lo[1], a[2]], [b[0], lo[1], b[2]], [b[0], hi[1], b[2]], [a[0], hi[1], a[2]]])
        pl.add_mesh(clip(_quads(np.asarray(strips, dtype=float).reshape(-1, 3))), color=col, opacity=0.85,
                    name=f"setup:{role}", label=label)
    for p in scene.find("coverage"):
        n = len(p.coords) // 4
        faces = np.c_[np.full(n, 4), np.arange(4 * n).reshape(n, 4)].ravel()
        pl.add_mesh(pv.PolyData(p.coords, faces), color=COVERAGE_COLOUR.get(p.meta["leg"], "#64748b"),
                    opacity=0.15, name=f"setup:coverage-{p.meta['leg']}",
                    label={1: "Coverage, direct", 2: "Coverage, 1st skip", 3: "Coverage, 2nd skip"}.get(p.meta["leg"]))
    for p in scene.find("focus-sweep"):
        if len(p.coords) > 1:
            pl.add_points(p.coords, scalars=np.asarray(p.meta["law"], dtype=float), cmap=LAW_CMAP,
                          point_size=8, render_points_as_spheres=True, show_scalar_bar=False,
                          name="setup:focus-sweep", label="Focal points (sweep)")
    return lo, hi


def _law_geometry(scene):
    """{actor name: (points (N, 3), kind, style)} for the current law."""
    out = {}
    for p in scene.find("ray"):
        out[f"law:ray-{p.meta['array']}"] = (p.coords, "segments", dict(color=RAY_COLOUR[p.meta["array"]],
                                                                         opacity=0.6, line_width=1, label="Rays"))
    for p in scene.find("interface-point"):
        out["law:interface"] = (p.coords, "points", dict(color="black", point_size=4, label="Interface points"))
    for p in scene.find("central-ray"):
        out["law:central-ray"] = (p.coords, "polyline", dict(color="black", line_width=3,
                                                             label="Central ray (skips)"))
    focus = [p for p in scene.find("focus") if p.meta["law"] == current_law(scene)]
    if focus:
        out["law:focus"] = (focus[0].coords, "points", dict(color="black", point_size=16,
                                                            render_points_as_spheres=True, label="Focal point"))
    return out


def add_law(pl, scene):
    """
    The current law's rays, interface points and focus. When the previous law's actors have
    the same number of points (the active aperture is fixed for a calculation), their meshes
    are updated in place; otherwise they are replaced. Never adds a second set.
    """
    cache = getattr(pl, "_pac_law_meshes", None)
    if cache is None or any(name not in pl.renderer.actors for name in cache):
        cache = {}
    new = _law_geometry(scene)
    for name in list(cache):
        if name not in new:
            pl.remove_actor(name, render=False)
            del cache[name]
    for name, (pts, kind, style) in new.items():
        mesh = cache.get(name)
        if mesh is not None and mesh.n_points == len(pts):
            mesh.points = np.asarray(pts, dtype=float)
            mesh.Modified()
            continue
        if kind == "segments":
            mesh = pv.line_segments_from_points(pts)
        elif kind == "polyline":
            mesh = pv.lines_from_points(np.asarray(pts, dtype=float))
        else:
            mesh = pv.PolyData(np.asarray(pts, dtype=float))
        if kind in ("segments", "polyline"):
            pl.add_mesh(mesh, name=name, **style)
        else:
            pl.add_points(mesh, name=name, **style)
        cache[name] = mesh
    pl._pac_law_meshes = cache


def current_law(scene):
    rays = scene.find("ray")
    if rays:
        return rays[0].meta["law"]
    pts = scene.find("interface-point")
    return pts[0].meta["law"] if pts else None


def set_camera(pl, view, lo, hi):
    """
    Look at the scene's centre along a preset direction (VIEWS: azimuth about the vertical,
    0 = from +Y, -90 = from -X; elevation above the part). -Z is up on screen, so depth is
    drawn downward; +X runs to the right in the X-Z view and +Y in the Y-Z view.
    """
    az, el = (np.radians(v) for v in VIEWS[view])
    centre = 0.5 * (lo + hi)
    dist = 2.2 * float(np.linalg.norm(hi - lo))
    # From +Y (so +X is to the right with -Z up), turned by azimuth, raised by elevation.
    direction = np.array([np.cos(el) * np.sin(az), np.cos(el) * np.cos(az), -np.sin(el)])
    pl.camera.focal_point = tuple(centre)
    pl.camera.position = tuple(centre + dist * direction)
    pl.camera.up = (0.0, 0.0, -1.0) if view != "Top" else (0.0, -1.0, 0.0)
    # Axis views read as drawings: parallel projection; the oblique view keeps perspective.
    if view == "Iso":
        pl.disable_parallel_projection()
    else:
        pl.enable_parallel_projection()
    pl.reset_camera_clipping_range()
    pl.reset_camera(bounds=(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))


def add_axes(pl, lo, hi):
    """Labelled millimetre axes on the scene's bounds, and the orientation marker."""
    pl.show_bounds(bounds=(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]), xtitle="X (mm)",
                   ytitle="Y (mm)", ztitle="Z depth (mm)", location="outer", grid=False,
                   ticks="outside", font_size=9, color="#334155", fmt="%.0f")
    pl.show_axes()


def refit_camera(pl, lo, hi):
    """Keep the camera's viewing direction, up and projection; frame new bounds (lo, hi)."""
    cam = pl.camera
    direction = np.subtract(cam.position, cam.focal_point)
    direction /= np.linalg.norm(direction)
    centre = 0.5 * (np.asarray(lo) + np.asarray(hi))
    cam.focal_point = tuple(centre)
    cam.position = tuple(centre + 2.2 * float(np.linalg.norm(np.subtract(hi, lo))) * direction)
    pl.reset_camera(bounds=(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2]))
    pl.reset_camera_clipping_range()


def display_positions(renderer, pts_mm):
    """(N, 3) world points (mm) -> (N, 3) display coordinates: pixel x, y and depth (0 near, 1 far)."""
    out = np.empty((len(pts_mm), 3))
    for k, p in enumerate(np.asarray(pts_mm, dtype=float)):
        renderer.SetWorldPoint(p[0], p[1], p[2], 1.0)
        renderer.WorldToDisplay()
        out[k] = renderer.GetDisplayPoint()
    return out


def element_at_display(scene, renderer, xy, max_px=None):
    """
    The internal index of the element whose centre is drawn nearest the screen position xy
    (pixels, as VTK reports a click), or None when none is within max_px. Picking in screen
    space: solids, rays and highlights in front of an element cannot intercept it. Ties (one
    element drawn over another) go to the element nearer the camera. max_px defaults to
    half the smallest on-screen spacing between element centres, between 4 and 20 pixels.
    """
    groups = scene.find("element")
    if not groups:
        return None
    centres = np.vstack([p.coords for p in groups])
    index = np.concatenate([p.meta["indices"] for p in groups])
    disp = display_positions(renderer, centres)
    if max_px is None:
        d2 = np.linalg.norm(disp[:, None, :2] - disp[None, :, :2], axis=2)
        d2[np.diag_indices_from(d2)] = np.inf
        max_px = float(np.clip(0.5 * d2.min(), 4.0, 20.0)) if len(disp) > 1 else 20.0
    dist = np.hypot(disp[:, 0] - xy[0], disp[:, 1] - xy[1])
    near = np.flatnonzero(dist <= max_px)
    if near.size == 0:
        return None
    best = near[np.lexsort((disp[near, 2], np.round(dist[near], 1)))[0]]
    return int(index[best])


def render_scene(scene, component_thickness_mm=0.0, view="Iso", window_size=(1200, 800),
                 section=False, path=None):
    """Off-screen render of a whole scene (setup and current law); returns the image array."""
    pl = pv.Plotter(off_screen=True, window_size=window_size)
    pl.set_background("white")
    lo, hi = add_setup(pl, scene, component_thickness_mm, section=section)
    add_law(pl, scene)
    pl.add_legend(bcolor="white", face="rectangle", size=(0.18, 0.24), loc="lower right")
    add_axes(pl, lo, hi)
    set_camera(pl, view, lo, hi)
    img = pl.screenshot(path, return_img=True)
    pl.close()
    return img
