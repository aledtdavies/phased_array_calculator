"""Beam field model (plan step 6): invariants, not stored numbers."""
import math
import unittest

import numpy as np

from beam_field import (Solid, Sources, beam_field, element_sources, fermat_entry,
                        hann_toneburst_spectrum, interface_coefficients, spread)
from delay_law import DelayLaw
from material import Material
from probe import create_probe_assembly
from wedge import Wedge

REXOLITE = Solid(1049.0, 2337.0, 1157.0)
STEEL = Solid(7900.0, 5900.0, 3230.0)
ALU = Solid(2700.0, 6320.0, 3080.0)


def flux(m: Solid, c, coeff, eta):
    """Normal energy flux of a unit-incident-normalised wave (propagating part only)."""
    return m.rho * c ** 2 * np.abs(np.real(eta)) * np.abs(coeff) ** 2


class TestInterfaceCoefficients(unittest.TestCase):
    def check_energy(self, up, lo, incident):
        c_in = up.cl if incident == "P" else up.cs
        th = np.radians(np.linspace(0, 89, 179))
        p = np.sin(th) / c_in
        r = interface_coefficients(p, up, lo, incident)
        eta = lambda c: np.sqrt((1 / c ** 2 - p ** 2).astype(complex))
        e_in = up.rho * c_in ** 2 * np.real(eta(c_in))
        e_out = (flux(up, up.cl, r["RP"], eta(up.cl)) + flux(up, up.cs, r["RS"], eta(up.cs))
                 + flux(lo, lo.cl, r["TP"], eta(lo.cl)) + flux(lo, lo.cs, r["TS"], eta(lo.cs)))
        np.testing.assert_allclose(e_out, e_in, rtol=1e-9)

    def test_energy_is_conserved_at_every_angle(self):
        for up, lo in ((REXOLITE, STEEL), (STEEL, REXOLITE), (STEEL, ALU), (ALU, REXOLITE)):
            for inc in ("P", "S"):
                with self.subTest(up=up, lo=lo, inc=inc):
                    self.check_energy(up, lo, inc)

    def test_identical_media_transmit_everything(self):
        p = np.sin(np.radians([0, 20, 50])) / STEEL.cl
        r = interface_coefficients(p, STEEL, STEEL, "P")
        np.testing.assert_allclose(r["TP"], 1, atol=1e-12)
        for k in ("RP", "RS", "TS"):
            np.testing.assert_allclose(r[k], 0, atol=1e-12)
        r = interface_coefficients(np.sin(np.radians(30)) / STEEL.cs, STEEL, STEEL, "S")
        self.assertAlmostEqual(complex(r["TS"]), 1, places=12)

    def test_normal_incidence_matches_the_impedance_formula(self):
        r = interface_coefficients(0.0, REXOLITE, STEEL, "P")
        z1, z2 = REXOLITE.rho * REXOLITE.cl, STEEL.rho * STEEL.cl
        self.assertAlmostEqual(complex(r["TP"]), 2 * z1 / (z1 + z2), places=12)
        self.assertAlmostEqual(abs(complex(r["RP"])), abs(z1 - z2) / (z1 + z2), places=12)
        self.assertAlmostEqual(abs(complex(r["TS"])), 0, places=12)

    def test_shear_from_a_longitudinal_wave_has_its_known_signs(self):
        """No converted wave at normal incidence; converted shear grows from zero off normal."""
        th = np.radians([1, 10, 20])
        r = interface_coefficients(np.sin(th) / REXOLITE.cl, REXOLITE, STEEL, "P")
        self.assertTrue(np.all(np.abs(r["TS"]) > 0))
        self.assertTrue(np.all(np.diff(np.abs(r["TS"])) > 0))


class TestCoefficientTable(unittest.TestCase):
    def test_the_table_matches_the_exact_coefficients(self):
        from beam_field import coefficient_table
        rng = np.random.default_rng(3)
        p = rng.uniform(0, 1 / REXOLITE.cl, 4000)
        for key in ("TP", "TS"):
            exact = interface_coefficients(p, REXOLITE, STEEL, "P")[key]
            tab = coefficient_table(REXOLITE, STEEL, key)(p)
            err = np.abs(tab - exact) / np.max(np.abs(exact))
            self.assertLess(np.max(err), 0.01, key)
            self.assertLess(np.median(err), 1e-6, key)


