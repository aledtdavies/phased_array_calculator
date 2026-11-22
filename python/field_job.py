"""
The beam field computation of one law, independent of any window: the sections to map (an X-Z
section, and in 3D a Y-Z section through the focus), and their peak envelopes in dB re the
largest of them. Used by the desktop Beam Field tab (qt_field.py) and the browser version
(web/pac_web.py), so both compute the same field.

values (the Beam Field inputs): model ("2D" or "3D"), pulsed, cycles, grid_mm, element_width_mm,
elevation_mm, wedge_shear_ms, wedge_density, component_density. Lengths in mm there; the job
holds SI.
"""
from __future__ import annotations

import numpy as np

import time

from beam_field import Solid, beam_field, element_sources, field_region, point_block, section_grid

FLOOR_DB = -30.0
MAX_POINTS = {2: 40000, 3: 12000}     # per section; the grid step grows to stay below


def make_job(solver, r, wave_type, thickness_mm, values):
    """
    The computation for law result r (session's result dict) of solver; ValueError if it
    cannot run.
    """
    v = values
    dim = 3 if v["model"] == "3D" else 2
    mode = wave_type.lower()
    mat = solver.material
    part_cs = mat.velocity_shear
    if part_cs is None:
        raise ValueError("the component needs a shear wave speed")
    wedge = Solid(v["wedge_density"], solver.wedge.velocity, v["wedge_shear_ms"])
    part = Solid(v["component_density"], mat.velocity_longitudinal, part_cs)
    delays = np.asarray(r["delays_us"], dtype=float) * 1e-6
    active = np.flatnonzero(np.isfinite(delays))
    if active.size == 0:
        raise ValueError("the law has no active element")
    (xl, xh), (zl, zh) = field_region(r, thickness_mm * 1e-3, active)
    step = v["grid_mm"] * 1e-3
    z0 = min(step, zh / 2)                # first depth below the surface, inside the part
    (X, Z), used = section_grid((xl, z0), (xh, zh), step, MAX_POINTS[dim])
    y0 = float(np.mean(solver._geometry()[0][active][:, 1])) if dim == 3 else 0.0
    GX, GZ = np.meshgrid(X, Z)
    sections = [dict(name="X-Z", h=X, z=Z, shape=GX.shape, fixed=("Y", y0),
                     points=np.column_stack([GX.ravel(), np.full(GX.size, y0), GZ.ravel()]))]
    if dim == 3:
        half = max(v["elevation_mm"] * 1e-3, 0.005) + 0.010
        (Y, Z2), _ = section_grid((r["fy"] - half, z0), (r["fy"] + half, zh), used, MAX_POINTS[dim])
        GY, GZ2 = np.meshgrid(Y, Z2)
        sections.append(dict(name="Y-Z", h=Y, z=Z2, shape=GY.shape, fixed=("X", r["fx"]),
                             points=np.column_stack([np.full(GY.size, r["fx"]), GY.ravel(), GZ2.ravel()])))
    return dict(solver=solver, delays=delays, width=v["element_width_mm"] * 1e-3,
                elevation=v["elevation_mm"] * 1e-3, dim=dim, f0=solver.probe.frequency,
                cycles=v["cycles"], pulsed=v["pulsed"], mode=mode, wedge=wedge, part=part,
                sections=sections, step_mm=used * 1e3, values=v)


def run_job(job, progress=None):
    """Compute the sections of a job (see make_job) in one go; returns the job with 'db'.
    progress(fraction) is called after each block of points (it may raise to stop)."""
    start_job(job)
    step_job(job, progress=progress)
    return finish_job(job)


# The job in steps: start_job, step_job until it returns True, finish_job. A caller that cannot
# be interrupted while Python runs (the browser) computes a step at a time, reports progress and
# can stop between steps. Steps are whole blocks (beam_field.point_block), so the result equals
# run_job's exactly.
def start_job(job):
    """Prepare a job for step_job: the element sources, and nothing computed yet."""
    job["src"] = element_sources(job["solver"], job["delays"], job["width"], job["elevation"], job["dim"],
                                 f_max=job["f0"] * (1.5 if job["pulsed"] else 1.0))
    job["block"] = point_block(job["src"])
    for s in job["sections"]:
        s["amp_flat"] = np.empty(s["points"].shape[0])
    job["cursor"] = [0, 0]                    # section, first point not yet computed
    job["total"] = sum(s["points"].shape[0] for s in job["sections"])
    job["done"] = 0
    return job


def step_job(job, seconds=None, progress=None):
    """
    Compute the next points of a started job: all of them (seconds None), or whole blocks until
    `seconds` have passed (at least one block). Returns True when every point is computed.
    """
    t0 = time.perf_counter()
    secs, block = job["sections"], job["block"]
    while job["cursor"][0] < len(secs):
        si, k0 = job["cursor"]
        s = secs[si]
        n = s["points"].shape[0]
        k1 = n if seconds is None else min(n, k0 + block)
        base = job["done"]

        def prog(f, base=base, m=k1 - k0):
            if progress:
                progress((base + f * m) / job["total"])
        s["amp_flat"][k0:k1] = beam_field(job["src"], s["points"][k0:k1], job["wedge"], job["part"], job["mode"],
                                          job["f0"], job["cycles"], job["pulsed"], progress=prog).amplitude
        job["done"] += k1 - k0
        job["cursor"] = [si + 1, 0] if k1 >= n else [si, k1]
        if seconds is not None and time.perf_counter() - t0 >= seconds:
            break
    return job["cursor"][0] >= len(secs)


def finish_job(job):
    """The dB maps of a fully stepped job, re the largest amplitude of its sections."""
    secs = job["sections"]
    for s in secs:
        s["amp"] = s.pop("amp_flat").reshape(s["shape"])
    peak = max(np.nanmax(s["amp"]) if np.isfinite(s["amp"]).any() else np.nan for s in secs)
    if not (np.isfinite(peak) and peak > 0):
        raise ValueError("the field has no finite amplitude anywhere in the section")
    for s in secs:
        with np.errstate(divide="ignore"):
            s["db"] = np.maximum(20 * np.log10(s["amp"] / peak), FLOOR_DB)
    return job
