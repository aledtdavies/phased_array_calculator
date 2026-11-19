"""
PROTOTYPE (plan step 1): a renderer-independent scene model.

The solver and focal rules produce *primitives* in the global frame (mm; X along the
wedge, Y across, Z down into the component, Z = 0 the interface). Renderers
(matplotlib for export, pyqtgraph for live 2D, PyVista for 3D) only draw primitives,
so every view shows the same geometry and the geometry is testable without a GUI.

Throwaway: names and fields are for the plan's discussion, not a frozen API.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "python")))

from delay_law import DelayLaw          # noqa: E402
from material import Material           # noqa: E402
from probe import create_probe_assembly  # noqa: E402
from wedge import Wedge                 # noqa: E402


@dataclass
class Prim:
    """One drawable thing. coords: (N, 3) mm in the global frame."""
    kind: str            # points | polyline | segments | polygon | prism | plane
    coords: np.ndarray
    role: str            # style key: element-active, ray, coverage-leg1, weld, ...
    label: str = ""
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Focal rule (constant depth) and central rays: the logic app.py holds today
# ---------------------------------------------------------------------------
def constant_depth_sweep(solver, angles_deg, depth, skew_deg=0.0, wave="longitudinal"):
    """Laws for a constant-depth sweep; returns [(angle, entry_point, focus, law)]."""
    cx, cy, cz = solver.aperture_centre()
    vw = solver.wedge.velocity
    vm = solver.material.velocity_shear if wave == "shear" else solver.material.velocity_longitudinal
    s = np.radians(skew_deg)
    out = []
    for a in angles_deg:
        b = np.radians(a)
        sa = vw / vm * np.sin(b)
        if abs(sa) >= 1:
            continue
        lead = abs(cz) * np.tan(np.arcsin(sa))
        entry = np.array([cx + lead * np.cos(s), cy + lead * np.sin(s), 0.0])
        d = np.array([np.sin(b) * np.cos(s), np.sin(b) * np.sin(s), np.cos(b)])
        focus = entry + d * depth / np.cos(b)
        out.append((a, entry, focus, solver.calculate_law(*focus, wave_type=wave)))
    return out


def skip_legs(entry, angle_deg, skew_deg, thickness, n_legs):
    """
    Central-ray legs in a flat plate of the given thickness (m): leg 1 to the backwall,
    leg 2 back to the scanning surface, ... Specular reflection, no mode conversion
    (ASSUMPTION for display: the same mode after each reflection).
    """
    b, s = np.radians(angle_deg), np.radians(skew_deg)
    d = np.array([np.sin(b) * np.cos(s), np.sin(b) * np.sin(s), np.cos(b)])
    pts = [np.asarray(entry, float)]
    for _ in range(n_legs):
        p = pts[-1]
        z_target = thickness if d[2] > 0 else 0.0
        t = (z_target - p[2]) / d[2]
        pts.append(p + t * d)
        d = d * np.array([1, 1, -1])
    return np.array(pts)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------
def single_v_weld(x_centre, thickness, included_deg=60.0, root_gap=0.002, land=0.0015):
    """X-Z outline (m) of a single-V butt weld preparation, opening upwards at Z = 0."""
    half = np.radians(included_deg / 2)
    top = root_gap / 2 + (thickness - land) * np.tan(half)
    return np.array([[x_centre - top, 0], [x_centre + top, 0],
                     [x_centre + root_gap / 2, thickness - land],
                     [x_centre + root_gap / 2, thickness], [x_centre - root_gap / 2, thickness],
                     [x_centre - root_gap / 2, thickness - land]])


def build_scene(solver, sweep, current, thickness, outline_xz=None, weld_xz=None,
                n_legs=2, max_rays=48, skew_deg=0.0):
    """Primitives for one law (`current` index into `sweep`) and the whole sweep."""
    mm = 1e3
    probe = solver.probe
    el = solver.wedge.get_transformed_elements(probe) * mm
    act = probe.get_active_element_indices()
    on = np.zeros(len(el), bool)
    on[act] = True
    if hasattr(probe, "array_separation"):
        tx = np.arange(len(el)) < len(el) // 2
        prims = [Prim("points", el[on & tx], "element-tx", "Tx elements"),
                 Prim("points", el[on & ~tx], "element-active", "Rx elements")]
    else:
        prims = [Prim("points", el[on], "element-active", "Active elements")]
    prims.append(Prim("points", el[~on], "element-inactive", "Inactive elements"))

    y_half = max(6.0, 0.6 * np.ptp(el[:, 1]) + 4, 0.15 * np.ptp(el[:, 0]))
    y_mid = el[:, 1].mean()
    if outline_xz is not None:
        prims.append(Prim("prism", np.c_[outline_xz[:, 0] * mm, np.zeros(len(outline_xz)),
                                         outline_xz[:, 1] * mm],
                          "wedge", "Wedge (catalogue)",
                          {"y0": y_mid - y_half, "y1": y_mid + y_half}))
    if weld_xz is not None:
        prims.append(Prim("prism", np.c_[weld_xz[:, 0] * mm, np.zeros(len(weld_xz)),
                                         weld_xz[:, 1] * mm],
                          "weld", "Weld preparation",
                          {"y0": y_mid - 3 * y_half, "y1": y_mid + 3 * y_half}))

    # Current law: element -> interface -> focus, decimated
    a, entry, focus, law = sweep[current]
    pick = act if len(act) <= max_rays else act[np.unique(np.linspace(0, len(act) - 1, max_rays).round().astype(int))]
    ip = law["interface_points"] * mm
    seg = []
    for i in pick:
        seg += [el[i], ip[i], ip[i], focus * mm]
    prims.append(Prim("segments", np.array(seg), "ray", f"Rays, law {current + 1}"))
    prims.append(Prim("points", (focus * mm)[None], "focus", "Focal point"))
    prims.append(Prim("points", np.array([f * mm for _, _, f, _ in sweep]), "focus-sweep",
                      "Focal points (sweep)", {"law": np.arange(len(sweep))}))

    # Coverage: central rays of every law, leg by leg, filled between neighbours
    paths = [skip_legs(e, ang, skew_deg, thickness, n_legs) * mm for ang, e, _, _ in sweep]
    for leg in range(n_legs):
        quads = []
        for p, q in zip(paths[:-1], paths[1:]):
            quads.append(np.array([p[leg], p[leg + 1], q[leg + 1], q[leg]]))
        prims.append(Prim("polygon", np.concatenate(quads), f"coverage-leg{leg + 1}",
                          ["Coverage, direct", "Coverage, first skip", "Coverage, second skip"][leg],
                          {"n_quads": len(quads)}))
    prims.append(Prim("polyline", paths[current], "central-ray", "Central ray (with skips)"))

    # Component: a plate block over the drawn extent (Z from the interface to the backwall)
    allp = np.vstack([el, np.concatenate(paths)])
    x0, x1 = allp[:, 0].min() - 5, allp[:, 0].max() + 5
    yy0 = min(allp[:, 1].min(), y_mid - 2 * y_half) - 3
    yy1 = max(allp[:, 1].max(), y_mid + 2 * y_half) + 3
    prims.append(Prim("box", np.array([[x0, yy0, 0.0], [x1, yy1, thickness * mm]]),
                      "component", "Component"))
    return prims


# ---------------------------------------------------------------------------
# Illustrative CW field (NOT a validated model)
# ---------------------------------------------------------------------------
def cw_field_xz(solver, law, freq, xs, zs, wave="longitudinal"):
    """
    |sum_e A_e exp(-i w (d_e + T_e(p)))| over an X-Z grid (m), 2D, at one frequency.
    T_e(p): Fermat time element -> interface -> p (bisection on the monotone Snell
    residual). A_e: 1/sqrt(path) spreading only; no transmission coefficients, element
    directivity or attenuation. ILLUSTRATION of what a field view could show; a real
    one should come from a validated model (see the plan, check buildFE/imageFE first).
    """
    el = solver.wedge.get_transformed_elements(solver.probe)
    act = solver.probe.get_active_element_indices()
    v1 = solver.wedge.velocity
    v2 = solver.material.velocity_shear if wave == "shear" else solver.material.velocity_longitudinal
    X, Z = np.meshgrid(xs, zs)
    w = 2 * np.pi * freq
    acc = np.zeros(X.shape, complex)
    for i in act:
        xe, h = el[i, 0], -el[i, 2]
        lo, hi = np.minimum(xe, X), np.maximum(xe, X)
        for _ in range(50):
            u = 0.5 * (lo + hi)
            r = (u - xe) / (v1 * np.hypot(u - xe, h)) - (X - u) / (v2 * np.hypot(X - u, Z))
            hi = np.where(r > 0, u, hi)
            lo = np.where(r > 0, lo, u)
        u = 0.5 * (lo + hi)
        l1, l2 = np.hypot(u - xe, h), np.hypot(X - u, Z)
        t = l1 / v1 + l2 / v2
        acc += np.exp(-1j * w * (law["delays"][i] + t)) / np.sqrt(l1 + l2 * v2 / v1)
    return np.abs(acc)


def demo_setup(catalog_dir=None):
    """The buildFE SA2-N55S wedge with the 2.25L64 probe (values as in buildFE's catalogue)."""
    from catalog import Catalog
    if catalog_dir:
        w = Catalog(os.path.join(catalog_dir, "wedges.json")).wedge("evident-SA2-N55S")
        p = Catalog(os.path.join(catalog_dir, "probes.json")).probe("evident-2.25L64-A2")
        wedge = Wedge(w.angle_deg, w.height_at_element1, w.velocity, w.probe_offset_x)
        outline = np.array(w.outline) * [1, -1]
        n, pitch, freq = p.num_elements, p.pitch, p.frequency
    else:   # same values typed in, when no buildFE checkout is beside this repo
        wedge = Wedge(36.0, 0.005, 2337.0, 0.004)
        toe = 0.005 - 0.004 * np.tan(np.radians(36))
        cap = 0.004 + (0.043 - 0.005) / np.tan(np.radians(36))
        outline = np.array([[0, 0], [0.069, 0], [0.069, -0.043], [cap, -0.043], [0, -toe]])
        n, pitch, freq = 64, 0.00075, 2.25e6
    probe = create_probe_assembly("Linear", n, pitch, freq, start_element=17, num_active_elements=32)
    return DelayLaw(probe, wedge, Material(5920.0, 3240.0)), outline, freq
