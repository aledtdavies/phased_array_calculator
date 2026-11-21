"""
Plan step 6 finish check: the calculator's beam field against buildFE's FE solve of the same
beam (Task 125, case f74b8bab65), measured by one rule (beam_metrics) against the tolerances
fixed in docs/plans/PLAN-2026-11-qt-vtk-migration.md before this script was first run.

    python validation/beam_field/compare_buildfe.py <field_products.h5> [out_dir]

field_products.h5 is in buildFE's returned bundle
transfer/RETURN_cab02_wedge_beam_20261007_20261007_103843/results.zip
(cab02_wedge_beam/cases/f74b8bab65/field_products.h5); it is not copied into this repository.

Frames: the FE map is in buildFE's plate frame (x along the surface, wedge origin at plate
x = 10 mm); the calculator's X is the wedge frame's x (catalogue mapping, catalog.py), so plate
X = calculator X + 10 mm. Z is depth in both.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "..", "python")]

from beam_field import Solid, beam_field, element_sources          # noqa: E402
from beam_metrics import beam_axis                                  # noqa: E402
from delay_law import DelayLaw                                      # noqa: E402
from fe_reference import fe_beam_map                                # noqa: E402
from material import Material                                       # noqa: E402
from probe import create_probe_assembly                             # noqa: E402
from wedge import Wedge                                             # noqa: E402

# The reference case (buildFE examples/cab02-wedge/beam.json and catalog entries)
WEDGE_ORIGIN_PLATE_X = 0.010
REXOLITE = Solid(1049.0, 2337.0, 1157.0)
STEEL = Solid(7900.0, 5900.0, 3230.0)
F0, CYCLES, ANGLE = 2.25e6, 3, 45.0
N_EL, PITCH, WIDTH = 64, 0.75e-3, 0.55e-3
FACE_DEG, X1, H1 = 36.0, 0.004, 0.005
DEPTH = 0.05

TOL = {"angle_deg": 1.0, "exit_mm": 2.0, "width_rel": 0.10, "level_db": 1.5}


def steer_delays(solver):
    """buildFE delayLaw 'steer' with a wedge: d = (sin a, cos a) in X-Z (Z down),
    sin a = cW / cPart sin(angle); delay_i = (e_i . d) / cW, smallest 0."""
    elements, _, _ = solver._geometry()
    a = math.asin(REXOLITE.cl / STEEL.cs * math.sin(math.radians(ANGLE)))
    d = np.array([math.sin(a), 0.0, math.cos(a)])
    t = elements @ d / REXOLITE.cl
    return t - t.min()


def model_map(X_plate_mm, Z_mm):
    probe = create_probe_assembly("Linear", N_EL, PITCH, F0)
    solver = DelayLaw(probe, Wedge(FACE_DEG, H1, REXOLITE.cl, X1), Material(STEEL.cl, STEEL.cs))
    src = element_sources(solver, steer_delays(solver), WIDTH, dim=2)
    GX, GZ = np.meshgrid(X_plate_mm, Z_mm)
    ok = (GZ >= 2) & (GZ <= DEPTH * 1e3 - 2)
    pts = np.column_stack([(GX[ok] * 1e-3 - WEDGE_ORIGIN_PLATE_X), np.zeros(ok.sum()), GZ[ok] * 1e-3])
    amp = np.full(GX.shape, np.nan)
    amp[ok] = beam_field(src, pts, REXOLITE, STEEL, "shear", F0, CYCLES).amplitude
    return amp, solver


def verdict(fe, md):
    rows = [("Axis angle (deg)", fe.angle_deg, md.angle_deg, md.angle_deg - fe.angle_deg,
             f"<= {TOL['angle_deg']}", abs(md.angle_deg - fe.angle_deg) <= TOL["angle_deg"]),
            ("Exit X (mm, plate)", fe.exit_x_mm, md.exit_x_mm, md.exit_x_mm - fe.exit_x_mm,
             f"<= {TOL['exit_mm']}", abs(md.exit_x_mm - fe.exit_x_mm) <= TOL["exit_mm"])]
    for d, wf, wm, lf, lm in zip(fe.depths_mm, fe.width6_mm, md.width6_mm, fe.level_db, md.level_db):
        rel = (wm - wf) / wf
        rows.append((f"-6 dB width at Z {d:g} (mm)", wf, wm, rel * 100, f"<= {TOL['width_rel']*100:g} %",
                     abs(rel) <= TOL["width_rel"]))
        rows.append((f"Axis level at Z {d:g} (dB)", lf, lm, lm - lf, f"<= {TOL['level_db']}",
                     abs(lm - lf) <= TOL["level_db"]))
    return rows


def figure(path, fe_map, md_map, X, Z, fe, md):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 1, figsize=(9, 7.4), dpi=150, sharex=True)
    for ax, m, met, title in ((axs[0], fe_map, fe, "buildFE: Pogo FE, 2D, bonded wedge (first arrival)"),
                              (axs[1], md_map, md, "Calculator: ray model, 2D line elements, bonded wedge")):
        db = 20 * np.log10(m / np.nanmax(m))
        im = ax.imshow(np.clip(db, -30, 0), extent=[X[0], X[-1], Z[-1], Z[0]] if Z[0] < Z[-1] else [X[0], X[-1], Z[0], Z[-1]],
                       origin="upper" if Z[0] < Z[-1] else "lower", cmap="turbo", vmin=-30, vmax=0, aspect="equal")
        ax.contour(X, Z, db, levels=[-6], colors="w", linewidths=1.0)
        ax.contour(X, Z, db, levels=[-12], colors="w", linewidths=0.8, linestyles="--")
        zz = np.array([0, DEPTH * 1e3])
        ax.plot(met.exit_x_mm + np.tan(np.radians(met.angle_deg)) * zz, zz, "w:", lw=1)
        ax.set_ylim(DEPTH * 1e3, 0)
        ax.set_xlim(X[0], X[-1])
        ax.set_ylabel("Z depth (mm)")
        ax.set_title(f"{title}\naxis {met.angle_deg:.1f} deg, exit X {met.exit_x_mm:.1f} mm; -6 dB width "
                     + ", ".join(f"{w:.1f}" for w in met.width6_mm) + " mm at Z 10/20/30/40", fontsize=9)
        fig.colorbar(im, ax=ax, label="dB re beam maximum", fraction=0.025)
    axs[1].set_xlabel("X along the surface (mm, buildFE plate frame; wedge front at 10 mm)")
    fig.suptitle("2.25L64-A2 on SA2-N55S, 64 elements, 45 deg shear steer, 3-cycle 2.25 MHz Hann burst", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)


def main(h5, out):
    os.makedirs(out, exist_ok=True)
    fe_map, X, Z = fe_beam_map(h5)
    fe = beam_axis(fe_map, X, Z)
    t = time.time()
    md_map, _ = model_map(X, Z)
    secs = time.time() - t
    md = beam_axis(md_map, X, Z)
    rows = verdict(fe, md)
    ok = all(r[-1] for r in rows)
    lines = ["| Metric | buildFE FE | Calculator | Difference | Tolerance | Pass |", "|---|---|---|---|---|---|"]
    for name, a, b, d, tol, p in rows:
        lines.append(f"| {name} | {a:.2f} | {b:.2f} | {d:+.2f}{' %' if 'width' in name else ''} | {tol} | {'yes' if p else 'NO'} |")
    table = "\n".join(lines)
    print(table)
    print(f"\nModel map: {md_map.size} grid points in {secs:.1f} s. Overall: {'PASS' if ok else 'FAIL'}")
    figure(os.path.join(out, "step6_beam_vs_buildfe.png"), fe_map, md_map, X, Z, fe, md)
    with open(os.path.join(out, "step6_beam_vs_buildfe.json"), "w") as f:
        json.dump({"pass": ok, "seconds": secs, "tolerance": TOL,
                   "rows": [dict(metric=r[0], fe=r[1], model=r[2], diff=r[3], pass_=r[5]) for r in rows]}, f, indent=1)
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "out")) else 1)
