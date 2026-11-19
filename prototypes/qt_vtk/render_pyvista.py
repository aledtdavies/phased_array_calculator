"""
PROTOTYPE (plan step 3): PyVista/VTK renderer of the scene model.

    python render_pyvista.py [buildFE/catalog folder]     -> off-screen PNGs in docs/plans/images
    python render_pyvista.py [folder] --show              -> interactive window (click an element)

`add_scene(plotter, prims)` is the whole renderer: the pyvistaqt mock-up uses it unchanged.
"""
import os
import sys

import numpy as np
import pyvista as pv

from scene_model import (build_scene, constant_depth_sweep, demo_setup, single_v_weld,
                         DelayLaw, Material, Wedge, create_probe_assembly)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "plans", "images"))

COLOURS = {"element-active": "#dc2626", "element-tx": "#2563eb", "component": "#94a3b8", "element-inactive": "#94a3b8", "ray": "#1d4ed8",
           "focus": "black", "focus-sweep": None, "wedge": "#22c55e", "weld": "#f59e0b",
           "coverage-leg1": "#2563eb", "coverage-leg2": "#7c3aed", "coverage-leg3": "#db2777",
           "interface": "#94a3b8", "backwall": "#334155", "central-ray": "black"}


def prism_mesh(p):
    """Extrude an X-Z outline (coords mm, Y ignored) across meta y0..y1."""
    xz = p.coords[:, [0, 2]]
    y0, y1 = p.meta["y0"], p.meta["y1"]
    pts = np.c_[xz[:, 0], np.full(len(xz), y0), xz[:, 1]]
    face = np.r_[len(pts), np.arange(len(pts))]
    return pv.PolyData(pts, face).extrude((0, y1 - y0, 0), capping=True)


def add_scene(pl, prims, element_size=None):
    """Add every primitive to a pv.Plotter (or pyvistaqt QtInteractor). Returns the element actor."""
    picked = None
    for p in prims:
        c = COLOURS.get(p.role)
        if p.kind == "prism":
            pl.add_mesh(prism_mesh(p), color=c, opacity=0.18 if p.role == "wedge" else 0.35,
                        show_edges=False, label=p.label, smooth_shading=False)
            pl.add_mesh(prism_mesh(p).extract_feature_edges(30), color=c, line_width=1.5)
        elif p.kind == "box":
            (x0, y0, z0), (x1, y1, z1) = p.coords
            box = pv.Box(bounds=(x0, x1, y0, y1, z0, z1))
            pl.add_mesh(box, color=c, opacity=0.10, label=p.label)
            pl.add_mesh(box.extract_feature_edges(), color="#475569", line_width=1)
        elif p.kind == "polygon":
            n = p.meta["n_quads"]
            faces = np.c_[np.full(n, 4), np.arange(4 * n).reshape(n, 4)].ravel()
            pl.add_mesh(pv.PolyData(p.coords, faces), color=c, opacity=0.18, label=p.label)
        elif p.kind == "segments":
            pl.add_mesh(pv.line_segments_from_points(p.coords), color=c, opacity=0.5,
                        line_width=1, label=p.label)
        elif p.kind == "polyline":
            pl.add_mesh(pv.lines_from_points(p.coords), color=c, line_width=3, label=p.label)
        elif p.kind == "points" and len(p.coords):
            if p.role == "focus-sweep":
                pl.add_points(p.coords, scalars=p.meta["law"], cmap="viridis", point_size=9,
                              render_points_as_spheres=True, show_scalar_bar=False,
                              label=p.label)
            elif p.role.startswith("element"):
                size = element_size or 0.6
                glyphs = pv.PolyData(p.coords).glyph(geom=pv.Cube(x_length=size, y_length=size * 3,
                                                                  z_length=size * 0.4),
                                                     orient=False, scale=False)
                actor = pl.add_mesh(glyphs, color=c, label=p.label,
                                    style="wireframe" if p.role == "element-inactive" else "surface")
                if p.role in ("element-active", "element-tx"):
                    picked = actor
            else:
                pl.add_points(p.coords, color=c, point_size=16, render_points_as_spheres=True,
                              label=p.label)
    pl.add_legend(bcolor="white", face="rectangle", size=(0.17, 0.26), loc="lower right")
    pl.show_axes()
    return picked


def z_down_camera(pl, focus, distance, azimuth_deg=-60, elevation_deg=25):
    """
    Look at `focus` (mm) from above the part (-Z is up) and from +Y (so +X runs to the right), turned by
    azimuth about the vertical; depth (+Z) is drawn downward.
    """
    a, e = np.radians(azimuth_deg), np.radians(elevation_deg)
    direction = np.array([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), -np.sin(e)])
    pl.camera.focal_point = tuple(focus)
    pl.camera.position = tuple(np.asarray(focus) + distance * direction)
    pl.camera.up = (0, 0, -1)


def linear_scene(catalog_dir):
    solver, outline, _ = demo_setup(catalog_dir)
    T = 0.025
    sweep = constant_depth_sweep(solver, np.arange(40, 71, 2.5), 0.020, wave="shear")
    cur = len(sweep) // 2
    weld = single_v_weld(sweep[cur][1][0] + 0.040, T)
    return build_scene(solver, sweep, cur, T, outline_xz=outline, weld_xz=weld, n_legs=2)


def dual_matrix_scene():
    probe = create_probe_assembly("Dual Matrix", 16, 1.0e-3, 2.25e6, num_elements_y=4,
                                  pitch_y=1.5e-3, array_separation=14e-3,
                                  element_order="column-first")
    solver = DelayLaw(probe, Wedge(18.0, 0.008, 2330.0, 0.004, roof_angle_degrees=5.0),
                      Material(5740.0, 3130.0))
    T = 0.040
    sweep = constant_depth_sweep(solver, np.arange(35, 71, 5), 0.030, skew_deg=12.0)
    return build_scene(solver, sweep, 3, T, n_legs=1, max_rays=64, skew_deg=12.0)


def main(catalog_dir=None, show=False):
    os.makedirs(OUT, exist_ok=True)
    for name, prims, cam in (("proto_pyvista_linear.png", linear_scene(catalog_dir),
                              ((60, 0, 0), 230, -35, 30)),
                             ("proto_pyvista_dual_matrix.png", dual_matrix_scene(),
                              ((25, 0, 5), 120, -40, 28))):
        pl = pv.Plotter(off_screen=not show, window_size=(1300, 800))
        pl.set_background("white")
        add_scene(pl, prims)
        z_down_camera(pl, *cam)
        pl.add_text(name.replace("proto_pyvista_", "").replace(".png", "").replace("_", " "),
                    font_size=10, color="black")
        if show:
            pl.enable_point_picking(lambda pt: print("picked", pt), show_message=True)
            pl.show()
        else:
            pl.screenshot(os.path.join(OUT, name))
            pl.close()
            print(os.path.join(OUT, name))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else None, show="--show" in sys.argv)
