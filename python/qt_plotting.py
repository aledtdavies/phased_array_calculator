"""
Qt plot tabs: ray tracing (X-Z / Y-Z) and delays (bar chart or aperture maps); the 3D tab is
qt_view3d.py (PyVista).

matplotlib canvases (FigureCanvasQTAgg) drawing with scene.py, the same renderer as the Tk
tabs; navigation through navigation.LawNavigation. Plan step 2: same features as the Tk
window; PyVista and pyqtgraph replace the canvases in steps 3-4.
"""
from __future__ import annotations

import numpy as np
from qtpy import QtCore, QtWidgets
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from navigation import LawNavigation
from scene import COLOR_ELEMENT_INACTIVE, draw_aperture_maps, draw_projection


class LawTab(QtWidgets.QWidget):
    """A matplotlib canvas with law navigation: angle and skew sliders, step buttons, readout."""

    def __init__(self, projection=None, toolbar=False):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._make_view(lay, projection, toolbar)

        self.controls = QtWidgets.QGridLayout()
        lay.addLayout(self.controls)
        self.lbl_angle = QtWidgets.QLabel("Angle: 0.0°")
        self.lbl_angle.setMinimumWidth(110)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.lbl_skew = QtWidgets.QLabel("Skew: 0.0°")
        self.slider_skew = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.controls.addWidget(self.lbl_angle, 0, 0)
        self.controls.addWidget(self.slider, 0, 1)
        self.controls.addWidget(self.lbl_skew, 1, 0)
        self.controls.addWidget(self.slider_skew, 1, 1)
        step = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("◀")
        self.btn_next = QtWidgets.QPushButton("▶")
        for b in (self.btn_prev, self.btn_next):
            b.setFixedWidth(32)
            step.addWidget(b)
        self.lbl_law = QtWidgets.QLabel("")
        step.addWidget(self.lbl_law, 1)
        self.controls.addLayout(step, 2, 0, 1, 2)
        self.controls.setColumnStretch(1, 1)
        self.btn_prev.clicked.connect(lambda: self.step_law(-1))
        self.btn_next.clicked.connect(lambda: self.step_law(1))
        self.slider.valueChanged.connect(self._sliders_moved)
        self.slider_skew.valueChanged.connect(self._sliders_moved)

        self.nav = LawNavigation()
        self.solver = None
        self.focal_points = []
        self.wave_type = "longitudinal"
        self.is_matrix = False
        self.is_playing = False
        self._set_skew_visible(False)

    def _make_view(self, lay, projection, toolbar):
        """The tab's drawing surface: a matplotlib canvas (the 3D tab overrides this)."""
        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.figure.add_subplot(111, projection=projection)
        self.canvas = FigureCanvasQTAgg(self.figure)
        if toolbar:
            lay.addWidget(NavigationToolbar2QT(self.canvas, self))
        lay.addWidget(self.canvas, 1)

    def _blank_view(self):
        projection = "3d" if self.ax.name == "3d" else None
        self.figure.clear()
        self.ax = self.figure.add_subplot(111, projection=projection)
        self.canvas.draw_idle()

    # -- law set ------------------------------------------------------------
    @property
    def results(self):
        return self.nav.results

    @property
    def current_idx(self):
        return self.nav.current

    def update_navigation(self, solver, focal_points, wave_type, results, is_matrix):
        self.solver = solver
        self.focal_points = list(focal_points)
        self.wave_type = wave_type
        self.is_matrix = is_matrix
        self.nav.set_laws(results, len(self.focal_points))
        self._set_sliders(len(self.nav.angle_values) or len(self.focal_points),
                          len(self.nav.skew_values), 0, 0)
        self._set_skew_visible(is_matrix)
        self._sliders_moved()

    def clear_laws(self):
        """Forget the law set (a calculation gave no laws) and blank the plot."""
        if self.is_playing:
            self.toggle_play()
        self.solver = None
        self.focal_points = []
        self.nav.clear()
        self.lbl_law.setText("")
        self._blank_view()

    def _set_skew_visible(self, visible):
        self.lbl_skew.setVisible(visible)
        self.slider_skew.setVisible(visible)

    def _set_sliders(self, n_az, n_sk, i_az, i_sk):
        for s, n, i in ((self.slider, n_az, i_az), (self.slider_skew, n_sk, i_sk)):
            s.blockSignals(True)
            s.setRange(0, max(0, n - 1))
            s.setValue(i)
            s.blockSignals(False)

    def _sliders_moved(self, *_):
        if not self.focal_points:
            return
        self.nav.from_sliders(self.slider.value(), self.slider_skew.value() if self.is_matrix else 0)
        self._labels()
        if not self.is_playing:
            self.refresh_plot()

    def show_law(self, idx, redraw=True):
        """Select law idx directly (table row, step buttons, animation)."""
        if not self.focal_points:
            return
        i_az, i_sk = self.nav.select(idx)
        for s, v in ((self.slider, i_az), (self.slider_skew, i_sk)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        self._labels()
        if redraw:
            self.refresh_plot()

    def step_law(self, delta):
        if self.focal_points:
            self.show_law(self.nav.current + delta)

    def _labels(self):
        a, s, law = self.nav.readout()
        self.lbl_angle.setText(a)
        self.lbl_skew.setText(s)
        self.lbl_law.setText(law)

    def _get_law_data(self, idx):
        """(interface_points_mm, target_mm) for law idx, reusing the calculated law."""
        fp = self.focal_points[idx]
        r = self.results[idx]
        return r['interface_points'] * 1000, np.asarray(fp) * 1000

    def refresh_plot(self):
        raise NotImplementedError


class PlayMixin:
    """Play/Pause animation over every law in order."""

    def _add_play(self, row, column):
        self.play_btn = QtWidgets.QPushButton("Play")
        self.controls.addWidget(self.play_btn, row, column)
        self.play_btn.clicked.connect(self.toggle_play)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.animate)

    def toggle_play(self):
        if self.is_playing:
            self.is_playing = False
            self.play_btn.setText("Play")
            self.timer.stop()
        elif self.focal_points:     # nothing to play before laws are calculated
            self.is_playing = True
            self.play_btn.setText("Pause")
            self.timer.start()

    def animate(self):
        if not self.is_playing or not self.focal_points:
            return
        self.show_law(self.nav.current + 1)


