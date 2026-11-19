"""
PROTOTYPE: static (report/export) renderer of the scene model with matplotlib.
Writes docs/plans/images/proto_coverage_field.png.

    python render_static.py [buildFE/catalog folder]
"""
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from scene_model import build_scene, constant_depth_sweep, cw_field_xz, demo_setup, single_v_weld

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "plans", "images"))

STYLE = {
    "wedge": dict(fc="#22c55e", ec="#15803d", alpha=0.15),
    "weld": dict(fc="#f59e0b", ec="#b45309", alpha=0.25),
    "coverage-leg1": dict(fc="#2563eb", alpha=0.10),
    "coverage-leg2": dict(fc="#7c3aed", alpha=0.08),
    "coverage-leg3": dict(fc="#db2777", alpha=0.06),
}


def draw_xz(ax, prims, thickness_mm, field=None, grid_mm=None):
    if field is not None:
        db = 20 * np.log10(field / field.max())
        im = ax.pcolormesh(grid_mm[0], grid_mm[1], np.clip(db, -30, 0), cmap="turbo",
                           vmin=-30, vmax=0, shading="auto", zorder=0)
    ax.axhspan(0, thickness_mm, color="#94a3b8", alpha=0.12 if field is None else 0, zorder=0)
    for p in prims:
        xz = p.coords[:, [0, 2]]
        if p.kind == "prism":
            ax.add_patch(Polygon(xz, closed=True, lw=1, label=p.label, zorder=2, **STYLE[p.role]))
        elif p.kind == "polygon":
            for k in range(p.meta["n_quads"]):
                ax.add_patch(Polygon(xz[4 * k:4 * k + 4], closed=True, lw=0, zorder=1,
                                     label=p.label if k == 0 else None, **STYLE[p.role]))
        elif p.kind == "segments" and field is None:
            from matplotlib.collections import LineCollection
            ax.add_collection(LineCollection(xz.reshape(-1, 2, 2), lw=0.4, color="#1d4ed8",
                                             alpha=0.5, zorder=3))
        elif p.kind == "polyline":
            ax.plot(xz[:, 0], xz[:, 1], "--", color="k", lw=1.2, label=p.label, zorder=4)
        elif p.role == "element-active":
            ax.plot(xz[:, 0], xz[:, 1], "s", ms=2.5, color="#dc2626", label=p.label, zorder=5)
        elif p.role == "element-inactive":
            ax.plot(xz[:, 0], xz[:, 1], "s", ms=2.5, mfc="none", mec="#94a3b8", zorder=5)
        elif p.role == "focus":
            ax.plot(xz[:, 0], xz[:, 1], "x", ms=8, mew=2, color="w" if field is not None else "k",
                    label=p.label, zorder=6)
    ax.axhline(0, color="k", lw=1.5, zorder=3)
    ax.axhline(thickness_mm, color="#334155", lw=1.2, zorder=3)
    ax.set_aspect("equal")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Z depth (mm)")
    ax.grid(True, ls=":", alpha=0.4)
    return im if field is not None else None


def main(catalog_dir=None):
    os.makedirs(OUT, exist_ok=True)
    solver, outline, freq = demo_setup(catalog_dir)
    T = 0.025
    sweep = constant_depth_sweep(solver, np.arange(40, 71, 2.5), 0.020, wave="shear")
    cur = len(sweep) // 2
    _, entry, focus, law = sweep[cur]
    weld = single_v_weld(entry[0] + 0.040, T)
    prims = build_scene(solver, sweep, cur, T, outline_xz=outline, weld_xz=weld, n_legs=2)

    fig = Figure(figsize=(13, 5.6), dpi=110)
    ax1, ax2 = fig.add_subplot(121), fig.add_subplot(122)
    draw_xz(ax1, prims, T * 1e3)
    ax1.set_ylim(T * 1e3 + 4, -48)
    ax1.set_xlim(-5, 125)
    ax1.set_title("Coverage of a 40-70° S-scan, direct and first skip, over a single-V weld",
                  fontsize=9)
    ax1.legend(loc="lower right", fontsize=7, framealpha=0.85)

    xs = np.linspace(0.005, 0.11, 360)
    zs = np.linspace(0.0005, T, 110)
    f = cw_field_xz(solver, law, freq, xs, zs, wave="shear")
    im = draw_xz(ax2, [p for p in prims if p.role in ("wedge", "element-active", "element-inactive",
                                                       "focus", "weld")],
                 T * 1e3, field=f, grid_mm=(xs * 1e3, zs * 1e3))
    # Check: the field's peak should sit at (or near) the focus.
    iz, ix = np.unravel_index(np.argmax(f), f.shape)
    print(f"field peak at X={xs[ix]*1e3:.1f}, Z={zs[iz]*1e3:.1f} mm; "
          f"focus at X={focus[0]*1e3:.1f}, Z={focus[2]*1e3:.1f} mm")
    ax2.set_ylim(T * 1e3 + 4, -48)
    ax2.set_xlim(-5, 125)
    ax2.set_title(f"ILLUSTRATIVE CW field, {freq / 1e6:.2f} MHz, law {cur + 1} "
                  f"({sweep[cur][0]:.1f}° SW, focus 20 mm deep)" "\n"
                  "not a validated model", fontsize=9)
    fig.colorbar(im, ax=ax2, shrink=0.6, label="dB (floor -30)")
    fig.suptitle("Prototype: one scene model, static matplotlib renderer "
                 "(buildFE SA2-N55S wedge + 2.25L64-A2, elements 17-48)", fontsize=10)
    fig.tight_layout()
    path = os.path.join(OUT, "proto_coverage_field.png")
    fig.savefig(path)
    print(path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
