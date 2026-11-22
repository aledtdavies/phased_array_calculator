"""
The browser prototype's Python side (runs in Pyodide, in a Web Worker): a thin layer over the
calculator's own modules (session.py, beam_field.py), so the browser calculates exactly what the
desktop window does. Inputs and outputs are JSON text; lengths in mm, times in us, as the panels.
"""
from __future__ import annotations

import json
import time

import numpy as np

from beam_field import MODEL_NOTE, Solid, beam_field, element_sources, field_region, section_grid
from session import TABLE_HEADINGS, build_solver, calculate

FLOOR_DB = -30.0
MAX_POINTS = 40000
VALIDATION_NOTE = ("Validated in 2D against an FE solve (buildFE Task 125: a steered 45 degree shear beam); "
                   "see docs/beam_field_model.html for where the model can be trusted.")
_state = {}


def _mm(a):
    return np.round(np.asarray(a, dtype=float) * 1e3, 4).tolist()


def calc(cfg_text):
    """Every law of the scan: table rows and the geometry the X-Z view and delay chart draw."""
    t0 = time.perf_counter()
    cfg = json.loads(cfg_text)
    solver = build_solver(cfg["probe"], cfg["wedge"], cfg["material"], cfg["sub_aperture"])
    c = calculate(solver, cfg["scan"], cfg["probe"].get("probe_type", "Linear"))
    _state.update(solver=solver, calc=c, thickness_mm=float(cfg["material"].get("thickness_mm", 0.0)))
    elements, _, active = solver._geometry()
    laws = []
    for r in c.results:
        d = np.asarray(r["delays_us"], dtype=float)
        laws.append({"angle": r["angle"], "focus": _mm([r["fx"], r["fz"]]),
                     "interface": _mm(np.asarray(r["interface_points"])[active][:, [0, 2]]),
                     "delays": np.round(d[active], 5).tolist()})
    return json.dumps({
        "headings": list(TABLE_HEADINGS),
        "rows": [[str(v) for v in values] for values, _ in c.rows],
        "elements": _mm(elements[:, [0, 2]]), "active": [int(i) for i in active],
        "laws": laws, "wave": c.wave_type, "seconds": time.perf_counter() - t0})


def field(cfg_text):
    """The 2D beam field (X-Z section, line elements) of law index `law`, in dB re its maximum."""
    t0 = time.perf_counter()
    cfg = json.loads(cfg_text)
    solver, c = _state["solver"], _state["calc"]
    r = c.results[int(cfg["law"])]
    mat = solver.material
    wedge = Solid(cfg["wedge_density"], solver.wedge.velocity, cfg["wedge_shear_ms"])
    part = Solid(cfg["component_density"], mat.velocity_longitudinal, mat.velocity_shear)
    delays = np.asarray(r["delays_us"], dtype=float) * 1e-6
    active = np.flatnonzero(np.isfinite(delays))
    (xl, xh), (_, zh) = field_region(r, _state["thickness_mm"] * 1e-3, active)
    step = cfg["grid_mm"] * 1e-3
    z0 = min(step, zh / 2)
    (X, Z), used = section_grid((xl, z0), (xh, zh), step, MAX_POINTS)
    GX, GZ = np.meshgrid(X, Z)
    pts = np.column_stack([GX.ravel(), np.zeros(GX.size), GZ.ravel()])
    src = element_sources(solver, delays, cfg["element_width_mm"] * 1e-3, dim=2)
    t1 = time.perf_counter()
    amp = beam_field(src, pts, wedge, part, c.wave_type.lower(), solver.probe.frequency,
                     cfg["cycles"], cfg["pulsed"]).amplitude.reshape(GX.shape)
    t2 = time.perf_counter()
    with np.errstate(divide="ignore"):
        db = np.maximum(20 * np.log10(amp / np.nanmax(amp)), FLOOR_DB)
    return json.dumps({"x": _mm(X), "z": _mm(Z), "db": np.round(db, 2).tolist(), "grid_mm": used * 1e3,
                       "law": int(cfg["law"]), "note": MODEL_NOTE + ". " + VALIDATION_NOTE,
                       "points": int(GX.size), "seconds_field": t2 - t1, "seconds": time.perf_counter() - t0})