class TestRays(unittest.TestCase):
    def test_fermat_entry_obeys_snell_and_is_the_minimum_time(self):
        rng = np.random.default_rng(1)
        a, d, b = rng.uniform(1e-3, 0.05, 50), rng.uniform(0, 0.1, 50), rng.uniform(1e-3, 0.05, 50)
        s = fermat_entry(a, d, b, 2337.0, 3230.0)
        np.testing.assert_allclose(s / np.hypot(a, s) / 2337.0,
                                   (d - s) / np.hypot(b, d - s) / 3230.0, rtol=1e-9, atol=1e-12)
        for i in range(5):
            x = np.linspace(0, d[i], 20001)
            t = np.hypot(a[i], x) / 2337.0 + np.hypot(b[i], d[i] - x) / 3230.0
            self.assertLessEqual(np.hypot(a[i], s[i]) / 2337.0 + np.hypot(b[i], d[i] - s[i]) / 3230.0,
                                 t.min() + 1e-15)

    def _ray(self, a, th1, r2, c1, c2, phi=0.0):
        """End point (3D) of the ray from (0, 0, -a) leaving at th1 from vertical, azimuth phi,
        travelling r2 beyond the interface."""
        s1 = math.sin(th1)
        th2 = math.asin(s1 * c2 / c1)
        x = a * math.tan(th1) + r2 * math.sin(th2)
        return np.array([x * math.cos(phi), x * math.sin(phi), r2 * math.cos(th2)]), th2

    def test_spreading_matches_a_numerical_ray_tube(self):
        """Energy in a ray tube: |T spread|^2 rho2 c2 W2 = tau_E rho1 c1 W1 (unit amplitude at
        unit distance in the wedge), for 2D (in-plane) and 3D (with the azimuthal width)."""
        a, c1, c2 = 0.012, REXOLITE.cl, STEEL.cs
        h = 1e-7
        for th1_deg in (5.0, 20.0, 30.0, 35.0):
            for r2 in (0.005, 0.03, 0.08):
                th1 = math.radians(th1_deg)
                p0, th2 = self._ray(a, th1, r2, c1, c2)
                p1, _ = self._ray(a, th1 + h, r2, c1, c2)
                u2 = np.array([math.sin(th2), 0, math.cos(th2)])
                dp = p1 - p0
                W2 = np.linalg.norm(dp - (dp @ u2) * u2) / h        # tube width per radian
                r1 = a / math.cos(th1)
                sp2 = spread(r1, r2, math.cos(th1), math.cos(th2), c1, c2, 2)
                # Geometric identity behind the energy balance with plane-wave coefficients:
                # |A2|^2 W2 cos(th1) / cos(th2) = 1 (2D), A2 = spread with unit coefficients.
                self.assertAlmostEqual(sp2 ** 2 * W2 * math.cos(th1) / math.cos(th2) * c2 / c1
                                       * (c1 / c2), 1.0, places=5)
                # 3D: the azimuthal width is the ray's horizontal distance from the source axis
                p2, _ = self._ray(a, th1, r2, c1, c2, phi=h)
                Wphi = np.linalg.norm(p2 - p0) / h
                sp3 = spread(r1, r2, math.cos(th1), math.cos(th2), c1, c2, 3)
                self.assertAlmostEqual(sp3 ** 2 * W2 * Wphi * math.cos(th1) / math.cos(th2)
                                       / math.sin(th1), 1.0, places=5)


def _single(pos, delay=0.0, weight=1.0, dim=3):
    return Sources(np.array([pos], dtype=float), np.array([[0.0, 0, 1]]), np.array([[1.0, 0, 0]]),
                   np.array([delay]), np.array([weight]), 0.0, dim)


def _merge(*srcs):
    return Sources(*(np.concatenate([getattr(s, k) for s in srcs]) for k in
                     ("positions", "normals", "width_axes", "delays", "weights")), 0.0, srcs[0].dim)


