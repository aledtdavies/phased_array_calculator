"""
Qt tab base: law navigation (angle and skew sliders, step buttons, readout), Play, the dragged
focus, and element selection shared across tabs. The views themselves are qt_views2d.py
(pyqtgraph: ray tracing, delays) and qt_view3d.py (PyVista: 3D).
"""
from __future__ import annotations

import numpy as np
from qtpy import QtCore, QtWidgets

from navigation import LawNavigation


class LawTab(QtWidgets.QWidget):
    """
    A view with law navigation. Subclasses build the view (_make_view), blank it
    (_blank_view) and draw the current law (refresh_plot).

    The current law is a law of the sweep, or a "custom" law: one solved for a focus dragged
    in the X-Z view (set_custom). A custom law is not in the sweep or the table; any slider,
    step, table selection or new calculation returns to the sweep.
    """

    element_selected = QtCore.Signal(int)     # an element clicked in this view (internal index)
    law_changed = QtCore.Signal(int)          # this tab's navigation chose sweep law (index)

    def __init__(self):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._make_view(lay)

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
        self.custom = None
        self.selected_element = None
        self.coverage = None          # coverage.SweepCoverage, or None (off)
        self._stale = False
        self._set_skew_visible(False)

    # -- redraw scheduling ------------------------------------------------------------
    def request_redraw(self):
        """
        Redraw now, or, while this tab is hidden behind another in a shown window, when it is
        next shown: Play, steps and a dragged focus then cost only the visible tab.
        """
        if self.window().isVisible() and not self.isVisible():
            self._stale = True
        else:
            self._stale = False
            self.refresh_plot()

    def showEvent(self, event):      # noqa: N802 - Qt's name
        super().showEvent(event)
        if self._stale:
            self._stale = False
            self.refresh_plot()

    # -- view (subclasses) ----------------------------------------------------------
    def _make_view(self, lay):
        raise NotImplementedError

    def _blank_view(self):
        raise NotImplementedError

    def refresh_plot(self):
        raise NotImplementedError

    def highlight_element(self, idx):
        """Show element idx as selected (driven by any tab; never re-emits element_selected)."""
        self.selected_element = idx

    # -- law set --------------------------------------------------------------------
    @property
    def results(self):
        return self.nav.results

    @property
    def current_idx(self):
        return self.nav.current

    def current_result(self):
        """The current law's result dict (session.calculate's), or the custom law's."""
        return self.custom["result"] if self.custom else self.results[self.nav.current]

    def current_focal(self):
        """The current law's focus (m)."""
        return np.asarray(self.custom["focal"] if self.custom else self.focal_points[self.nav.current])

    def update_navigation(self, solver, focal_points, wave_type, results, is_matrix):
        self.solver = solver
        self.focal_points = list(focal_points)
        self.wave_type = wave_type
        self.is_matrix = is_matrix
        self.custom = None
        self.selected_element = None
        self.coverage = None          # the window sets the new calculation's coverage
        self.nav.set_laws(results, len(self.focal_points))
        self._set_sliders(len(self.nav.angle_values) or len(self.focal_points),
                          len(self.nav.skew_values), 0, 0)
        self._set_skew_visible(is_matrix)
        self._sliders_moved()

    def clear_laws(self):
        """Forget the law set (a calculation gave no laws) and blank the view."""
        if self.is_playing:
            if getattr(self, "play_controller", None) is not None:
                self.play_controller.stop()
            else:
                self.toggle_play()
        self.solver = None
        self.focal_points = []
        self.custom = None
        self.selected_element = None
        self.nav.clear()
        self.lbl_law.setText("")
        self._blank_view()

    def set_coverage(self, cov):
        """Show (or, with None, hide) the sweep's coverage and the central ray with its skips."""
        self.coverage = cov
        self._coverage_changed()
        self.request_redraw()

    def _coverage_changed(self):
        """Subclasses rebuild whatever draws the coverage."""

    def coverage_path_mm(self):
        """The current law's (or dragged focus's) central-ray path in mm, or None."""
        if self.coverage is None or not self.focal_points:
            return None
        path = (self.coverage.path_for(self.custom["focal"]) if self.custom
                else self.coverage.paths[self.nav.current])
        # From the aperture centre: the wedge leg, then the legs in the component.
        return np.vstack([self.solver.aperture_centre()[None, :], path]) * 1e3

    def set_custom(self, result, focal):
        """Show a law solved for a dragged focus (result as session.calculate's; focal in m)."""
        if not self.focal_points:
            return
        self.custom = {"result": result, "focal": tuple(focal)}
        f = np.asarray(focal) * 1e3
        self.lbl_law.setText(f"Dragged focus (not in the sweep): F = ({f[0]:.1f}, {f[1]:.1f}, {f[2]:.1f}) mm")
        self.request_redraw()

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
        self.custom = None
        self.nav.from_sliders(self.slider.value(), self.slider_skew.value() if self.is_matrix else 0)
        self._labels()
        self.request_redraw()
        self.law_changed.emit(self.nav.current)

    def show_law(self, idx, redraw=True, notify=True):
        """
        Select law idx directly (step buttons, animation, table row). The choice is announced
        (law_changed) so every tab shows the same law, unless notify is False (the window
        relaying another tab's choice to this one).
        """
        if not self.focal_points:
            return
        self.custom = None
        i_az, i_sk = self.nav.select(idx)
        for s, v in ((self.slider, i_az), (self.slider_skew, i_sk)):
            s.blockSignals(True)
            s.setValue(v)
            s.blockSignals(False)
        self._labels()
        if redraw:
            self.request_redraw()
        if notify:
            self.law_changed.emit(self.nav.current)

    def step_law(self, delta):
        if self.focal_points:
            self.show_law(self.nav.current + delta)

    def _labels(self):
        a, s, law = self.nav.readout()
        self.lbl_angle.setText(a)
        self.lbl_skew.setText(s)
        self.lbl_law.setText(law)

    def _get_law_data(self, idx):
        """(interface_points_mm, target_mm) for law idx, or for the custom law when shown."""
        if self.custom and idx == self.nav.current:
            return self.custom["result"]["interface_points"] * 1000, np.asarray(self.custom["focal"]) * 1000
        fp = self.focal_points[idx]
        r = self.results[idx]
        return r['interface_points'] * 1000, np.asarray(fp) * 1000


