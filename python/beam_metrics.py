"""
Beam dimensions measured on a time-flattened field map: the beam axis, its exit point, and the
-6 / -12 dB widths across the axis at chosen depths.

Ported from buildFE ``examples/fe-ref-field/make_field_figures.m`` (functions ``beamAxis``,
``widestRun`` and ``band``; buildFE commit at the time of the port: see the step 6 entry in
CHANGELOG.md), so that a calculator field map and a buildFE FE map are measured by the same rule.
The rule, as buildFE states it (APPROXIMATION):

* the map is median-filtered (5 points along X, then along Z, NaN-aware) to remove specks;
* on each row (one depth) the beam is the widest run above -6 dB of that row's maximum; the
  row's axis point is the run's midpoint;
* a straight line X = c1 Z + c0 fitted through the axis points of rows whose maximum is within
  12 dB of the map's maximum gives the axis angle (atan c1, from the vertical, positive towards
  +X) and the exit point c0 (where the axis meets Z = 0);
* the width at a depth is the run's extent along X times cos(axis angle), so it is measured
  across the beam; the -12 dB width is the contiguous band about the row's peak inside the run;
* the axis level at a depth is that row's maximum in dB re the map's maximum.

Frame and units: X along the surface, Z depth (down), both in mm; the map is indexed [z, x].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

DEPTHS_MM = (10.0, 20.0, 30.0, 40.0)


def movmedian_nan(a, n, axis):
    """MATLAB movmedian(a, n, axis, 'omitnan') for odd n: a centred window, shrunk at the ends."""
    a = np.moveaxis(np.asarray(a, dtype=float), axis, -1)
    h = n // 2
    pad = np.pad(a, [(0, 0)] * (a.ndim - 1) + [(h, h)], constant_values=np.nan)
    win = np.lib.stride_tricks.sliding_window_view(pad, n, axis=-1)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN windows stay NaN
            out = np.nanmedian(win, axis=-1)
    return np.moveaxis(out, -1, axis)


def _widest_run(mask):
    """First widest run of True: (lo, hi) inclusive indices."""
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    starts = np.flatnonzero(d == 1)
    stops = np.flatnonzero(d == -1) - 1
    k = int(np.argmax(stops - starts))
    return int(starts[k]), int(stops[k])


def _band(row, a, rm, level_db):
    with np.errstate(all="ignore"):
        above = 20 * np.log10(row / rm) >= level_db
    lo = hi = a
    while lo > 0 and above[lo - 1]:
        lo -= 1
    while hi < len(row) - 1 and above[hi + 1]:
        hi += 1
    return lo, hi


@dataclass
class BeamMetrics:
    angle_deg: float                 # axis angle from the vertical, + towards +X
    exit_x_mm: float                 # where the axis meets Z = 0
    depths_mm: tuple
    axis_x_mm: list = field(default_factory=list)
    width6_mm: list = field(default_factory=list)
    width12_mm: list = field(default_factory=list)
    level_db: list = field(default_factory=list)
    peak_x_mm: float = math.nan
    peak_z_mm: float = math.nan

    def rows(self):
        """One dict per depth, as buildFE's beam_metrics.csv."""
        return [dict(depth_mm=d, axisX_mm=x, width6dB_mm=w6, width12dB_mm=w12, axisLevel_dB=l)
                for d, x, w6, w12, l in zip(self.depths_mm, self.axis_x_mm, self.width6_mm,
                                            self.width12_mm, self.level_db)]


def beam_axis(field_map, x_mm, z_mm, depths_mm=DEPTHS_MM):
    """
    BeamMetrics of a time-flattened amplitude map field_map[z, x] (linear amplitude, NaN where
    blank) on grid vectors x_mm, z_mm. Refuses a map with too few beam rows to fit an axis.
    """
    m = np.asarray(field_map, dtype=float)
    X = np.asarray(x_mm, dtype=float)
    Z = np.asarray(z_mm, dtype=float)
    if m.shape != (Z.size, X.size):
        raise ValueError(f"map shape {m.shape} does not match the grid ({Z.size}, {X.size})")
    m = movmedian_nan(movmedian_nan(m, 5, 1), 5, 0)
    pk = np.nanmax(m)
    n = Z.size
    mid, w6, w12, top = (np.full(n, np.nan) for _ in range(4))
    for r in range(n):
        row = m[r]
        if np.all(np.isnan(row)):
            continue
        rm = np.nanmax(row)
        with np.errstate(all="ignore"):
            mask = 20 * np.log10(row / rm) >= -6
        lo, hi = _widest_run(mask)
        a = lo + int(np.nanargmax(row[lo:hi + 1]))
        top[r] = row[a]
        mid[r] = (X[lo] + X[hi]) / 2
        w6[r] = X[hi] - X[lo]
        lo, hi = _band(row, a, row[a], -12)
        w12[r] = X[hi] - X[lo]
    ridge = (top >= pk * 10 ** (-12 / 20)) & ~np.isnan(mid)
    if ridge.sum() < 2:
        raise ValueError("too few beam rows to fit an axis")
    c1, c0 = np.polyfit(Z[ridge], mid[ridge], 1)
    ang = math.degrees(math.atan(c1))
    out = BeamMetrics(ang, float(c0), tuple(depths_mm))
    cosa = math.cos(math.radians(ang))
    for d in depths_mm:
        r = int(np.argmin(np.abs(Z - d)))
        if np.isnan(mid[r]):
            vals = (np.nan,) * 4
        else:
            vals = (mid[r], w6[r] * cosa, w12[r] * cosa, 20 * math.log10(top[r] / pk))
        for lst, v in zip((out.axis_x_mm, out.width6_mm, out.width12_mm, out.level_db), vals):
            lst.append(float(v))
    GX, GZ = np.meshgrid(X, Z)
    off = np.abs(GX - (c1 * GZ + c0)) * cosa
    band = off <= np.nanmax(w6[ridge]) * cosa / 2
    masked = np.where(band, m, np.nan)
    iz, ix = np.unravel_index(int(np.nanargmax(masked)), m.shape)
    out.peak_x_mm, out.peak_z_mm = float(X[ix]), float(Z[iz])
    return out
