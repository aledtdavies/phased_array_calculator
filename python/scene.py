"""
matplotlib renderer of the scene model (scene_model.py): the 2D X-Z / Y-Z projections and the
3D view used by the Tk GUI panels and the standalone visualisation script, plus the aperture
delay maps. Geometry is decided in scene_model; this module only styles and draws it.
Everything draws onto a plain matplotlib Axes or Figure, so it is toolkit-independent.
"""
import matplotlib
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon
import numpy as np

from scene_model import (build_scene, decimate_rays, user_element_numbers,  # noqa: F401 (re-exported)
                         wedge_silhouette_xz)

# ---------------------------------------------------------------------------
# Shared scene styling
# ---------------------------------------------------------------------------
COLOR_ELEMENT_ACTIVE = "#dc2626"      # red squares (single probe / Rx array)
COLOR_ELEMENT_TX = "#2563eb"          # blue squares (Tx array of dual probes)
COLOR_ELEMENT_INACTIVE = "#94a3b8"    # grey squares (outside sub-aperture)
COLOR_RAY = "#2563eb"
COLOR_RAY_TX = "tab:blue"
COLOR_RAY_RX = "tab:red"
COLOR_WEDGE_FACE = "#22c55e"
COLOR_WEDGE_EDGE = "#15803d"
COLOR_PROBE_FACE = "#64748b"
COLOR_PROBE_EDGE = "#334155"
COLOR_MATERIAL = "#94a3b8"
COLOR_BACKWALL = "#334155"
LAW_CMAP = "viridis"

ELEMENT_COLOUR = {"single": COLOR_ELEMENT_ACTIVE, "tx": COLOR_ELEMENT_TX, "rx": COLOR_ELEMENT_ACTIVE}
ELEMENT_LABEL = {"single": "Elements", "tx": "Tx elements", "rx": "Rx elements"}
RAY_COLOUR = {"single": COLOR_RAY, "tx": COLOR_RAY_TX, "rx": COLOR_RAY_RX}
WEDGE_LABEL = {"catalogue": "Wedge (catalogue)", "schematic": "Wedge (schematic)"}


# ---------------------------------------------------------------------------
# 2D projections
# ---------------------------------------------------------------------------
def _draw_elements_2d(ax, scene, dim_idx):
    """Element markers: active coloured, inactive grey; Tx/Rx split for duals."""
    for p in scene.find("element"):
        c, z = p.coords[:, dim_idx], p.coords[:, 2]
        if p.meta["active"]:
            ax.plot(c, z, "s", color=ELEMENT_COLOUR[p.meta["array"]], markersize=4,
                    linestyle="none", zorder=5, label=ELEMENT_LABEL[p.meta["array"]])
        else:
            ax.plot(c, z, "s", markerfacecolor="none",
                    markeredgecolor=COLOR_ELEMENT_INACTIVE, markersize=4,
                    linestyle="none", zorder=5,
                    label="Inactive elements" if p.meta["array"] in ("single", "tx") else None)


