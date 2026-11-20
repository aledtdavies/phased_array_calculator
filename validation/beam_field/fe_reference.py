"""
Read buildFE's returned FE field products (field_products.h5, buildFE Task 129 format) and form
the time-flattened beam map exactly as buildFE ``examples/cab02-field/make_field_figures.m``
(``peakMap``, gate 'first', beam-only exclusions; buildFE commit 9febff0) does.

FE frame: plate x along the surface, y up (part y < 0). Returned map indexed [z, x] with
X = x in mm and Z = -y in mm (depth).
"""
from __future__ import annotations

import numpy as np


def analytic_signal(x, axis=-1):
    """buildfe.results.analyticSignal: one-sided spectrum, doubled positive bins."""
    nt = x.shape[axis]
    X = np.fft.fft(x, axis=axis)
    w = np.zeros(nt)
    w[0] = 1
    if nt % 2 == 0:
        w[1:nt // 2] = 2
        w[nt // 2] = 1
    else:
        w[1:(nt + 1) // 2] = 2
    shape = [1] * x.ndim
    shape[axis] = nt
    return np.fft.ifft(X * w.reshape(shape), axis=axis)


def fe_beam_map(h5_path, view="wide", cycles=3, f0=2.25e6, depth_m=0.05):
    """(map[z, x], X_mm, Z_mm) of the FE run's first-arrival beam."""
    import h5py
    with h5py.File(h5_path, "r") as f:
        g = f["views"][view]
        t = np.asarray(f["times"]).ravel()
        scale = np.asarray(g["scale"]).ravel()
        # MATLAB-written arrays read back with reversed dimensions: (nF, nx, ny) -> (ny, nx, nF)
        U = np.asarray(g["ux"]).transpose(2, 1, 0).astype(np.float32) * scale.astype(np.float32)
        V = np.asarray(g["uy"]).transpose(2, 1, 0).astype(np.float32) * scale.astype(np.float32)
        valid = np.asarray(g["valid"]).T.astype(bool)
        x = np.asarray(g["x"]).ravel()
        y = np.asarray(g["y"]).ravel()
    ny, nx, nF = U.shape
    E = np.sqrt(np.abs(analytic_signal(U.reshape(-1, nF))) ** 2
                + np.abs(analytic_signal(V.reshape(-1, nF))) ** 2)
    del U, V
    T = cycles / f0
    pk = E.max(axis=1)
    above = E >= pk[:, None] * 10 ** (-12 / 20)
    hit = above.any(axis=1)
    i1 = np.argmax(above, axis=1)
    t1 = np.where(hit, t[i1], np.inf)
    E[t[None, :] > (t1 + 1.5 * T)[:, None]] = 0
    T1 = t1.reshape(ny, nx).copy()
    T1[~np.isfinite(T1)] = np.nan
    dTdy, _ = np.gradient(T1, y, x)                    # rows follow y (up)
    upgoing = dTdy > 0
    m = E.max(axis=1).reshape(ny, nx)
    m[upgoing] = np.nan
    m[~valid] = np.nan
    X = x * 1e3
    Z = -y * 1e3
    m[Z < 2, :] = np.nan
    m[Z > depth_m * 1e3 - 2, :] = np.nan
    return m, X, Z
