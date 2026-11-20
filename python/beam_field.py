"""
Beam field of a delay law: a ray-based, delayed sum of the active elements' contributions in the
component, mapped as the time-flattened peak of the displacement envelope (plan step 6).

Frame and units: the calculator's global frame, SI. X along the wedge, Y across, Z down; the
wedge-component interface is the plane Z = 0, the wedge Z < 0, the component Z > 0. Angles in
radians inside, from the interface normal (Z) unless stated.

Model (each piece is classified):

* Each element radiates a longitudinal wave into the wedge as a uniform normal load on the
  wedge's free surface (Miller and Pursey 1954): the L-wave far-field directivity
  ``cos t (k^2 - 2 sin^2 t) / F0(sin t)`` with k = cL/cS of the wedge, t the angle from the
  element's normal, times ``sinc(w sin t / lambda)`` across the element width w in 2D. Copied
  from arim (see ``_f0`` and ``directivity_l``). APPROXIMATION: far field of each element.
* The ray from an element to a field point refracts at Z = 0 at the Fermat point (Snell), found
  here for every element-point pair at once (``fermat_entry``). FACT for a flat interface and
  homogeneous isotropic media.
* At the interface the wedge's L wave converts into the component's chosen mode with the plane-
  wave displacement transmission coefficient of a WELDED (bonded) solid-solid interface
  (``interface_coefficients``: continuity of displacement and normal and shear traction).
  ASSUMPTION: bonded contact, as buildFE's FE reference; a fluid couplant (no shear) is not
  modelled. APPROXIMATION: plane-wave coefficients applied ray by ray.
* Geometric spreading through the interface (Schmerr, Fundamentals of Ultrasonic Phased Arrays,
  2015, ch. 2; arim ``beamspread_2d_for_path``): 2D (line sources)
  ``1 / sqrt(r1 + r2 (c2 cos^2 a1) / (c1 cos^2 a2))``; 3D (point sources) the product of that
  in-plane term and the out-of-plane ``r1 + r2 c2 / c1`` under one square root. DERIVED from
  ray tubes and tested against a numerical ray tube (test_beam_field).
* Frequency content: 2D sources carry the line-source factor ``1 / sqrt(omega)``; 3D point
  sources none. The pulse is a Hann-windowed tone burst (as buildFE's ``hann-toneburst``).
* The map is the peak over time of the envelope of the displacement vector, summed over
  elements component by component, ``sqrt(sum_c |analytic u_c|^2)``. Only the direct beam is
  modelled: no back-wall or surface reflection, no mode conversion, no attenuation (ASSUMPTION,
  stated with the views).

2D mode (``dim=2``) treats each element as an infinitely long strip (plane strain), which is
what buildFE's 2D FE reference solves; 3D mode (``dim=3``) splits each element into point
sources across its elevation and width.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

MODEL_NOTE = ("Beam field: ray model, bonded wedge, direct beam only; no reflections, "
              "mode conversion or attenuation")
CHUNK = 2048            # field points per block, at most
CHUNK_PAIRS = 1 << 21   # (point, source) pairs per block: bounds the block's memory
SPECTRUM_FLOOR = 1e-2   # band edges: where the pulse spectrum falls below this fraction (-40 dB) of its peak


# ---------------------------------------------------------------------------------------------
# Element directivity: copied from arim (MIT licence, (c) 2016-2025 arim contributors),
# src/arim/model.py, functions _f0 and directivity_2d_rectangular_on_solid_l, commit 0cee9de.
# References: Miller G F and Pursey H 1954, Proc R Soc A 223, 521-541, eqs (74), (93);
# Drinkwater B W and Wilcox P D 2006, NDT&E Int 39, 525-541.
# ---------------------------------------------------------------------------------------------
def _f0(x, k2):
    # Miller and Pursey 1954 eq (74). sqrt(a) * sqrt(b) != sqrt(a * b) for negative values.
    x2 = x * x
    return (2 * x2 - k2) ** 2 - 4 * x2 * np.sqrt(x2 - 1) * np.sqrt(x2 - k2)


def directivity_l(sin_t, cos_t, width_term, k):
    """
    L-wave far-field directivity of a normal strip load on a solid (complex, unnormalised):
    ``cos t (k^2 - 2 sin^2 t) / F0(sin t) * sinc(width_term)``, k = cL / cS of the solid,
    width_term = w * (sine across the width) / lambda_L (0 for a point source).
    """
    k2 = k * k
    s = np.asarray(sin_t).astype(complex)
    return (k2 - 2 * s ** 2) * cos_t / _f0(s, k2) * np.sinc(width_term)


# ---------------------------------------------------------------------------------------------
# Plane-wave coefficients at a welded solid-solid interface
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Solid:
    """An isotropic solid: density (kg/m^3), longitudinal and shear speeds (m/s)."""
    rho: float
    cl: float
    cs: float

    def __post_init__(self):
        if not (self.rho > 0 and self.cl > 0 and self.cs > 0):
            raise ValueError("a solid needs positive density and wave speeds")
        if not self.cl > math.sqrt(2) * self.cs:
            raise ValueError("cL must exceed sqrt(2) cS (positive Lame lambda)")

    @property
    def mu(self):
        return self.rho * self.cs ** 2

    @property
    def lam(self):
        return self.rho * (self.cl ** 2 - 2 * self.cs ** 2)


def _eta(p, c):
    """Vertical slowness of a down-going wave (Im >= 0: evanescent waves decay with +Z)."""
    return np.sqrt((1.0 / c ** 2 - p ** 2).astype(complex))


def _wave_columns(m: Solid, p, eta_p, eta_s):
    """
    Displacement (x, z) and traction (szz, sxz, both / i omega) of unit-displacement P and S
    plane waves e^{i omega (p x + eta z - t)}: P polarised along (p, eta) c_L, S along
    (eta, -p) c_S. Returns two (..., 4) arrays.
    """
    def col(ux, uz, eta):
        szz = m.lam * (p * ux + eta * uz) + 2 * m.mu * eta * uz
        sxz = m.mu * (eta * ux + p * uz)
        return np.stack([ux, uz, szz, sxz], axis=-1)
    P = col(p * m.cl, eta_p * m.cl, eta_p)
    S = col(eta_s * m.cs, -p * m.cs, eta_s)
    return P, S


def interface_coefficients(p, upper: Solid, lower: Solid, incident="P"):
    """
    Displacement-amplitude reflection and transmission coefficients of a plane wave travelling
    down (+Z) in ``upper`` onto a welded interface Z = 0 with ``lower``. p: horizontal slowness
    (s/m, sin(angle)/c of the incident wave), scalar or array. Returns a dict of complex arrays
    RP, RS (reflected, up-going in upper), TP, TS (transmitted, down-going in lower).
    Polarisations: P along its propagation direction, S along (cos a, -sin a) for a down-going
    wave at angle a from +Z towards +X (and (eta, -p) c_S in general).
    """
    p = np.asarray(p, dtype=float)
    e1p, e1s = _eta(p, upper.cl), _eta(p, upper.cs)
    e2p, e2s = _eta(p, lower.cl), _eta(p, lower.cs)
    inc_p, inc_s = _wave_columns(upper, p, e1p, e1s)
    ref_p, ref_s = _wave_columns(upper, p, -e1p, -e1s)
    tr_p, tr_s = _wave_columns(lower, p, e2p, e2s)
    M = np.stack([ref_p, ref_s, -tr_p, -tr_s], axis=-1)          # (..., 4 conditions, 4 waves)
    rhs = -(inc_p if incident.upper() == "P" else inc_s)
    x = np.linalg.solve(M, rhs[..., None])[..., 0]
    return {"RP": x[..., 0], "RS": x[..., 1], "TP": x[..., 2], "TS": x[..., 3]}


TABLE_SIZE = 16385     # slownesses tabulated from 0 to 1 / c1 (see coefficient_table)


def coefficient_table(upper: Solid, lower: Solid, key, incident="P"):
    """
    interface_coefficients(...)[key] for a P (or S) wave in ``upper``, as a function of the
    horizontal slowness p in [0, 1/c]: a callable p -> complex, linear interpolation of an exact
    table of TABLE_SIZE slownesses. APPROXIMATION: within about 1 % next to a critical angle
    (where the coefficient has a square-root kink), to rounding elsewhere (test_beam_field).
    """
    c = upper.cl if incident.upper() == "P" else upper.cs
    # stop just short of grazing (p = 1/c), where incident and reflected waves coincide and the
    # boundary conditions are singular; slownesses beyond the last entry take its value
    grid = np.linspace(0.0, (1.0 - 1e-9) / c, TABLE_SIZE)
    vals = interface_coefficients(grid, upper, lower, incident)[key]

    def f(p):
        p = np.asarray(p, dtype=float)
        return np.interp(p, grid, vals.real) + 1j * np.interp(p, grid, vals.imag)
    return f


# ---------------------------------------------------------------------------------------------
# Rays through the interface Z = 0
# ---------------------------------------------------------------------------------------------
def fermat_entry(a, d, b, c1, c2, bisections=14, newton=6):
    """
    Horizontal distance s (0 <= s <= d) from a source at height a above Z = 0 to the Fermat
    entry point on the way to a point at depth b and horizontal distance d: Snell's law
    s / (c1 r1) = (d - s) / (c2 r2). The residual is monotone in s (its derivative
    a^2 / (c1 r1^3) + b^2 / (c2 r2^3) > 0): vectorised bisection brackets the root, then Newton
    steps kept inside the bracket finish it. Arrays broadcast.
    """
    a, d, b = np.broadcast_arrays(*(np.asarray(v, dtype=float) for v in (a, d, b)))
    lo = np.zeros_like(d)
    hi = d.copy()

    def res(s):
        r1, r2 = np.hypot(a, s), np.hypot(b, d - s)
        return s / (c1 * r1) - (d - s) / (c2 * r2), r1, r2

    for _ in range(bisections):
        s = 0.5 * (lo + hi)
        f = res(s)[0]
        hi = np.where(f > 0, s, hi)
        lo = np.where(f > 0, lo, s)
    s = 0.5 * (lo + hi)
    for _ in range(newton):
        f, r1, r2 = res(s)
        fp = a * a / (c1 * r1 ** 3) + b * b / (c2 * r2 ** 3)
        s = np.clip(s - f / fp, lo, hi)
    return s


def spread(r1, r2, cos1, cos2, c1, c2, dim):
    """Geometric spreading through the interface (see the module notes); dim 2 or 3."""
    inplane = r1 + r2 * (c2 * cos1 ** 2) / (c1 * cos2 ** 2)
    if dim == 2:
        return 1.0 / np.sqrt(inplane)
    return 1.0 / np.sqrt(inplane * (r1 + r2 * c2 / c1))


# ---------------------------------------------------------------------------------------------
# Sources and pulse
# ---------------------------------------------------------------------------------------------
@dataclass
class Sources:
    """
    Radiating sources (m, global frame): positions (n, 3), unit normals (n, 3) pointing from
    the probe face into the wedge (towards the component), unit width axes (n, 3) along each
    element's width, delays (n,) in s, weights (n,) (area or length of the patch), and the
    element width used in the 2D sinc (0 for 3D patches, which are point sources).
    """
    positions: np.ndarray
    normals: np.ndarray
    width_axes: np.ndarray
    delays: np.ndarray
    weights: np.ndarray
    element_width: float
    dim: int


def element_sources(solver, delays, element_width, elevation=None, dim=2, f_max=None):
    """
    Sources of the active elements of a DelayLaw solver, with firing delays (s, one per element,
    NaN where inactive). dim 2: one strip per element, which needs every element and normal in
    the X-Z plane (a single linear array without roof). dim 3: each element split into point
    sources no more than half a wedge L wavelength at f_max apart across its width and elevation
    (the element's own size across the array; for matrix arrays at most the secondary pitch).
    """
    probe, wedge = solver.probe, solver.wedge
    elements, _, active = solver._geometry()
    delays = np.asarray(delays, dtype=float)
    if delays.shape != (elements.shape[0],):
        raise ValueError("one delay per element is needed")
    active = np.asarray([i for i in active if np.isfinite(delays[i])], dtype=int)
    if active.size == 0:
        raise ValueError("no active element with a delay")
    if not element_width > 0:
        raise ValueError("the element width must be positive")
    signs = wedge.roof_signs(probe)
    # per element axes (roof signs differ for dual probes)
    def axis(v, sign):
        o = wedge.transform_points(np.zeros((1, 3)), sign)[0]
        return wedge.transform_points(np.array([v], dtype=float), sign)[0] - o
    pos, nrm, wax, dl, wt = [], [], [], [], []
    for i in active:
        s = signs[i]
        ax_w, ax_e, n = axis([1, 0, 0], s), axis([0, 1, 0], s), axis([0, 0, 1], s)
        if n[2] < 0:
            n = -n
        if dim == 2:
            if abs(elements[i, 1]) > 1e-9 or abs(n[1]) > 1e-9 or abs(ax_w[1]) > 1e-9:
                raise ValueError("2D field needs a single linear array in the X-Z plane (no Y offset or roof)")
            pos.append(elements[i]); nrm.append(n); wax.append(ax_w); dl.append(delays[i]); wt.append(1.0)
            continue
        if not (elevation and elevation > 0):
            raise ValueError("3D field needs the element elevation (> 0)")
        lam = wedge.velocity / (f_max or probe.frequency)
        el_len = elevation                    # the element's own Y size, also for matrix arrays
        if probe.num_elements_y > 1 and el_len > probe.pitch_y * (1 + 1e-9):
            raise ValueError(f"the element elevation ({el_len * 1e3:g} mm) exceeds the secondary pitch "
                             f"({probe.pitch_y * 1e3:g} mm): set the element's own Y size")
        nw = max(1, math.ceil(element_width / (lam / 2)))
        ne = max(1, math.ceil(el_len / (lam / 2)))
        uw = (np.arange(nw) + 0.5) / nw - 0.5
        ue = (np.arange(ne) + 0.5) / ne - 0.5
        for a in uw:
            for b in ue:
                pos.append(elements[i] + a * element_width * ax_w + b * el_len * ax_e)
                nrm.append(n); wax.append(ax_w); dl.append(delays[i])
                wt.append(element_width * el_len / (nw * ne))
    return Sources(np.array(pos), np.array(nrm), np.array(wax), np.array(dl), np.array(wt),
                   float(element_width) if dim == 2 else 0.0, dim)


def hann_toneburst_spectrum(f, f0, cycles):
    """Fourier transform (kernel e^{-i 2 pi f t}, numpy's FFT sign) of a Hann tone burst,
    sin(2 pi f0 t) hann(t), 0 <= t <= cycles / f0, by direct quadrature; complex, unnormalised."""
    T = cycles / f0
    t = np.linspace(0.0, T, 385)          # 128 per cycle: trapezoid error far below the -40 dB band cut
    g = np.sin(2 * np.pi * f0 * t) * np.sin(np.pi * t / T) ** 2
    dt = t[1] - t[0]
    w = np.full(t.size, dt)
    w[[0, -1]] = dt / 2
    return (g * w) @ np.exp(-2j * np.pi * np.outer(t, np.atleast_1d(f)))


# ---------------------------------------------------------------------------------------------
# Field sections (grids for the views)
# ---------------------------------------------------------------------------------------------
def section_grid(lo, hi, step, max_points):
    """Two 1D grids spanning lo..hi (each a 2-tuple, m) at step (m), coarsened (and the step
    returned) so their product stays within max_points."""
    n = [max(2, int(math.floor((h - l) / step)) + 1) for l, h in zip(lo, hi)]
    while n[0] * n[1] > max_points:
        step *= 1.25
        n = [max(2, int(math.floor((h - l) / step)) + 1) for l, h in zip(lo, hi)]
    return [l + np.arange(k) * step for l, k in zip(lo, n)], step


def field_region(result, thickness_m, active_x):
    """
    X and Z extents (m) of the X-Z section for a law: the active interface points and the
    focus, with 20 mm beyond them on both sides (so a beam steered either way keeps its focus
    and focal region); from the surface to the component thickness, or 1.3 x the focus depth
    when no thickness is set.
    """
    ip = np.asarray(result["interface_points"])[active_x]
    fx, fz = result["fx"], result["fz"]
    x_lo = min(fx, float(np.min(ip[:, 0]))) - 0.020
    x_hi = max(fx, float(np.max(ip[:, 0]))) + 0.020
    z_hi = thickness_m if thickness_m > 0 else max(1.3 * fz, 0.010)
    return (x_lo, x_hi), (0.0, z_hi)


# ---------------------------------------------------------------------------------------------
# The field
# ---------------------------------------------------------------------------------------------
@dataclass
class FieldResult:
    amplitude: np.ndarray        # (m,) peak envelope (linear, unnormalised); NaN where no ray
    mode: str
    dim: int
    pulsed: bool


def _contributions(src: Sources, pts, wedge: Solid, part: Solid, mode):
    """Per (point, source): travel time, frequency-independent amplitude, polarisation (m, n, 3),
    and the wedge ray's sine across the element width (for the 2D sinc)."""
    c1 = wedge.cl
    c2 = part.cl if mode == "longitudinal" else part.cs
    E = src.positions[None, :, :]                       # (1, n, 3)
    P = pts[:, None, :]                                 # (m, 1, 3)
    a = -E[..., 2]                                      # source height above Z = 0
    b = P[..., 2]
    hvec = P[..., :2] - E[..., :2]
    d = np.linalg.norm(hvec, axis=-1)
    a, b = np.broadcast_arrays(a, b)
    s = fermat_entry(a, d, b, c1, c2)
    with np.errstate(invalid="ignore", divide="ignore"):
        h = np.where(d[..., None] > 0, hvec / np.where(d > 0, d, 1)[..., None], np.array([1.0, 0.0]))
    r1 = np.hypot(a, s)
    r2 = np.hypot(b, d - s)
    sin1, cos1 = s / r1, a / r1
    sin2, cos2 = (d - s) / r2, b / r2
    t = r1 / c1 + r2 / c2 + src.delays[None, :]
    # wedge ray direction and the angle from the element normal
    u1 = np.concatenate([h * sin1[..., None], cos1[..., None]], axis=-1)
    cos_t = np.einsum("mnk,nk->mn", u1, src.normals)
    sin_t = np.sqrt(np.clip(1 - cos_t ** 2, 0, None))
    sin_w = np.einsum("mnk,nk->mn", u1, src.width_axes)
    D = directivity_l(sin_t, cos_t, 0.0, wedge.cl / wedge.cs)
    D = np.where(cos_t > 0, D, 0)                       # rays leaving the back of the face
    coeff = coefficient_table(wedge, part, "TP" if mode == "longitudinal" else "TS")(sin1 / c1)
    A = src.weights[None, :] * D * coeff * spread(r1, r2, cos1, cos2, c1, c2, src.dim)
    if mode == "longitudinal":
        pol = np.concatenate([h * sin2[..., None], cos2[..., None]], axis=-1)
    else:
        pol = np.concatenate([h * cos2[..., None], -sin2[..., None]], axis=-1)
    return t, A, pol, sin_w


def _peak(env):
    """Row maxima of sampled envelopes, refined by a parabola through the top three samples."""
    i = np.argmax(env, axis=1)
    r = np.arange(env.shape[0])
    n = env.shape[1]
    y0, y1, y2 = env[r, (i - 1) % n], env[r, i], env[r, (i + 1) % n]
    den = y0 - 2 * y1 + y2
    with np.errstate(invalid="ignore", divide="ignore"):
        d = np.where(den < 0, 0.5 * (y0 - y2) / den, 0.0)
    return y1 - 0.25 * (y0 - y2) * d


def beam_field(src: Sources, points, wedge: Solid, part: Solid, mode="shear", f0=None,
               cycles=None, pulsed=True, progress=None):
    """
    Peak displacement envelope at points (m, 3) in the component (Z > 0, m). Pulsed: the Hann
    tone burst of ``cycles`` at ``f0``, broadband sum, peak over time. Not pulsed: continuous
    wave at f0, |sum|. Points at Z <= 0 are refused. progress(fraction) is called after each
    block of points, if given.
    """
    mode = mode.lower()
    if mode not in ("longitudinal", "shear"):
        raise ValueError("mode must be longitudinal or shear")
    pts = np.atleast_2d(np.asarray(points, dtype=float))
    if np.any(pts[:, 2] <= 0):
        raise ValueError("field points must lie in the component (Z > 0)")
    if not (f0 and f0 > 0):
        raise ValueError("the centre frequency must be positive")
    if pulsed and not (cycles and cycles > 0):
        raise ValueError("a pulsed field needs the number of cycles")
    if pulsed:
        fb = np.linspace(0, 4 * f0, 4097)[1:]
        Sb = np.abs(hann_toneburst_spectrum(fb, f0, cycles))
        band = fb[Sb >= SPECTRUM_FLOOR * Sb.max()]
        f_lo, f_hi = band.min(), band.max()
        T_pulse = cycles / f0
    out = np.empty(pts.shape[0])
    ncomp = 2 if src.dim == 2 else 3
    chunk = int(min(CHUNK, max(16, CHUNK_PAIRS // len(src.delays))))
    for k0 in range(0, pts.shape[0], chunk):
        P = pts[k0:k0 + chunk]
        t, A, pol, sin_w = _contributions(src, P, wedge, part, mode)
        if src.dim == 2:
            pol = pol[..., [0, 2]]
        if not pulsed:
            w = 2 * np.pi * f0
            lam_w = wedge.cl / f0
            Af = A * np.sinc(src.element_width * sin_w / lam_w)
            if src.dim == 2:
                Af = Af / math.sqrt(w)
            u = np.einsum("mn,mnc->mc", Af * np.exp(1j * w * (t - t.min(axis=1, keepdims=True))), pol)
            out[k0:k0 + chunk] = np.sqrt((np.abs(u) ** 2).sum(axis=1))
            if progress:
                progress(min(1.0, (k0 + chunk) / pts.shape[0]))
            continue
        tref = t.min(axis=1, keepdims=True)
        tau = t - tref
        span = float(tau.max()) + 4 * T_pulse
        dt = 1.0 / (4 * f_hi)
        N = 1 << int(math.ceil(math.log2(max(16, span / dt))))
        df = 1.0 / (N * dt)
        ks = np.arange(max(1, int(math.floor(f_lo / df))), int(math.ceil(f_hi / df)) + 1)
        S = hann_toneburst_spectrum(ks * df, f0, cycles)
        # A is in the e^{-i omega t} convention of the coefficients; numpy's inverse FFT builds
        # positive frequencies as e^{+i omega t}, so the conjugate is synthesised.
        A = np.conj(A)
        spec = np.zeros((P.shape[0], N, ncomp), dtype=complex)
        base = np.exp(-2j * np.pi * df * tau)          # e^{-i omega t}: time shift by tau
        ph = np.exp(-2j * np.pi * ks[0] * df * tau)
        # single precision inside the frequency loop (the map is shown to a few 0.01 dB)
        Ap = [(A * pol[..., c]).astype(np.complex64) for c in range(ncomp)]
        xw = (np.pi * src.element_width / wedge.cl * sin_w).astype(np.float32)   # pi x per Hz
        small = np.abs(xw) * f_hi < 1e-4
        xw_safe = np.where(small, 1.0, xw).astype(np.float32)
        ph = ph.astype(np.complex64)
        base = base.astype(np.complex64)
        for j, kk in enumerate(ks):
            f = kk * df
            y = xw_safe * np.float32(f)
            snc = np.where(small, np.float32(1), np.sin(y) / y)
            scale = 2 * S[j] / (math.sqrt(2 * np.pi * f) if src.dim == 2 else 1.0)
            g = snc * ph
            for c in range(ncomp):
                spec[:, kk, c] = scale * np.einsum("mn,mn->m", g, Ap[c])
            ph *= base
        # analytic signal (one-sided spectrum); N df = 1 / dt makes the discrete inverse the
        # continuous one, so a unit amplitude gives the burst's own envelope
        sig = np.fft.ifft(spec, axis=1) / dt
        env = np.sqrt((np.abs(sig) ** 2).sum(axis=2))
        out[k0:k0 + chunk] = _peak(env)
        if progress:
            progress(min(1.0, (k0 + chunk) / pts.shape[0]))
    return FieldResult(out, mode, src.dim, bool(pulsed))