def _draw_wedge_2d(ax, scene, dim_idx):
    """
    Wedge body, schematic probe body and dimensions. Returns (coord, z) bound points.
    X-Z: the wedge polygon (catalogue outline or schematic). Y-Z: a rectangle over the
    element footprint up to the tallest of the elements and the catalogue outline.
    """
    el = np.vstack([p.coords for p in scene.find("element")])
    ec, ez = el[:, dim_idx], el[:, 2]
    if scene.contact:
        p = scene.one("contact")
        ax.text(float(p.coords[0, dim_idx]), float(p.coords[0, 2]), p.meta["text"], fontsize=7,
                color=COLOR_PROBE_EDGE, zorder=6)
        return []
    wedge = scene.one("wedge")
    if dim_idx == 1:
        span = float(np.max(ec) - np.min(ec))
        margin = max(2.0, 0.15 * span)
        z_top = float(np.min(ez))
        if wedge.meta["source"] == "catalogue":
            z_top = min(z_top, float(np.min(wedge.coords[:, 2])))
        verts = [(np.min(ec) - margin, 0.0), (np.max(ec) + margin, 0.0),
                 (np.max(ec) + margin, z_top), (np.min(ec) - margin, z_top)]
        ax.add_patch(Polygon(verts, closed=True, facecolor=COLOR_WEDGE_FACE,
                             edgecolor=COLOR_WEDGE_EDGE, alpha=0.16,
                             linewidth=1.0, zorder=1.5))
        return verts

    verts = [(float(x), float(z)) for x, _, z in wedge.coords]
    ax.add_patch(Polygon(verts, closed=True, facecolor=COLOR_WEDGE_FACE,
                         edgecolor=COLOR_WEDGE_EDGE, alpha=0.16,
                         linewidth=1.0, zorder=1.5, label=WEDGE_LABEL[wedge.meta["source"]]))
    body = [(float(x), float(z)) for x, _, z in scene.one("probe-body").coords]
    ax.add_patch(Polygon(body, closed=True, facecolor=COLOR_PROBE_FACE,
                         edgecolor=COLOR_PROBE_EDGE, alpha=0.18,
                         linewidth=1.0, zorder=1.5, label="Probe (schematic)"))
    dim = scene.one("dimension")
    ax.plot(dim.coords[:, 0], dim.coords[:, 2], color=COLOR_WEDGE_EDGE, linewidth=0.9, zorder=4)
    ax.text(*dim.meta["text_at"], dim.meta["text"], fontsize=7, color=COLOR_WEDGE_EDGE, zorder=6)
    ang = scene.one("wedge-angle")
    ax.text(float(ang.coords[0, 0]), float(ang.coords[0, 2]), ang.meta["text"], fontsize=7,
            color=COLOR_WEDGE_EDGE, ha="center", zorder=6)
    return verts + body


def _draw_law_2d(ax, scene, law, dim_idx, colour=None, alpha=1.0, show_all=False,
                 label_focal=False):
    """Envelope rays and focus of one law. Returns (coord, z) bound points."""
    bounds = []
    for p in scene.find("envelope-ray", law=law):
        c = colour if colour is not None else RAY_COLOUR[p.meta["array"]]
        el, ip, _, tg = p.coords
        ax.plot([el[dim_idx], ip[dim_idx]], [el[2], ip[2]], color=c, alpha=alpha,
                linewidth=1, zorder=4)
        ax.plot([ip[dim_idx], tg[dim_idx]], [ip[2], tg[2]], color=c, alpha=alpha,
                linewidth=1, zorder=4)
        bounds.append((float(ip[dim_idx]), float(ip[2])))
    tg = scene.one("focus", law=law).coords[0]
    marker_c = colour if colour is not None else COLOR_ELEMENT_ACTIVE
    ax.plot(tg[dim_idx], tg[2], marker="o" if show_all else "x", color=marker_c,
            markersize=3 if show_all else 8, zorder=6,
            label="Focal point" if label_focal else None)
    bounds.append((float(tg[dim_idx]), float(tg[2])))
    return bounds


