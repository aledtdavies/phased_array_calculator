"""
Toolkit-independent 2D scene drawing for the ray-tracing view.

Everything here draws onto a plain matplotlib Axes, so it is shared by the
Tkinter GUI panels (plotting.py) and the standalone visualisation script,
and stays portable to other front ends (e.g. pogopy's Qt canvas).
"""
import matplotlib
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon
import numpy as np

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

_CONTACT_TOL_MM = 1e-3   # elements closer than this to z=0 count as contact


def _active_envelope_indices(probe):
    """
    Returns the element indices whose rays bound the active aperture:
    [(first, last)] for a single array, [(tx_first, tx_last), (rx_first,
    rx_last)] for dual probes (either entry omitted if that array has no
    active elements). Fixes the previous behaviour of always using
    element 0 / element -1, whose interface points are zero-filled when
    those elements are inactive.
    """
    act = np.asarray(probe.get_active_element_indices())
    if act.size == 0:
        return []
    if hasattr(probe, "array_separation"):
        n_half = probe.total_elements // 2
        pairs = []
        tx = act[act < n_half]
        rx = act[act >= n_half]
        if tx.size:
            pairs.append((int(tx[0]), int(tx[-1])))
        if rx.size:
            pairs.append((int(rx[0]), int(rx[-1])))
        return pairs
    return [(int(act[0]), int(act[-1]))]


def draw_elements(ax, elements_mm, probe, dim_idx):
    """Element markers: active coloured, inactive grey; Tx/Rx split for duals."""
    act = np.asarray(probe.get_active_element_indices())
    n_el = len(elements_mm)
    active_mask = np.zeros(n_el, dtype=bool)
    active_mask[act] = True

    ec = elements_mm[:, dim_idx]
    ez = elements_mm[:, 2]
    is_dual = hasattr(probe, "array_separation")

    if is_dual:
        n_half = n_el // 2
        halves = [
            (slice(0, n_half), COLOR_ELEMENT_TX, "Tx elements"),
            (slice(n_half, n_el), COLOR_ELEMENT_ACTIVE, "Rx elements"),
        ]
    else:
        halves = [(slice(0, n_el), COLOR_ELEMENT_ACTIVE, "Elements")]

    for sl, colour, label in halves:
        m = active_mask[sl]
        c = ec[sl]
        z = ez[sl]
        if m.any():
            ax.plot(c[m], z[m], "s", color=colour, markersize=4,
                    linestyle="none", zorder=5, label=label)
        if (~m).any():
            ax.plot(c[~m], z[~m], "s", markerfacecolor="none",
                    markeredgecolor=COLOR_ELEMENT_INACTIVE, markersize=4,
                    linestyle="none", zorder=5,
                    label="Inactive elements" if sl.start == 0 else None)


def draw_wedge_overlay(ax, elements_mm, wedge, dim_idx):
    """
    Draw the wedge body under the element footprint (schematic, derived
    from the wedge angle and transformed element positions) plus a
    schematic probe body and dimension annotations. Returns a list of
    (coord, z) points to include in the axis bounds.

    dim_idx 0 = X-Z view (sloped wedge silhouette), 1 = Y-Z view
    (rectangular silhouette).
    """
    ec = elements_mm[:, dim_idx]
    ez = elements_mm[:, 2]

    # Contact setup: no wedge body to draw
    if float(np.max(np.abs(ez))) < _CONTACT_TOL_MM:
        ax.text(float(np.min(ec)), -1.2, "Contact", fontsize=7,
                color=COLOR_PROBE_EDGE, zorder=6)
        return []

    span = float(np.max(ec) - np.min(ec))
    margin = max(2.0, 0.15 * span)
    bounds = []

    if dim_idx == 1:
        # Y-Z silhouette of the wedge block is a rectangle up to its
        # tallest edge.
        z_top = float(np.min(ez))
        verts = [(np.min(ec) - margin, 0.0), (np.max(ec) + margin, 0.0),
                 (np.max(ec) + margin, z_top), (np.min(ec) - margin, z_top)]
        ax.add_patch(Polygon(verts, closed=True, facecolor=COLOR_WEDGE_FACE,
                             edgecolor=COLOR_WEDGE_EDGE, alpha=0.16,
                             linewidth=1.0, zorder=1.5))
        return verts

    tan_a = float(np.tan(wedge.angle_rad))
    if tan_a > 1e-6:
        # Top-face silhouette line z(x) = -tan_a * x + c through the
        # highest elements (covers roof-angled duals too).
        c = float(np.min(ez + tan_a * ec))
        x_toe = c / tan_a       # z = 0 crossing of the top-face line
        x_back = float(np.max(ec)) + margin
        z_back = -tan_a * x_back + c

        # Cap a very long toe with a vertical front face so a shallow
        # wedge doesn't dominate the frame.
        x_front_cap = float(np.min(ec)) - 4.0 * margin
        if x_toe < x_front_cap:
            z_front = -tan_a * x_front_cap + c
            verts = [(x_front_cap, 0.0), (x_back, 0.0),
                     (x_back, z_back), (x_front_cap, z_front)]
        else:
            verts = [(x_toe, 0.0), (x_back, 0.0), (x_back, z_back)]
    else:
        # Flat wedge (delay line): rectangle
        z_top = float(np.min(ez))
        verts = [(np.min(ec) - margin, 0.0), (np.max(ec) + margin, 0.0),
                 (np.max(ec) + margin, z_top), (np.min(ec) - margin, z_top)]

    ax.add_patch(Polygon(verts, closed=True, facecolor=COLOR_WEDGE_FACE,
                         edgecolor=COLOR_WEDGE_EDGE, alpha=0.16,
                         linewidth=1.0, zorder=1.5, label="Wedge"))
    bounds.extend(verts)

    # Schematic probe body sitting on the top face over the element extent
    if tan_a > 1e-6:
        c_line = float(np.min(ez + tan_a * ec))
        z_at = lambda x: -tan_a * x + c_line
    else:
        z_top = float(np.min(ez))
        z_at = lambda x: z_top
    hp = max(3.0, 0.25 * abs(float(np.min(ez))))
    x0, x1 = float(np.min(ec)), float(np.max(ec))
    probe_verts = [(x0, z_at(x0)), (x1, z_at(x1)),
                   (x1, z_at(x1) - hp), (x0, z_at(x0) - hp)]
    ax.add_patch(Polygon(probe_verts, closed=True, facecolor=COLOR_PROBE_FACE,
                         edgecolor=COLOR_PROBE_EDGE, alpha=0.18,
                         linewidth=1.0, zorder=1.5, label="Probe (schematic)"))
    bounds.extend(probe_verts)

    # Dimension annotations: h1 drop line at element 1 and the wedge angle
    x_el1, z_el1 = float(ec[0]), float(ez[0])
    h1 = abs(z_el1)
    ax.plot([x_el1, x_el1], [0.0, z_el1], color=COLOR_WEDGE_EDGE,
            linewidth=0.9, zorder=4)
    ax.text(x_el1 + 0.8, z_el1 * 0.5, f"h1={h1:.1f} mm", fontsize=7,
            color=COLOR_WEDGE_EDGE, zorder=6)
    x_mid = 0.5 * (min(v[0] for v in verts) + max(v[0] for v in verts))
    z_top_wedge = min(v[1] for v in verts)
    ax.text(x_mid, z_top_wedge - 1.0,
            f"angle={wedge.angle_degrees:.1f}°", fontsize=7,
            color=COLOR_WEDGE_EDGE, ha="center", zorder=6)
    return bounds


