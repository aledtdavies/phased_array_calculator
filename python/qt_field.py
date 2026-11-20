"""
The Qt window's Beam Field tab (plan step 6): the selected law's beam in the component, from
beam_field's ray model, as a dB map over the X-Z section (and, in 3D mode, a Y-Z section
through the focus), with the -6 dB contour and the beam's axis and width (beam_metrics).

Frame: global, millimetres on screen, Z (depth) drawn downward; Y-Z is seen from -X. Colours:
turbo, 0 to -30 dB re the map's maximum (the suite's dB-map convention).

The field is computed on request (it takes seconds) in a worker thread. A field belongs to the
law it was computed for: when the law, the setup or the inputs change it is marked stale and
taken out of the 3D view until it is computed again.

Validated case: 2D mode, pulsed, against buildFE's FE solve (validation/beam_field). 3D mode
uses the same ingredients with point sources over each element and is not separately validated.
"""
from __future__ import annotations

import math

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from beam_field import (MODEL_NOTE, Solid, beam_field, element_sources, field_region,
                        section_grid)
from beam_metrics import beam_axis

FLOOR_DB = -30.0
MAX_POINTS = {2: 40000, 3: 12000}     # per section; the grid step grows to stay below
MODELS = ["2D: line elements (X-Z section)", "3D: rectangular elements (X-Z and Y-Z)"]
PULSES = ["Pulsed (Hann burst)", "Continuous wave"]


class FieldWorker(QtCore.QThread):
    progress = QtCore.Signal(float)
    done = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            self.done.emit(run_job(self.job, self.progress.emit))
        except (ValueError, ArithmeticError, np.linalg.LinAlgError) as e:
            self.failed.emit(str(e))


def run_job(job, progress=None):
    """Compute the sections of a job (see FieldTab.job); returns the job with 'sections'."""
    src = element_sources(job["solver"], job["delays"], job["width"], job["elevation"], job["dim"],
                          f_max=job["f0"] * (1.5 if job["pulsed"] else 1.0))
    secs = job["sections"]
    total = sum(s["points"].shape[0] for s in secs)
    done = 0
    for s in secs:
        n = s["points"].shape[0]

        def prog(f, done=done, n=n):
            if progress:
                progress((done + f * n) / total)
        amp = beam_field(src, s["points"], job["wedge"], job["part"], job["mode"], job["f0"],
                         job["cycles"], job["pulsed"], progress=prog).amplitude
        s["amp"] = amp.reshape(s["shape"])
        done += n
    peak = max(np.nanmax(s["amp"]) for s in secs)
    for s in secs:
        with np.errstate(divide="ignore"):
            s["db"] = np.maximum(20 * np.log10(s["amp"] / peak), FLOOR_DB)
    return job