def finish_projection(ax, bounds, dim_idx, wave_type,
                      component_thickness_mm=0.0, show_legend=True):
    """
    Interface line, component fill/backwall, explicit padded framing,
    labels, and legend for one projection axes. `bounds` is a list of
    (coord, z) points accumulated from every drawn artist.
    """
    ax.axhline(0, color="k", linestyle="-", linewidth=2, zorder=3,
               label="Interface")

    xs = [b[0] for b in bounds]
    zs = [b[1] for b in bounds]
    if component_thickness_mm > 0:
        zs.append(component_thickness_mm)
    if not xs:
        xs, zs = [0.0, 10.0], [0.0, 10.0]

    xmin, xmax = min(xs), max(xs)
    zmin, zmax = min(zs), max(zs)
    xpad = max(2.0, (xmax - xmin) * 0.08)
    zpad = max(2.0, (zmax - zmin) * 0.10)
    x0, x1 = xmin - xpad, xmax + xpad
    z_top, z_bot = zmin - zpad, zmax + zpad

    # Component fill: to the backwall if a thickness is set, else to the
    # bottom of the frame.
    fill_bot = component_thickness_mm if component_thickness_mm > 0 else z_bot
    ax.fill_between([x0, x1], 0, fill_bot, color=COLOR_MATERIAL, alpha=0.15,
                    zorder=1, label="Component")
    if component_thickness_mm > 0:
        ax.axhline(component_thickness_mm, color=COLOR_BACKWALL,
                   linestyle="-", linewidth=1.5, zorder=2, label="Backwall")

    ax.set_xlim(x0, x1)
    ax.set_ylim(z_bot, z_top)   # inverted: depth increases downward
    ax.set_aspect("equal")

    ax.set_title(f"Ray Tracing {'X-Z' if dim_idx == 0 else 'Y-Z'} ({wave_type})")
    ax.set_xlabel("X (mm)" if dim_idx == 0 else "Y (mm)")
    ax.set_ylabel("Z Depth (mm)")
    ax.grid(True, linestyle="--", alpha=0.5)
    if show_legend:
        ax.legend(loc="upper right", fontsize=7, framealpha=0.7)


def draw_scene_projection(ax, scene, indices, dim_idx, wave_type, show_all,
                          component_thickness_mm=0.0):
    """Draw one projection (dim_idx 0 = X-Z, 1 = Y-Z) of a Scene holding the laws in `indices`."""
    bounds = [(float(c), float(z)) for p in scene.find("element")
              for c, z in zip(p.coords[:, dim_idx], p.coords[:, 2])]
    bounds.extend(_draw_wedge_2d(ax, scene, dim_idx))
    _draw_elements_2d(ax, scene, dim_idx)

    cmap = matplotlib.colormaps[LAW_CMAP]
    norm = mcolors.Normalize(vmin=0, vmax=max(1, len(indices) - 1))
    for j, idx in enumerate(indices):
        bounds.extend(_draw_law_2d(ax, scene, idx, dim_idx,
                                   colour=cmap(norm(idx)) if show_all else None,
                                   alpha=0.5 if show_all else 1.0, show_all=show_all,
                                   label_focal=(j == 0)))
    finish_projection(ax, bounds, dim_idx, wave_type,
                      component_thickness_mm=component_thickness_mm,
                      show_legend=(dim_idx == 0))


def draw_projection(ax, solver, get_law, indices, dim_idx, wave_type,
                    show_all, component_thickness_mm=0.0, outline_mm=None):
    """
    Draw one full projection (geometry + rays for `indices`).
    `get_law(idx)` must return (interface_points_mm, target_mm).
    """
    scene = build_scene(solver, get_law, indices, outline_mm=outline_mm)
    draw_scene_projection(ax, scene, indices, dim_idx, wave_type, show_all,
                          component_thickness_mm=component_thickness_mm)


# ---------------------------------------------------------------------------
# 3D scene
# ---------------------------------------------------------------------------
VIEW_PRESETS = {
    # name: (elev, azim) for mplot3d's view_init; Z is drawn increasing downward.
    "Iso": (25.0, -60.0),
    "X-Z": (0.0, -90.0),     # looking along +Y
    "Y-Z": (0.0, 0.0),       # looking along -X
    "Top": (90.0, -90.0),
}


def _wedge_faces_3d(xz_verts, y0, y1):
    """Faces of a prism: the X-Z polygon extruded across Y from y0 to y1 (mm)."""
    front = [(x, y0, z) for x, z in xz_verts]
    back = [(x, y1, z) for x, z in xz_verts]
    faces = [front, back]
    n = len(xz_verts)
    for k in range(n):
        a, b = xz_verts[k], xz_verts[(k + 1) % n]
        faces.append([(a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1])])
    return faces