def draw_law_rays(ax, elements_mm, int_pts_mm, target_mm, probe, dim_idx,
                  colour=None, alpha=1.0, show_all=False, label_focal=False):
    """
    Draw the envelope rays (first/last ACTIVE element of each array) for
    one focal law, plus the focal-point marker. Returns (coord, z) bound
    points.
    """
    is_dual = hasattr(probe, "array_separation")
    n_half = probe.total_elements // 2 if is_dual else None
    bounds = []

    for i0, i1 in _active_envelope_indices(probe):
        if colour is not None:
            c = colour
        elif is_dual:
            c = COLOR_RAY_TX if (n_half and i0 < n_half) else COLOR_RAY_RX
        else:
            c = COLOR_RAY
        for i in (i0, i1):
            p_el = elements_mm[i]
            p_int = int_pts_mm[i]
            ax.plot([p_el[dim_idx], p_int[dim_idx]], [p_el[2], p_int[2]],
                    color=c, alpha=alpha, linewidth=1, zorder=4)
            ax.plot([p_int[dim_idx], target_mm[dim_idx]],
                    [p_int[2], target_mm[2]],
                    color=c, alpha=alpha, linewidth=1, zorder=4)
            bounds.append((float(p_int[dim_idx]), float(p_int[2])))

    marker_c = colour if colour is not None else COLOR_ELEMENT_ACTIVE
    ax.plot(target_mm[dim_idx], target_mm[2],
            marker="o" if show_all else "x", color=marker_c,
            markersize=3 if show_all else 8, zorder=6,
            label="Focal point" if label_focal else None)
    bounds.append((float(target_mm[dim_idx]), float(target_mm[2])))
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


def draw_projection(ax, solver, get_law, indices, dim_idx, wave_type,
                    show_all, component_thickness_mm=0.0):
    """
    Draw one full projection (geometry + rays for `indices`).
    `get_law(idx)` must return (interface_points_mm, target_mm).
    """
    elements_mm = solver.wedge.get_transformed_elements(solver.probe) * 1000
    probe = solver.probe

    bounds = [(float(c), float(z))
              for c, z in zip(elements_mm[:, dim_idx], elements_mm[:, 2])]
    bounds.extend(draw_wedge_overlay(ax, elements_mm, solver.wedge, dim_idx))
    draw_elements(ax, elements_mm, probe, dim_idx)

    cmap = matplotlib.colormaps[LAW_CMAP]
    norm = mcolors.Normalize(vmin=0, vmax=max(1, len(indices) - 1))
    for j, idx in enumerate(indices):
        int_pts_mm, target_mm = get_law(idx)
        colour = cmap(norm(idx)) if show_all else None
        alpha = 0.5 if show_all else 1.0
        bounds.extend(draw_law_rays(
            ax, elements_mm, int_pts_mm, target_mm, probe, dim_idx,
            colour=colour, alpha=alpha, show_all=show_all,
            label_focal=(j == 0)))

    finish_projection(ax, bounds, dim_idx, wave_type,
                      component_thickness_mm=component_thickness_mm,
                      show_legend=(dim_idx == 0))
