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
    for p in scene.find("focus-sweep"):
        if len(p.coords) > 1:
            pl.add_points(p.coords, scalars=np.asarray(p.meta["law"], dtype=float), cmap=LAW_CMAP,
                          point_size=8, render_points_as_spheres=True, show_scalar_bar=False,
                          name="setup:focus-sweep", label="Focal points (sweep)")
    return lo, hi


def add_law(pl, scene):
    """The current law's rays, interface points and focus; replaces the previous law's."""
    for name in list(pl.renderer.actors):
        if name.startswith("law:"):
            pl.remove_actor(name, render=False)
    for p in scene.find("ray"):
        pl.add_mesh(pv.line_segments_from_points(p.coords), color=RAY_COLOUR[p.meta["array"]],
                    opacity=0.6, line_width=1, name=f"law:ray-{p.meta['array']}", label="Rays")
    for p in scene.find("interface-point"):
        pl.add_points(p.coords, color="black", point_size=4, name="law:interface",
                      label="Interface points")
    focus = [p for p in scene.find("focus") if p.meta["law"] == current_law(scene)]
    if focus:
        pl.add_points(focus[0].coords, color="black", point_size=16, render_points_as_spheres=True,
                      name="law:focus", label="Focal point")


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


def nearest_element(scene, point, max_distance_mm):
    """The internal index of the element centre nearest `point` (mm), or None beyond max_distance_mm."""
    best, best_d = None, max_distance_mm
    for p in scene.find("element"):
        d = np.linalg.norm(p.coords - np.asarray(point, dtype=float), axis=1)
        k = int(np.argmin(d))
        if d[k] <= best_d:
            best, best_d = int(p.meta["indices"][k]), float(d[k])
    return best


def render_scene(scene, component_thickness_mm=0.0, view="Iso", window_size=(1200, 800),
                 section=False, path=None):
    """Off-screen render of a whole scene (setup and current law); returns the image array."""
    pl = pv.Plotter(off_screen=True, window_size=window_size)
    pl.set_background("white")
    lo, hi = add_setup(pl, scene, component_thickness_mm, section=section)
    add_law(pl, scene)
    pl.add_legend(bcolor="white", face="rectangle", size=(0.18, 0.24), loc="lower right")
    pl.show_axes()
    set_camera(pl, view, lo, hi)
    img = pl.screenshot(path, return_img=True)
    pl.close()
    return img