def draw_scene_3d_from(ax, scene, wave_type, component_thickness_mm=0.0, show_locus=True):
    """
    Draw a Scene built with a current law on a mplot3d Axes (mm, global frame, Z drawn
    increasing downward): wedge prism, interface and backwall planes, elements, the current
    law's rays and interface points, the sweep's foci and the current focus.
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

    elements = [p for p in scene.find("element")]
    rays = scene.find("ray")
    law = rays[0].meta["law"] if rays else scene.find("focus")[0].meta["law"]
    target = scene.one("focus", law=law).coords[0]
    sweep = scene.find("focus-sweep")
    fp = sweep[0].coords if sweep else None

    pts = [np.vstack([p.coords for p in elements]), target[None, :]]
    all_ip = scene.find("interface-point-all")
    if all_ip:
        pts.append(all_ip[0].coords)
    if fp is not None:
        pts.append(fp)
    faces = None
    wedges = scene.find("wedge")
    if wedges:
        w = wedges[0]
        faces = _wedge_faces_3d([(float(x), float(z)) for x, _, z in w.coords],
                                w.meta["y0"], w.meta["y1"])
        pts.append(np.array([p for f in faces for p in f]))

    allp = np.vstack(pts)
    lo, hi = allp.min(axis=0), allp.max(axis=0)
    if component_thickness_mm > 0:
        hi[2] = max(hi[2], component_thickness_mm)
    pad = np.maximum(2.0, 0.08 * (hi - lo))
    lo, hi = lo - pad, hi + pad

    def plane(z, colour, alpha, label):
        quad = [[(lo[0], lo[1], z), (hi[0], lo[1], z), (hi[0], hi[1], z), (lo[0], hi[1], z)]]
        ax.add_collection3d(Poly3DCollection(quad, facecolor=colour, alpha=alpha,
                                             edgecolor=colour, linewidth=0.6, label=label))
    plane(0.0, COLOR_MATERIAL, 0.18, "Interface")
    if component_thickness_mm > 0:
        plane(component_thickness_mm, COLOR_BACKWALL, 0.10, "Backwall")
    if faces is not None:
        ax.add_collection3d(Poly3DCollection(
            faces, facecolor=COLOR_WEDGE_FACE, alpha=0.10, edgecolor=COLOR_WEDGE_EDGE,
            linewidth=0.5, label=WEDGE_LABEL[wedges[0].meta["source"]]))

    # Elements: active coloured (Tx/Rx split for duals), inactive hollow grey
    inactive_labelled = False
    for p in elements:
        if p.meta["active"]:
            ax.scatter(*p.coords.T, marker="s", s=10, color=ELEMENT_COLOUR[p.meta["array"]],
                       depthshade=False, label=ELEMENT_LABEL[p.meta["array"]])
        else:
            ax.scatter(*p.coords.T, marker="s", s=10, facecolors="none",
                       edgecolors=COLOR_ELEMENT_INACTIVE, depthshade=False,
                       label=None if inactive_labelled else "Inactive elements")
            inactive_labelled = True

    # Rays of the current law, in element order (Tx before Rx)
    n_rays, n_active = 0, 0
    if rays:
        segs = np.concatenate([p.coords for p in rays]).reshape(-1, 2, 3)
        cols = [RAY_COLOUR[p.meta["array"]] for p in rays for _ in range(len(p.coords) // 2)]
        ax.add_collection3d(Line3DCollection(segs, colors=cols, linewidths=0.6, alpha=0.7))
        ip = scene.one("interface-point", law=law)
        ax.scatter(*ip.coords.T, s=4, color="k", depthshade=False, label="Interface points")
        n_rays = sum(len(p.meta["elements"]) for p in rays)
        n_active = rays[0].meta["n_active"]

    if show_locus and fp is not None and len(fp) > 1:
        ax.scatter(*fp.T, c=np.arange(len(fp)), cmap=LAW_CMAP, s=8,
                   depthshade=False, label="Focal points (sweep)")
    ax.scatter(*target.T, marker="x", s=60, color="k", depthshade=False,
               label="Focal point")

    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(hi[2], lo[2])               # depth increases downward
    ax.set_box_aspect(tuple(hi - lo))       # equal scale on all axes
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z depth (mm)")
    note = f", rays from {n_rays} of {n_active} active elements" if n_rays < n_active else ""
    ax.set_title(f"3D ray scene ({wave_type}{note})", fontsize=10)
    ax.legend(loc="upper left", fontsize=7, framealpha=0.7)


def draw_scene_3d(ax, solver, law, focal_points_mm, current_idx, wave_type,
                  component_thickness_mm=0.0, outline_mm=None, max_rays=48,
                  show_locus=True):
    """
    3D view of one focal law on a mplot3d Axes (all mm, global frame: Z > 0
    in the component, drawn increasing downward).

    law: (interface_points_mm, target_mm) for the selected law.
    focal_points_mm: (N, 3) focal points of every law, drawn as the sweep
    locus coloured by law index; current_idx is the selected law.
    Rays run element -> interface point -> focus for every active element
    (an even subset of at most max_rays, ends kept, for large apertures).
    The wedge body is the catalogue outline or the schematic silhouette,
    extruded across the element footprint in Y; roof angles tilt the
    elements but are not shown in the body.
    """
    scene = build_scene(solver, lambda i: law, [], outline_mm=outline_mm, current=current_idx,
                        max_rays=max_rays, sweep_focal_mm=focal_points_mm)
    draw_scene_3d_from(ax, scene, wave_type, component_thickness_mm=component_thickness_mm,
                       show_locus=show_locus)


# ---------------------------------------------------------------------------
# Aperture delay map (matrix probes)
# ---------------------------------------------------------------------------
def draw_aperture_maps(fig, probe, delays_us, vmax=None, title=""):
    """
    One heat map per array of the delay (µs) over the element grid, X across
    and Y up, inactive elements grey (NaN). Element numbers in the user's
    convention are written on the cells when the grid is small enough to read.
    """
    nx, ny = probe.num_elements, probe.num_elements_y
    per = nx * ny
    n_arrays = probe.total_elements // per
    numbers = user_element_numbers(probe)
    cmap = matplotlib.colormaps[LAW_CMAP].copy()
    cmap.set_bad("#e2e8f0")
    delays_us = np.asarray(delays_us, dtype=float)
    finite = delays_us[np.isfinite(delays_us)]
    if vmax is None or not np.isfinite(vmax) or vmax <= 0:
        vmax = float(finite.max()) if finite.size and finite.max() > 0 else 1.0
    names = ["Tx array", "Rx array"] if n_arrays == 2 else ["Aperture"]
    axes, im = [], None
    for b in range(n_arrays):
        ax = fig.add_subplot(1, n_arrays, b + 1)
        grid = delays_us[b * per:(b + 1) * per].reshape(nx, ny).T     # rows = Y, cols = X
        im = ax.imshow(np.ma.masked_invalid(grid), origin="lower", cmap=cmap,
                       vmin=0.0, vmax=vmax, aspect="equal",
                       extent=(0.5, nx + 0.5, 0.5, ny + 0.5))
        if nx * ny <= 256:
            nums = numbers[b * per:(b + 1) * per].reshape(nx, ny)
            for ix in range(nx):
                for iy in range(ny):
                    v = grid[iy, ix]
                    colour = ("#475569" if not np.isfinite(v)
                              else ("k" if v > 0.6 * vmax else "w"))
                    ax.text(ix + 1, iy + 1, str(nums[ix, iy]), ha="center", va="center",
                            fontsize=6, color=colour)
        ax.set_xlabel("X element index")
        ax.set_ylabel("Y element index")
        ax.set_title(names[b], fontsize=9)
        axes.append(ax)
    fig.colorbar(im, ax=axes, label="Delay (µs)", shrink=0.8)
    if title:
        fig.suptitle(title, fontsize=10)
    return axes