class PlayController(QtCore.QObject):
    """
    One Play for a window: a single timer steps the shared current law (the visible tab steps
    and the window relays it), and every Play button shows the same state. Tabs attached to a
    controller delegate Play to it, so two tabs can never play at once.
    """

    def __init__(self, tabs, interval_ms=100):
        super().__init__()
        self.tabs = list(tabs)
        self.playing = False
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.tick)
        for t in self.tabs:
            t.play_controller = self

    def source(self):
        """The tab that steps: the visible one with laws, else the first with laws."""
        with_laws = [t for t in self.tabs if t.focal_points]
        visible = [t for t in with_laws if t.isVisible()]
        return (visible or with_laws or [None])[0]

    def toggle(self):
        if self.playing:
            self.stop()
        elif self.source() is not None:     # nothing to play before laws are calculated
            self._set(True)
            self.timer.start()

    def stop(self):
        self.timer.stop()
        self._set(False)

    def tick(self):
        src = self.source()
        if not self.playing or src is None:
            return
        src.show_law(src.nav.current + 1)

    def _set(self, playing):
        self.playing = playing
        for t in self.tabs:
            t.is_playing = playing
            if hasattr(t, "play_btn"):
                t.play_btn.setText("Pause" if playing else "Play")


class PlayMixin:
    """Play/Pause over every law in order: the window's PlayController, or this tab alone."""

    play_controller = None

    def _add_play(self, row, column):
        self.play_btn = QtWidgets.QPushButton("Play")
        self.controls.addWidget(self.play_btn, row, column)
        self.play_btn.clicked.connect(self.toggle_play)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.animate)

    def toggle_play(self):
        if self.play_controller is not None:
            self.play_controller.toggle()
            return
        if self.is_playing:
            self.is_playing = False
            self.play_btn.setText("Play")
            self.timer.stop()
        elif self.focal_points:     # nothing to play before laws are calculated
            self.is_playing = True
            self.play_btn.setText("Pause")
            self.timer.start()

    def animate(self):
        if self.play_controller is not None:
            self.play_controller.tick()
            return
        if not self.is_playing or not self.focal_points:
            return
        self.show_law(self.nav.current + 1)
