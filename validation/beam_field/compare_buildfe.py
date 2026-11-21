"""
The calculator's beam field against buildFE's FE solves of the same beams, measured by one rule
(beam_metrics) against tolerances fixed in docs/plans/PLAN-2026-11-qt-vtk-migration.md before
each comparison was first run.

    python validation/beam_field/compare_buildfe.py <field_products.h5> [out_dir] [--case NAME]

Cases (--case; default sv45):
  sv45          buildFE Task 125, case f74b8bab65: 64 elements, unfocused 45 deg shear (plan step 6)
  focused_sv55  buildFE Task 204: elements 1-32, shear, focused at plate (67.816, -25.000) mm
  steer_l60     buildFE Task 204: 64 elements, unfocused 60 deg longitudinal

field_products.h5 is in buildFE's returned bundle (cab02_wedge_beam for sv45, under
cab02_wedge_beam/cases/f74b8bab65/; cab02_wedge_laws for the Task 204 cases); it is not copied
into this repository.

Frames: the FE map is in buildFE's plate frame (x along the surface, wedge origin at plate
x = 10 mm); the calculator's X is the wedge frame's x (catalogue mapping, catalog.py), so plate
X = calculator X + 10 mm. Z is depth in both.
"""
from __future__ import annotations

import argparse
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

# The reference setup (buildFE examples/cab02-wedge and cab02-wedge-laws, catalog entries)
WEDGE_ORIGIN_PLATE_X = 0.010
REXOLITE = Solid(1049.0, 2337.0, 1157.0)
STEEL = Solid(7900.0, 5900.0, 3230.0)
F0, CYCLES = 2.25e6, 3
N_EL, PITCH, WIDTH = 64, 0.75e-3, 0.55e-3
FACE_DEG, X1, H1 = 36.0, 0.004, 0.005
DEPTH = 0.05

# Tolerances as fixed in the plan (sv45: 2026-11-20, fb37a6a; Task 204 cases: 2026-11-21, 5ded4b8).
CASES = {
    "sv45": dict(mode="shear", law="steer", angle=45.0, elements=(1, 64), depths=(10.0, 20.0, 30.0, 40.0),
                 tol=dict(angle_deg=1.0, exit_mm=2.0, width_rel=0.10, level_db=1.5),
                 title="64 elements, 45 deg shear steer", image="step6_beam_vs_buildfe"),
    "focused_sv55": dict(mode="shear", law="focus", point_plate=(0.067816, 0.025), elements=(1, 32),
                         depths=(15.0, 25.0, 35.0),
                         tol=dict(angle_deg=1.5, exit_mm=2.0, width_rel=0.15, level_db=2.0, peak_mm=4.0),
                         title="elements 1-32, 55 deg shear focused at 25 mm", image="beam_vs_buildfe_focused_sv55"),
    "steer_l60": dict(mode="longitudinal", law="steer", angle=60.0, elements=(1, 64), depths=(10.0, 20.0, 30.0, 40.0),
                      tol=dict(angle_deg=1.0, exit_mm=2.0, width_rel=0.10, level_db=1.5),
                      title="64 elements, 60 deg longitudinal steer", image="beam_vs_buildfe_steer_l60"),
}


def part_speed(mode):
    return STEEL.cl if mode == "longitudinal" else STEEL.cs


def steer_delays(solver, angle_deg, mode):
    """buildFE delayLaw 'steer' with a wedge: d = (sin a, cos a) in X-Z (Z down),
    sin a = cW / cPart sin(angle); delay_i = (e_i . d) / cW, smallest active delay 0."""
    elements, _, active = solver._geometry()
    a = math.asin(REXOLITE.cl / part_speed(mode) * math.sin(math.radians(angle_deg)))
    d = np.array([math.sin(a), 0.0, math.cos(a)])
    t = np.full(elements.shape[0], np.nan)
    t[active] = elements[active] @ d / REXOLITE.cl
    return t - np.nanmin(t)


def case_solver(case):
    first, count = case["elements"]
    probe = create_probe_assembly("Linear", N_EL, PITCH, F0, start_element=first, num_active_elements=count)
    return DelayLaw(probe, Wedge(FACE_DEG, H1, REXOLITE.cl, X1), Material(STEEL.cl, STEEL.cs))


def case_delays(solver, case):
    if case["law"] == "steer":
        return steer_delays(solver, case["angle"], case["mode"])
    # buildFE 'focus': each element's Fermat time to the point, delay = max(T) - T (the calculator's rule)
    px, pz = case["point_plate"]
    return solver.calculate_law(px - WEDGE_ORIGIN_PLATE_X, 0.0, pz, case["mode"])["delays"]


def model_map(case, X_plate_mm, Z_mm):
    solver = case_solver(case)
    src = element_sources(solver, case_delays(solver, case), WIDTH, dim=2)
    GX, GZ = np.meshgrid(X_plate_mm, Z_mm)
    ok = (GZ >= 2) & (GZ <= DEPTH * 1e3 - 2)
    pts = np.column_stack([(GX[ok] * 1e-3 - WEDGE_ORIGIN_PLATE_X), np.zeros(ok.sum()), GZ[ok] * 1e-3])
    amp = np.full(GX.shape, np.nan)
    amp[ok] = beam_field(src, pts, REXOLITE, STEEL, case["mode"], F0, CYCLES).amplitude
    return amp


