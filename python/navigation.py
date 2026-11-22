"""
Law navigation, toolkit-free: which law the angle/skew sliders, the step buttons, a table
row or the animation select. The Qt tabs use it.

The angle and skew sliders index the sorted distinct angles and skews of the law set. A
slider pair picks the first law with that (angle, skew); when that pair does not exist
(sound-path Y sweeps give angle-dependent skews) it picks the first law at that angle. A law
chosen by index (step, table, animation) is kept while the sliders still point at its
(angle, skew), so laws that share an angle and skew (Y-sweep targets) stay reachable.
"""
from __future__ import annotations


class LawNavigation:
    def __init__(self):
        self.clear()

    def clear(self):
        """No laws."""
        self.results = []
        self.n_laws = 0
        self.angle_values = []
        self.skew_values = []
        self.index_map = {}
        self.current = 0
        self._pinned = None

    def set_laws(self, results, n_laws=None):
        """A new law set (session.Calculation.results); selects law 0."""
        self.clear()
        self.results = list(results or [])
        self.n_laws = len(self.results) if n_laws is None else n_laws
        if self.results:
            self.angle_values = sorted({r['angle'] for r in self.results})
            self.skew_values = sorted({r.get('skew', 0.0) for r in self.results})
            for i, r in enumerate(self.results):
                self.index_map.setdefault((r['angle'], r.get('skew', 0.0)), i)

    def _key(self, idx):
        r = self.results[idx]
        return r['angle'], r.get('skew', 0.0)

    def from_sliders(self, i_az, i_sk=0):
        """The law the sliders point at (and make it current)."""
        if not self.n_laws:
            return 0
        if not self.results:
            self.current = min(max(int(i_az), 0), self.n_laws - 1)
            return self.current
        az = self.angle_values[min(max(int(i_az), 0), len(self.angle_values) - 1)]
        sk = self.skew_values[min(max(int(i_sk), 0), len(self.skew_values) - 1)]
        idx = self.index_map.get((az, sk))
        if idx is None:
            idx = next((i for i, r in enumerate(self.results) if r['angle'] == az), 0)
        if self._pinned is not None and self._pinned < len(self.results):
            if self._key(self._pinned) == (az, sk):
                idx = self._pinned
            else:
                self._pinned = None
        self.current = min(max(idx, 0), self.n_laws - 1)
        return self.current

    def select(self, idx):
        """Choose law idx (wrapping); returns the slider positions (i_az, i_sk) that show it."""
        if not self.n_laws:
            return 0, 0
        idx = int(idx) % self.n_laws
        self.current = idx
        self._pinned = idx
        return self.slider_positions(idx)

    def step(self, delta):
        return self.select(self.current + delta)

    def slider_positions(self, idx):
        if idx < len(self.results):
            az, sk = self._key(idx)
            return self.angle_values.index(az), self.skew_values.index(sk)
        return idx, 0

    def readout(self):
        """(angle text, skew text, law text) for the current law."""
        if not self.n_laws:
            return "", "", ""
        if self.current < len(self.results):
            r = self.results[self.current]
            return (f"Angle: {r['angle']:.1f}°", f"Skew: {r.get('skew', 0.0):.1f}°",
                    f"Law {self.current + 1}/{self.n_laws}  F = ({r['fx']*1e3:.1f}, "
                    f"{r.get('fy', 0.0)*1e3:.1f}, {r['fz']*1e3:.1f}) mm")
        return f"Index: {self.current + 1}", "", f"Law {self.current + 1}/{self.n_laws}"