class RayTab(PlayMixin, LawTab):
    """X-Z projection, plus Y-Z for matrix and dual probes; Show All overlays every law."""

    def __init__(self):
        super().__init__(toolbar=True)
        self._add_play(0, 2)
        self.chk_all = QtWidgets.QCheckBox("Show All")
        self.controls.addWidget(self.chk_all, 0, 3)
        self.chk_all.toggled.connect(lambda _: self.refresh_plot())
        self.component_thickness_mm = 0.0
        self.outline_mm = None

    def update_plot(self, solver, focal_points, wave_type, results=None, is_matrix=False,
                    component_thickness_mm=0.0, outline_mm=None):
        self.component_thickness_mm = component_thickness_mm
        self.outline_mm = outline_mm
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        self.figure.clear()
        probe = self.solver.probe
        linear = probe.num_elements_y == 1 and not hasattr(probe, "array_separation")
        if linear:
            self.ax = self.figure.add_subplot(111)
            axes = [(self.ax, 0)]
        else:
            ax_x, ax_y = self.figure.add_subplot(121), self.figure.add_subplot(122)
            axes = [(ax_x, 0), (ax_y, 1)]
            self.ax = ax_x
        show_all = self.chk_all.isChecked()
        indices = list(range(len(self.focal_points))) if show_all else [self.nav.current]
        for ax, dim in axes:
            draw_projection(ax, self.solver, self._get_law_data, indices, dim, self.wave_type,
                            show_all, component_thickness_mm=self.component_thickness_mm,
                            outline_mm=self.outline_mm)
        if show_all:
            self.lbl_angle.setText(f"All {len(self.focal_points)} Laws")
            if self.is_matrix:
                self.lbl_skew.setText("")
        self.figure.tight_layout()
        self.canvas.draw_idle()


class DelayTab(LawTab):
    """Delay profile: bar chart for linear probes, per-array delay maps for matrix probes."""

    def __init__(self):
        super().__init__()
        self.global_max_delay = None
        self.ax.set_title("Delay Profile")
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (microseconds)")
        self.ax.grid(True)

    def update_plot(self, solver, focal_points, wave_type, global_max_delay=None, results=None,
                    is_matrix=False):
        self.global_max_delay = global_max_delay
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        delays = np.asarray(self.results[self.nav.current]['delays_us'], dtype=float)
        probe = self.solver.probe
        vmax = self.global_max_delay
        vmax = vmax if (vmax is not None and np.isfinite(vmax) and vmax > 0) else None
        title = f"Delay Profile - Law {self.nav.current + 1}"
        self.figure.clear()
        if probe.num_elements_y > 1:
            draw_aperture_maps(self.figure, probe, delays, vmax=vmax,
                               title=f"{title} (numbering: {probe.element_order})")
            self.ax = self.figure.axes[0]
            self.canvas.draw_idle()
            return
        self.ax = self.figure.add_subplot(111)
        n = len(delays)
        ids = np.arange(1, n + 1)
        active = np.isfinite(delays)
        self.ax.bar(ids[active], delays[active], color='skyblue', edgecolor='black', label="Active")
        if (~active).any():
            self.ax.plot(ids[~active], np.zeros((~active).sum()), "x",
                         color=COLOR_ELEMENT_INACTIVE, label="Inactive")
            self.ax.legend(loc="upper right", fontsize=7)
        if hasattr(probe, "array_separation"):
            self.ax.axvline(n / 2 + 0.5, color="#64748b", linestyle=":", linewidth=1)
        self.ax.set_title(title)
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (μs)")
        self.ax.set_xlim(0.5, n + 0.5)
        if vmax:
            self.ax.set_ylim(0, vmax * 1.1)
        self.ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        self.figure.tight_layout()
        self.canvas.draw_idle()