def verdict(case, fe, md):
    tol = case["tol"]
    rows = [("Axis angle (deg)", fe.angle_deg, md.angle_deg, md.angle_deg - fe.angle_deg,
             f"<= {tol['angle_deg']}", abs(md.angle_deg - fe.angle_deg) <= tol["angle_deg"]),
            ("Exit X (mm, plate)", fe.exit_x_mm, md.exit_x_mm, md.exit_x_mm - fe.exit_x_mm,
             f"<= {tol['exit_mm']}", abs(md.exit_x_mm - fe.exit_x_mm) <= tol["exit_mm"])]
    for d, wf, wm, lf, lm in zip(fe.depths_mm, fe.width6_mm, md.width6_mm, fe.level_db, md.level_db):
        rel = (wm - wf) / wf
        rows.append((f"-6 dB width at Z {d:g} (mm)", wf, wm, rel * 100, f"<= {tol['width_rel']*100:g} %",
                     bool(abs(rel) <= tol["width_rel"])))
        rows.append((f"Axis level at Z {d:g} (dB)", lf, lm, lm - lf, f"<= {tol['level_db']}",
                     bool(abs(lm - lf) <= tol["level_db"])))
    if "peak_mm" in tol:
        dist = math.hypot(md.peak_x_mm - fe.peak_x_mm, md.peak_z_mm - fe.peak_z_mm)
        rows.append((f"Peak position (FE {fe.peak_x_mm:.1f}, {fe.peak_z_mm:.1f}; model {md.peak_x_mm:.1f}, "
                     f"{md.peak_z_mm:.1f} mm): distance", 0.0, dist, dist, f"<= {tol['peak_mm']}",
                     dist <= tol["peak_mm"]))
    return rows


def figure(path, case, fe_map, md_map, X, Z, fe, md):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(2, 1, figsize=(9, 7.4), dpi=150, sharex=True)
    depths = "/".join(f"{d:g}" for d in fe.depths_mm)
    for ax, m, met, title in ((axs[0], fe_map, fe, "buildFE: Pogo FE, 2D, bonded wedge (first arrival)"),
                              (axs[1], md_map, md, "Calculator: ray model, 2D line elements, bonded wedge")):
        db = 20 * np.log10(m / np.nanmax(m))
        im = ax.imshow(np.clip(db, -30, 0), extent=[X[0], X[-1], Z[-1], Z[0]] if Z[0] < Z[-1] else [X[0], X[-1], Z[0], Z[-1]],
                       origin="upper" if Z[0] < Z[-1] else "lower", cmap="turbo", vmin=-30, vmax=0, aspect="equal")
        ax.contour(X, Z, db, levels=[-6], colors="w", linewidths=1.0)
        ax.contour(X, Z, db, levels=[-12], colors="w", linewidths=0.8, linestyles="--")
        zz = np.array([0, DEPTH * 1e3])
        ax.plot(met.exit_x_mm + np.tan(np.radians(met.angle_deg)) * zz, zz, "w:", lw=1)
        ax.plot([met.peak_x_mm], [met.peak_z_mm], "w+", ms=10, mew=1.5)
        ax.set_ylim(DEPTH * 1e3, 0)
        ax.set_xlim(X[0], X[-1])
        ax.set_ylabel("Z depth (mm)")
        ax.set_title(f"{title}\naxis {met.angle_deg:.1f} deg, exit X {met.exit_x_mm:.1f} mm; -6 dB width "
                     + ", ".join(f"{w:.1f}" for w in met.width6_mm) + f" mm at Z {depths}", fontsize=9)
        fig.colorbar(im, ax=ax, label="dB re beam maximum", fraction=0.025)
    axs[1].set_xlabel("X along the surface (mm, buildFE plate frame; wedge front at 10 mm)")
    fig.suptitle(f"2.25L64-A2 on SA2-N55S, {case['title']}, 3-cycle 2.25 MHz Hann burst", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)


def main(h5, out, name="sv45"):
    case = CASES[name]
    os.makedirs(out, exist_ok=True)
    fe_map, X, Z = fe_beam_map(h5)
    fe = beam_axis(fe_map, X, Z, depths_mm=case["depths"])
    t = time.time()
    md_map = model_map(case, X, Z)
    secs = time.time() - t
    md = beam_axis(md_map, X, Z, depths_mm=case["depths"])
    rows = verdict(case, fe, md)
    ok = all(r[-1] for r in rows)
    lines = [f"Case {name}: {case['title']}", "",
             "| Metric | buildFE FE | Calculator | Difference | Tolerance | Pass |", "|---|---|---|---|---|---|"]
    for metric, a, b, d, tol, p in rows:
        lines.append(f"| {metric} | {a:.2f} | {b:.2f} | {d:+.2f}{' %' if 'width' in metric else ''} | {tol} | "
                     f"{'yes' if p else 'NO'} |")
    print("\n".join(lines))
    print(f"\nModel map: {md_map.size} grid points in {secs:.1f} s. Overall: {'PASS' if ok else 'FAIL'}")
    figure(os.path.join(out, case["image"] + ".png"), case, fe_map, md_map, X, Z, fe, md)
    with open(os.path.join(out, case["image"] + ".json"), "w") as f:
        json.dump({"case": name, "pass": ok, "seconds": secs, "tolerance": case["tol"],
                   "rows": [dict(metric=r[0], fe=r[1], model=r[2], diff=r[3], pass_=bool(r[5])) for r in rows]},
                  f, indent=1)
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("h5")
    ap.add_argument("out", nargs="?", default=os.path.join(HERE, "out"))
    ap.add_argument("--case", default="sv45", choices=sorted(CASES))
    a = ap.parse_args()
    sys.exit(0 if main(a.h5, a.out, a.case) else 1)