class TestSynthesis(unittest.TestCase):
    f0, cycles = 2.25e6, 3

    def pulse_peak(self):
        """Peak of the Hann burst's envelope (its analytic signal), from a fine direct sampling."""
        T = self.cycles / self.f0
        n = 1 << 16
        t = np.arange(n) * (8 * T / n)
        g = np.where(t <= T, np.sin(2 * np.pi * self.f0 * t) * np.sin(np.pi * t / T) ** 2, 0)
        G = np.fft.fft(g)
        G[1:n // 2] *= 2
        G[n // 2 + 1:] = 0
        dt = t[1] - t[0]
        return np.abs(np.fft.ifft(G)).max(), dt

    def test_one_source_gives_its_amplitude_times_the_pulse_envelope(self):
        src = _single([0.0, 0.0, -0.01])
        pts = np.array([[0.005, 0.0, 0.02], [0.02, 0.003, 0.03]])
        cw = beam_field(src, pts, REXOLITE, STEEL, "shear", self.f0, pulsed=False).amplitude
        pk = beam_field(src, pts, REXOLITE, STEEL, "shear", self.f0, self.cycles).amplitude
        g, _ = self.pulse_peak()
        # 3D point sources carry no frequency factor; the coefficient varies a little across the band
        np.testing.assert_allclose(pk / g, cw, rtol=2e-3)

    def test_separate_arrivals_do_not_add_and_coincident_ones_do(self):
        a = _single([0.0, 0.0, -0.01])
        b = _single([0.0, 0.0, -0.01], delay=20e-6)      # far later than the pulse length
        pt = np.array([[0.004, 0.0, 0.02]])
        one = beam_field(a, pt, REXOLITE, STEEL, "shear", self.f0, self.cycles).amplitude
        two_apart = beam_field(_merge(a, b), pt, REXOLITE, STEEL, "shear", self.f0, self.cycles).amplitude
        two_together = beam_field(_merge(a, a), pt, REXOLITE, STEEL, "shear", self.f0, self.cycles).amplitude
        # the pulse spectrum is cut at -40 dB (SPECTRUM_FLOOR), so windows of different
        # lengths agree to about 1e-3 (0.01 dB), not to rounding
        np.testing.assert_allclose(two_apart, one, rtol=1e-3)
        np.testing.assert_allclose(two_together, 2 * one, rtol=1e-9)

    def test_long_pulses_converge_to_the_continuous_wave_with_complex_coefficients(self):
        """At 45 degrees shear the wedge-to-steel coefficient is complex (the steel L wave is
        evanescent), so this checks the phase convention of the pulsed synthesis."""
        p = create_probe_assembly("Linear", 16, 0.75e-3, 2.25e6)
        s = DelayLaw(p, Wedge(36.0, 0.005, 2337.0, 0.004), Material(5900.0, 3230.0))
        law = s.calculate_law(0.03, 0.0, 0.02, "shear")
        src = element_sources(s, law["delays"], 0.55e-3, elevation=0.012, dim=3)
        pts = np.array([[0.03, 0.0, 0.02], [0.025, 0.0, 0.02], [0.035, 0.002, 0.024]])
        cw = beam_field(src, pts, REXOLITE, STEEL, "shear", self.f0, pulsed=False).amplitude
        long = beam_field(src, pts, REXOLITE, STEEL, "shear", self.f0, 60).amplitude
        ratio = long / cw
        np.testing.assert_allclose(ratio / ratio[0], 1, rtol=0.01)

    def test_the_focus_is_the_brightest_point_nearby(self):
        p = create_probe_assembly("Linear", 32, 0.75e-3, 2.25e6)
        s = DelayLaw(p, Wedge(36.0, 0.005, 2337.0, 0.004), Material(5900.0, 3230.0))
        F = (0.035, 0.0, 0.015)
        law = s.calculate_law(*F, "shear")
        src = element_sources(s, law["delays"], 0.55e-3, dim=2)
        ring = [(F[0] + 0.004 * math.cos(t), 0.0, F[2] + 0.004 * math.sin(t))
                for t in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
        amp = beam_field(src, np.array([F] + ring), REXOLITE, STEEL, "shear", self.f0, self.cycles).amplitude
        self.assertTrue(np.all(amp[0] > amp[1:]), amp)

    def test_refusals(self):
        src = _single([0.0, 0.0, -0.01])
        with self.assertRaises(ValueError):
            beam_field(src, [[0.0, 0.0, 0.0]], REXOLITE, STEEL, "shear", self.f0, 3)
        with self.assertRaises(ValueError):
            beam_field(src, [[0.0, 0.0, 0.01]], REXOLITE, STEEL, "shear", self.f0, None)
        with self.assertRaises(ValueError):
            Solid(1000.0, 2000.0, 1500.0)
        p = create_probe_assembly("Matrix", 8, 1e-3, 2.25e6, num_elements_y=4, pitch_y=1.2e-3)
        s = DelayLaw(p, Wedge(36.0, 0.005, 2337.0, 0.004), Material(5900.0, 3230.0))
        law = s.calculate_law(0.03, 0.0, 0.02, "shear")
        with self.assertRaises(ValueError):
            element_sources(s, law["delays"], 0.9e-3, dim=2)        # matrix: not a 2D section


class TestSpectrum(unittest.TestCase):
    def test_peak_near_the_centre_frequency(self):
        f = np.linspace(0.5e6, 4e6, 701)
        S = np.abs(hann_toneburst_spectrum(f, 2.25e6, 3))
        self.assertLess(abs(f[np.argmax(S)] - 2.25e6), 0.1e6)


if __name__ == "__main__":
    unittest.main()