class FieldTab(QtWidgets.QWidget):
    """Beam field of the current law. Emits field_changed(slices or None) for the 3D view."""

    field_changed = QtCore.Signal(object)

    def __init__(self):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        g = QtWidgets.QGridLayout()
        lay.addLayout(g)

        def spin(lo, hi, val, dec, suffix=""):
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(lo, hi)
            w.setDecimals(dec)
            w.setValue(val)
            w.setSuffix(suffix)
            w.setKeyboardTracking(False)
            return w

        self.model = QtWidgets.QComboBox()
        self.model.addItems(MODELS)
        self.pulse = QtWidgets.QComboBox()
        self.pulse.addItems(PULSES)
        self.cycles = spin(0.5, 50, 3, 1)
        self.step = spin(0.05, 5, 0.5, 2, " mm")
        self.width = spin(0.01, 100, 0.5, 3, " mm")
        self.elevation = spin(0.1, 200, 10, 2, " mm")
        self.wedge_cs = spin(100, 10000, 1157, 0, " m/s")
        self.wedge_rho = spin(100, 30000, 1049, 0, " kg/m³")
        self.part_rho = spin(100, 30000, 7850, 0, " kg/m³")
        self.width.setToolTip("Element width along the pitch (the catalogue value when the probe came from one)")
        self.elevation.setToolTip("Element length across the array (3D mode)")
        self.wedge_cs.setToolTip("Wedge shear speed: needed for the element directivity and the "
                                 "wedge-to-component transmission (the catalogue value when the wedge came from one)")
        self.wedge_rho.setToolTip("Wedge density, for the transmission coefficient")
        self.part_rho.setToolTip("Component density, for the transmission coefficient")
        row = [("Model:", self.model), ("Pulse:", self.pulse), ("Cycles:", self.cycles), ("Grid:", self.step)]
        row2 = [("Element width:", self.width), ("Elevation:", self.elevation), ("Wedge S-wave:", self.wedge_cs),
                ("Wedge density:", self.wedge_rho), ("Component density:", self.part_rho)]
        for r, items in enumerate((row, row2)):
            for c, (label, w) in enumerate(items):
                g.addWidget(QtWidgets.QLabel(label), r, 2 * c)
                g.addWidget(w, r, 2 * c + 1)
        self.compute_btn = QtWidgets.QPushButton("Compute field")
        self.chk_3d = QtWidgets.QCheckBox("Show in 3D view")
        self.chk_3d.setChecked(True)
        self.status = QtWidgets.QLabel("Calculate laws, then compute the field of the selected law.")
        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setVisible(False)
        self.bar.setMaximumWidth(160)
        g.addWidget(self.compute_btn, 2, 0, 1, 2)
        g.addWidget(self.chk_3d, 2, 2, 1, 2)
        g.addWidget(self.bar, 2, 4, 1, 2)
        g.addWidget(self.status, 2, 6, 1, 4)
        self.note = QtWidgets.QLabel(MODEL_NOTE + ". Validated in 2D against an FE solve; 3D not separately validated.")
        self.note.setStyleSheet("color: #64748b")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)

        self.view = pg.GraphicsLayoutWidget()
        lay.addWidget(self.view, 1)
        self.cmap = pg.colormap.get("turbo")
        self.plots = []

        self.context = None          # the law the window shows: see set_context
        self.setup_dirty = False     # a setup panel edited since the laws were calculated
        self.setup_rev = 0           # counts setup edits; a job records the count it started at
        self.job = None              # the computed (or running) field
        self.worker = None
        self.compute_btn.clicked.connect(lambda: self.compute())
        self.chk_3d.toggled.connect(lambda _: self._emit())
        self.model.currentIndexChanged.connect(self._model_changed)
        for w in (self.pulse, self.model):
            w.currentIndexChanged.connect(lambda _: self._inputs_changed())
        for w in (self.cycles, self.step, self.width, self.elevation, self.wedge_cs, self.wedge_rho, self.part_rho):
            w.valueChanged.connect(lambda _: self._inputs_changed())
        self._model_changed()
        self.DEFAULTS = self.get_values()

    # -- inputs ------------------------------------------------------------------------
    def get_values(self):
        return {"model": "3D" if self.model.currentIndex() else "2D",
                "pulsed": self.pulse.currentIndex() == 0, "cycles": self.cycles.value(),
                "grid_mm": self.step.value(), "element_width_mm": self.width.value(),
                "elevation_mm": self.elevation.value(), "wedge_shear_ms": self.wedge_cs.value(),
                "wedge_density": self.wedge_rho.value(), "component_density": self.part_rho.value()}

    def is_default(self):
        return self.get_values() == self.DEFAULTS

    def set_values(self, v):
        if "model" in v:
            self.model.setCurrentIndex(1 if v["model"] == "3D" else 0)
        if "pulsed" in v:
            self.pulse.setCurrentIndex(0 if v["pulsed"] else 1)
        for key, w in (("cycles", self.cycles), ("grid_mm", self.step), ("element_width_mm", self.width),
                       ("elevation_mm", self.elevation), ("wedge_shear_ms", self.wedge_cs),
                       ("wedge_density", self.wedge_rho), ("component_density", self.part_rho)):
            if v.get(key) is not None:
                w.setValue(float(v[key]))

    def _model_changed(self, *_):
        is3d = self.model.currentIndex() == 1
        self.elevation.setEnabled(is3d)

    def _inputs_changed(self):
        self._stale("inputs changed")

    # -- context -----------------------------------------------------------------------
    def set_context(self, solver, result, wave_type, thickness_mm, label=""):
        """The law the window now shows (result: a law's result dict), or None."""
        new = None if solver is None or result is None else dict(
            solver=solver, result=result, wave_type=wave_type, thickness_mm=thickness_mm, label=label)
        same = (self.context is not None and new is not None and self.context["solver"] is solver
                and np.allclose([result["fx"], result["fy"], result["fz"]],
                                [self.context["result"][k] for k in ("fx", "fy", "fz")])
                and np.array_equal(np.nan_to_num(result["delays_us"]),
                                   np.nan_to_num(self.context["result"]["delays_us"]))
                and thickness_mm == self.context["thickness_mm"])
        self.context = new
        if not same:
            self._stale("the law changed" if new else "no law")

    def setup_edited(self):
        """A setup panel (probe, wedge, component, aperture) changed: the laws shown no longer
        match it, so the field goes stale and cannot be computed until the laws are recalculated."""
        self.setup_dirty = True
        self.setup_rev += 1
        self._stale("the setup changed")

    def _stale(self, why):
        if self.job is not None and "sections" in self.job and self.job.get("fresh", False):
            self.job["fresh"] = False
            self.status.setText(f"Field shown is stale ({why}): compute again for the current law.")
            self.field_changed.emit(None)

    # -- computing ---------------------------------------------------------------------
    def make_job(self):
        """The computation for the current context and inputs; ValueError if it cannot run."""
        c = self.context
        if c is None:
            raise ValueError("calculate laws first")
        if self.setup_dirty:
            raise ValueError("the setup changed since the laws were calculated: press Calculate Laws")
        v = self.get_values()
        solver, r = c["solver"], c["result"]
        dim = 3 if v["model"] == "3D" else 2
        mode = c["wave_type"].lower()
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
        (xl, xh), (zl, zh) = field_region(r, c["thickness_mm"] * 1e-3, active)
        step = v["grid_mm"] * 1e-3
        (X, Z), used = section_grid((xl, step), (xh, zh), step, MAX_POINTS[dim])
        y0 = float(np.mean(solver._geometry()[0][active][:, 1])) if dim == 3 else 0.0
        GX, GZ = np.meshgrid(X, Z)
        sections = [dict(name="X-Z", h=X, z=Z, shape=GX.shape, fixed=("Y", y0),
                         points=np.column_stack([GX.ravel(), np.full(GX.size, y0), GZ.ravel()]))]
        if dim == 3:
            half = max(v["elevation_mm"] * 1e-3, 0.005) + 0.010
            (Y, Z2), _ = section_grid((r["fy"] - half, step), (r["fy"] + half, zh), used, MAX_POINTS[dim])
            GY, GZ2 = np.meshgrid(Y, Z2)
            sections.append(dict(name="Y-Z", h=Y, z=Z2, shape=GY.shape, fixed=("X", r["fx"]),
                                 points=np.column_stack([np.full(GY.size, r["fx"]), GY.ravel(), GZ2.ravel()])))
        return dict(solver=solver, delays=delays, width=v["element_width_mm"] * 1e-3,
                    elevation=v["elevation_mm"] * 1e-3, dim=dim, f0=solver.probe.frequency,
                    cycles=v["cycles"], pulsed=v["pulsed"], mode=mode, wedge=wedge, part=part,
                    sections=sections, step_mm=used * 1e3, context=c, values=v,
                    setup_rev=self.setup_rev)

    def compute(self, sync=False):
        """Start the field for the current law (in a worker thread unless sync)."""
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            job = self.make_job()
            element_sources(job["solver"], job["delays"], job["width"], job["elevation"], job["dim"])
        except ValueError as e:
            self.status.setText(f"No field: {e}")
            return
        self.status.setText("Computing the field...")
        self.compute_btn.setEnabled(False)
        self.bar.setValue(0)
        self.bar.setVisible(True)
        if sync:
            try:
                self._done(run_job(job))
            except (ValueError, ArithmeticError, np.linalg.LinAlgError) as e:
                self._failed(str(e))
            return
        self.worker = FieldWorker(job)
        self.worker.progress.connect(lambda f: self.bar.setValue(int(100 * f)))
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _failed(self, msg):
        self.compute_btn.setEnabled(True)
        self.bar.setVisible(False)
        self.status.setText(f"No field: {msg}")

    def _done(self, job):
        self.compute_btn.setEnabled(True)
        self.bar.setVisible(False)
        # fresh only if nothing it depends on changed while it ran: law, field inputs, setup
        job["fresh"] = (job["context"] is self.context and job["values"] == self.get_values()
                        and job["setup_rev"] == self.setup_rev and not self.setup_dirty)
        self.job = job
        self.draw()
        v = job["values"]
        text = (f"{v['model']}, {'pulsed, %g cycles' % v['cycles'] if v['pulsed'] else 'continuous wave'}, "
                f"grid {job['step_mm']:.2f} mm")
        m = job.get("metrics")
        if m is not None:
            text += f"; beam axis {m.angle_deg:.1f}° from vertical"
        if not job["fresh"]:
            text = "Stale (the law, setup or inputs changed while computing): " + text
        self.status.setText(text)
        self._emit()

    def _emit(self):
        if self.job is None or not self.job.get("fresh") or not self.chk_3d.isChecked():
            self.field_changed.emit(None)
            return
        slices = []
        for s in self.job["sections"]:
            slices.append({"name": s["name"], "points_mm": s["points"].reshape(s["shape"] + (3,)) * 1e3,
                           "db": s["db"]})
        self.field_changed.emit(slices)

    # -- drawing -----------------------------------------------------------------------
    def draw(self):
        self.view.clear()
        self.plots = []
        job = self.job
        if job is None:
            return
        r = job["context"]["result"]
        th = job["context"]["thickness_mm"]
        job["metrics"] = None
        for k, s in enumerate(job["sections"]):
            h, z = s["h"] * 1e3, s["z"] * 1e3
            p = self.view.addPlot(title=f"{s['name']} section at {s['fixed'][0]} = {s['fixed'][1] * 1e3:.1f} mm")
            p.invertY(True)
            p.setAspectLocked(True)
            p.setLabel("bottom", f"{s['name'][0]} (mm)")
            p.setLabel("left", "Z depth (mm)")
            img = pg.ImageItem(s["db"].T, axisOrder="col-major")
            img.setColorMap(self.cmap)
            img.setLevels((FLOOR_DB, 0))
            dh = h[1] - h[0] if h.size > 1 else 1
            dz = z[1] - z[0] if z.size > 1 else 1
            img.setRect(QtCore.QRectF(h[0] - dh / 2, z[0] - dz / 2, dh * h.size, dz * z.size))
            p.addItem(img)
            iso = pg.IsocurveItem(data=s["db"].T, level=-6, pen=pg.mkPen("w", width=1.5))
            iso.setParentItem(img)          # drawn in the image's own (pixel) coordinates
            p.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen("k", width=1.5)))
            if th > 0:
                p.addItem(pg.InfiniteLine(pos=th, angle=0, pen=pg.mkPen("#334155", width=1.5)))
            fpos = (r["fx"] if s["name"] == "X-Z" else r["fy"]) * 1e3
            p.addItem(pg.ScatterPlotItem([fpos], [r["fz"] * 1e3], symbol="+", size=14,
                                         pen=pg.mkPen("w", width=2)))
            if s["name"] == "X-Z":
                try:
                    m = beam_axis(10 ** (s["db"] / 20), h, z, depths_mm=(r["fz"] * 1e3,))
                    job["metrics"] = m
                    zz = np.array([0, z[-1]])
                    p.addItem(pg.PlotDataItem(m.exit_x_mm + math.tan(math.radians(m.angle_deg)) * zz, zz,
                                              pen=pg.mkPen("w", width=1, style=QtCore.Qt.DotLine)))
                except ValueError:
                    pass
            if k == len(job["sections"]) - 1:
                bar = pg.ColorBarItem(values=(FLOOR_DB, 0), colorMap=self.cmap, label="dB re maximum",
                                      interactive=False)
                bar.setImageItem(img, insert_in=p)
            p.setXRange(h[0], h[-1], padding=0.02)
            p.setYRange(min(-2, z[0]), z[-1], padding=0.02)
            self.plots.append(p)
