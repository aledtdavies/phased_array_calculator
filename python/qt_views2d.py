"""
The Qt window's 2D views on pyqtgraph (plan step 4): ray tracing (X-Z, and Y-Z for matrix and
dual probes) and delays (bar chart, or per-array delay maps for matrix probes).

Both draw scene_model's geometry. Items are built once per calculation and only the current
law's items are updated per tick (setData), so scrubbing and Play redraw quickly. The X-Z
focus can be dragged: the window solves a law for it live (LawTab.set_custom). Clicking an
element (a marker, a bar or a map cell) selects it in every tab (LawTab.element_selected).

Frame: global, millimetres, Z (depth) drawn downward; Y-Z is seen from -X (Y to the right).
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from qtpy import QtCore, QtGui, QtWidgets

from qt_plotting import LawTab, PlayMixin
from scene import (COLOR_BACKWALL, COLOR_ELEMENT_ACTIVE, COLOR_ELEMENT_INACTIVE, COLOR_ELEMENT_TX,
                   COLOR_MATERIAL, COLOR_PROBE_EDGE, COLOR_PROBE_FACE, COLOR_WEDGE_EDGE,
                   COLOR_WEDGE_FACE)
from scene_model import build_scene, coverage_prims, user_element_numbers, wedge_yz_rect

pg.setConfigOptions(antialias=True, background="w", foreground="k")

ELEMENT_COLOUR = {"single": COLOR_ELEMENT_ACTIVE, "tx": COLOR_ELEMENT_TX, "rx": COLOR_ELEMENT_ACTIVE}
RAY_COLOUR = {"single": "#2563eb", "tx": "#1f77b4", "rx": "#d62728"}     # tab:blue / tab:red
PICK_COLOUR = "#f59e0b"
COVERAGE_COLOUR = {1: "#2563eb", 2: "#7c3aed", 3: "#db2777"}
COVERAGE_NAME = {1: "Coverage, direct", 2: "Coverage, 1st skip", 3: "Coverage, 2nd skip"}


def _rgba(hex_colour, alpha):
    c = QtGui.QColor(hex_colour)
    c.setAlphaF(alpha)
    return c


def _polygon(points, face, edge, alpha):
    item = QtWidgets.QGraphicsPolygonItem(QtGui.QPolygonF([QtCore.QPointF(float(a), float(b)) for a, b in points]))
    item.setBrush(QtGui.QBrush(_rgba(face, alpha)))
    pen = QtGui.QPen(QtGui.QColor(edge))
    pen.setCosmetic(True)
    item.setPen(pen)
    return item


class ProjectionPlot(pg.PlotWidget):
    """One projection (dim 0 = X-Z, 1 = Y-Z) of the scene."""

    element_clicked = QtCore.Signal(int)
    focus_dragged = QtCore.Signal(float, float)     # X (mm), Z (mm); X-Z view only

    def __init__(self, dim):
        super().__init__()
        self.dim = dim
        pi = self.getPlotItem()
        pi.invertY(True)
        pi.setAspectLocked(True)
        pi.showGrid(x=True, y=True, alpha=0.25)
        pi.setLabel("bottom", "X (mm)" if dim == 0 else "Y (mm)")
        pi.setLabel("left", "Z depth (mm)")
        pi.setTitle("Ray tracing X-Z" if dim == 0 else "Ray tracing Y-Z")
        self.legend = pi.addLegend(offset=(-10, 10), labelTextSize="8pt")
        self.setup_items = []
        self.env_items = {a: pg.PlotDataItem(connect="pairs", pen=pg.mkPen(RAY_COLOUR[a], width=1.5))
                          for a in ("single", "tx", "rx")}
        for it in self.env_items.values():
            it.setZValue(4)
            self.addItem(it)
        self.all_items = []
        self.focus = pg.TargetItem(size=14, movable=(dim == 0), symbol="crosshair",
                                   pen=pg.mkPen(COLOR_ELEMENT_ACTIVE, width=2.5),
                                   label="Focus (drag)" if dim == 0 else None,
                                   labelOpts={"color": "#64748b", "offset": (12, -14)})
        self.focus.setZValue(6)
        self.addItem(self.focus)
        self._placing_focus = False
        self.focus.sigPositionChanged.connect(self._focus_moved)
        self.pick = pg.ScatterPlotItem(size=13, brush=pg.mkBrush(PICK_COLOUR), pen=pg.mkPen("k"))
        self.pick.setZValue(7)
        self.addItem(self.pick)
        self.central = pg.PlotDataItem(pen=pg.mkPen("k", width=2, style=QtCore.Qt.DashLine))
        self.central.setZValue(4.5)
        self.addItem(self.central)

    # -- setup (once per calculation) -------------------------------------------------
    def set_setup(self, scene, component_thickness_mm, extra_points_mm=(), coverage=(), central=False):
        for it in self.setup_items:
            self.removeItem(it)
        self.setup_items = []
        self.legend.clear()
        d = self.dim

        def add(item, z=1, name=None, ignore_bounds=False):
            item.setZValue(z)
            self.addItem(item, ignoreBounds=ignore_bounds)
            self.setup_items.append(item)
            if name:
                self.legend.addItem(item, name)
            return item

        pts = [p.coords[:, [d, 2]] for p in scene.prims if p.kind != "text"]
        pts += [np.asarray(e)[:, [d, 2]] for e in extra_points_mm if len(e)]
        for p in coverage:
            if p.role == "coverage":
                pts.append(p.coords[:, [d, 2]])
                quads = p.coords[:, [d, 2]].reshape(-1, 4, 2)
                col = COVERAGE_COLOUR.get(p.meta["leg"], "#64748b")
                for k, q in enumerate(quads):
                    item = _polygon(q, col, col, 0.10)
                    item.setPen(QtGui.QPen(QtCore.Qt.NoPen))
                    add(item, 0.5)
                self.legend.addItem(pg.PlotDataItem(pen=pg.mkPen(col), fillLevel=0,
                                                    brush=pg.mkBrush(_rgba(col, 0.3))),
                                    COVERAGE_NAME.get(p.meta["leg"], f"Coverage, leg {p.meta['leg']}"))
        if scene.contact:
            c = scene.one("contact")
            add(pg.TextItem(c.meta["text"], color=COLOR_PROBE_EDGE, anchor=(0, 1)), 6).setPos(
                float(c.coords[0, d]), float(c.coords[0, 2]))
        elif d == 0:
            w = scene.one("wedge")
            verts = w.coords[:, [0, 2]]
            add(_polygon(verts, COLOR_WEDGE_FACE, COLOR_WEDGE_EDGE, 0.16), 1.5)
            legend_w = pg.PlotDataItem(pen=pg.mkPen(COLOR_WEDGE_EDGE), fillLevel=0,
                                       brush=pg.mkBrush(_rgba(COLOR_WEDGE_FACE, 0.3)))
            self.legend.addItem(legend_w, "Wedge (catalogue)" if w.meta["source"] == "catalogue" else "Wedge (schematic)")
            body = scene.one("probe-body").coords[:, [0, 2]]
            add(_polygon(body, COLOR_PROBE_FACE, COLOR_PROBE_EDGE, 0.18), 1.5)
            dim_ = scene.one("dimension")
            add(pg.PlotDataItem(dim_.coords[:, 0], dim_.coords[:, 2], pen=pg.mkPen(COLOR_WEDGE_EDGE)), 4)
            add(pg.TextItem(dim_.meta["text"], color=COLOR_WEDGE_EDGE, anchor=(0, 0.5)), 6).setPos(*dim_.meta["text_at"])
            ang = scene.one("wedge-angle")
            add(pg.TextItem(ang.meta["text"], color=COLOR_WEDGE_EDGE, anchor=(0.5, 1)), 6).setPos(
                float(ang.coords[0, 0]), float(ang.coords[0, 2]))
        else:
            add(_polygon(wedge_yz_rect(scene), COLOR_WEDGE_FACE, COLOR_WEDGE_EDGE, 0.16), 1.5)

        for p in scene.find("element"):
            active = p.meta["active"]
            c = ELEMENT_COLOUR[p.meta["array"]]
            sp = pg.ScatterPlotItem(p.coords[:, d], p.coords[:, 2], data=p.meta["indices"], symbol="s", size=7,
                                    brush=pg.mkBrush(c) if active else pg.mkBrush(None),
                                    pen=pg.mkPen(c if active else COLOR_ELEMENT_INACTIVE), hoverable=True)
            sp.sigClicked.connect(self._element_clicked)
            name = ({"single": "Elements", "tx": "Tx elements", "rx": "Rx elements"}[p.meta["array"]]
                    if active else ("Inactive elements" if p.meta["array"] in ("single", "tx") else None))
            add(sp, 5, name)

        allp = np.vstack(pts)
        lo, hi = allp.min(axis=0), allp.max(axis=0)
        hi[1] = max(hi[1], component_thickness_mm)
        pad = np.maximum(2.0, 0.08 * (hi - lo))
        lo, hi = lo - pad, hi + pad
        bottom = component_thickness_mm if component_thickness_mm > 0 else hi[1] + 1e3
        comp = QtWidgets.QGraphicsRectItem(lo[0] - 1e3, 0.0, (hi[0] - lo[0]) + 2e3, bottom)
        comp.setBrush(QtGui.QBrush(_rgba(COLOR_MATERIAL, 0.15)))
        comp.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        add(comp, 0, ignore_bounds=True)     # a backdrop: Auto Range frames the geometry, not it
        add(pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen("k", width=2)), 3)
        if component_thickness_mm > 0:
            add(pg.InfiniteLine(pos=component_thickness_mm, angle=0, pen=pg.mkPen(COLOR_BACKWALL, width=1.5)), 2)
        for a, name in (("single", "Rays"), ("tx", "Tx rays"), ("rx", "Rx rays")):
            if scene.find("envelope-ray", array=a):
                self.legend.addItem(self.env_items[a], name)
        # The draggable TargetItem cannot draw a legend sample: a plain marker stands in.
        self.legend.addItem(pg.ScatterPlotItem(symbol="+", size=12, pen=pg.mkPen(COLOR_ELEMENT_ACTIVE, width=2.5)),
                            "Focal point (drag in X-Z)" if self.dim == 0 else "Focal point")
        if central:
            self.legend.addItem(self.central, "Central ray (skips)")
        self.setRange(xRange=(lo[0], hi[0]), yRange=(lo[1], hi[1]), padding=0)
        self.pick.setData([], [])

    # -- per law ------------------------------------------------------------------------
    def set_law(self, scene, law):
        """Envelope rays and focus of one law: data updated in place."""
        self._clear_all()
        d = self.dim
        for a, item in self.env_items.items():
            segs = scene.find("envelope-ray", law=law, array=a)
            if segs:
                c = np.vstack([p.coords for p in segs])
                item.setData(c[:, d], c[:, 2])
            else:
                item.setData([], [])
            item.setVisible(True)
        f = scene.one("focus", law=law).coords[0]
        self._placing_focus = True
        self.focus.setPos(float(f[d]), float(f[2]))
        self._placing_focus = False
        self.focus.setVisible(True)

    def set_all(self, scene, indices):
        """Show All: every law's envelope rays and focus, coloured by law index."""
        self._clear_all()
        for it in self.env_items.values():
            it.setVisible(False)
        self.focus.setVisible(False)
        cmap = pg.colormap.get("viridis")
        n = max(1, len(indices) - 1)
        d = self.dim
        for j, law in enumerate(indices):
            col = cmap.map(j / n, mode="qcolor")
            col.setAlphaF(0.5)
            segs = scene.find("envelope-ray", law=law)
            if segs:
                c = np.vstack([p.coords for p in segs])
                it = pg.PlotDataItem(c[:, d], c[:, 2], connect="pairs", pen=pg.mkPen(col, width=1))
                it.setZValue(4)
                self.addItem(it)
                self.all_items.append(it)
            f = scene.one("focus", law=law).coords[0]
            sp = pg.ScatterPlotItem([f[d]], [f[2]], size=5, brush=pg.mkBrush(cmap.map(j / n, mode="qcolor")), pen=None)
            sp.setZValue(6)
            self.addItem(sp)
            self.all_items.append(sp)

    def _clear_all(self):
        for it in self.all_items:
            self.removeItem(it)
        self.all_items = []

    def clear_setup(self):
        """Remove everything a calculation drew (no laws)."""
        for it in self.setup_items:
            self.removeItem(it)
        self.setup_items = []
        self.legend.clear()
        self._clear_all()
        for it in self.env_items.values():
            it.setData([], [])
        self.focus.setVisible(False)
        self.pick.setData([], [])
        self.central.setData([], [])

    def set_central(self, path_mm):
        """The current law's central ray with its skips (None: hidden)."""
        if path_mm is None:
            self.central.setData([], [])
        else:
            self.central.setData(path_mm[:, self.dim], path_mm[:, 2])

    def set_pick(self, point_mm):
        if point_mm is None:
            self.pick.setData([], [])
        else:
            self.pick.setData([point_mm[self.dim]], [point_mm[2]])

    def _element_clicked(self, _item, points, *_):
        if len(points):
            self.element_clicked.emit(int(points[0].data()))

    def _focus_moved(self, *_):
        if not self._placing_focus and self.dim == 0:
            p = self.focus.pos()
            self.focus_dragged.emit(float(p.x()), float(p.y()))


class RayTab(PlayMixin, LawTab):
    """X-Z projection, plus Y-Z for matrix and dual probes; Show All overlays every law."""

    focus_dragged = QtCore.Signal(float, float)     # X (m), Z (m)

    def __init__(self):
        super().__init__()
        self._add_play(0, 2)
        self.chk_all = QtWidgets.QCheckBox("Show All")
        self.controls.addWidget(self.chk_all, 0, 3)
        self.chk_all.toggled.connect(lambda _: self.refresh_plot())
        self.component_thickness_mm = 0.0
        self.outline_mm = None
        self._setup_drawn = False
        self._all_drawn = False      # Show All overlays exist for this calculation

    def _make_view(self, lay):
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.xz = ProjectionPlot(0)
        self.yz = ProjectionPlot(1)
        self.splitter.addWidget(self.xz)
        self.splitter.addWidget(self.yz)
        lay.addWidget(self.splitter, 1)
        for p in (self.xz, self.yz):
            p.element_clicked.connect(self._element_clicked)
        self.xz.focus_dragged.connect(lambda x, z: self.focus_dragged.emit(x * 1e-3, z * 1e-3))

    def plots(self):
        return [self.xz] + ([self.yz] if self.yz.isVisibleTo(self) else [])

    def _blank_view(self):
        for p in (self.xz, self.yz):
            p.clear_setup()
        self._setup_drawn = False
        self._all_drawn = False

    def update_plot(self, solver, focal_points, wave_type, results=None, is_matrix=False,
                    component_thickness_mm=0.0, outline_mm=None):
        self.component_thickness_mm = component_thickness_mm
        self.outline_mm = outline_mm
        self._setup_drawn = False
        self._all_drawn = False
        probe = solver.probe
        self.yz.setVisible(probe.num_elements_y > 1 or hasattr(probe, "array_separation"))
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def _coverage_changed(self):
        self._setup_drawn = False
        self._all_drawn = False

    def reset_focus_marker(self):
        """Put the X-Z marker back on the focus shown (after a refused drag); no solve follows."""
        if not self.focal_points:
            return
        f = self.current_focal() * 1e3
        self.xz._placing_focus = True
        self.xz.focus.setPos(float(f[0]), float(f[2]))
        self.xz._placing_focus = False

    def _element_clicked(self, idx):
        self.highlight_element(idx)
        self.element_selected.emit(idx)

    def highlight_element(self, idx):
        super().highlight_element(idx)
        p = None if idx is None or self.solver is None else \
            self.solver.wedge.get_transformed_elements(self.solver.probe)[idx] * 1e3
        for plot in (self.xz, self.yz):
            plot.set_pick(p)

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        show_all = self.chk_all.isChecked() and not self.custom
        if show_all and self._setup_drawn and self._all_drawn:
            self.lbl_angle.setText(f"All {len(self.focal_points)} Laws")   # the same for every law
            return
        indices = list(range(len(self.focal_points))) if show_all else [self.nav.current]
        scene = build_scene(self.solver, self._get_law_data, indices, outline_mm=self.outline_mm)
        if not self._setup_drawn:
            extra = [np.asarray(self.focal_points) * 1e3]
            cov = []
            if self.coverage is not None:
                cov = coverage_prims(self.coverage)
                extra += [np.asarray(p) * 1e3 for p in self.coverage.paths]   # frame every skip path
            for p in (self.xz, self.yz):
                p.set_setup(scene, self.component_thickness_mm, extra, cov, central=self.coverage is not None)
            self._setup_drawn = True
            self.highlight_element(self.selected_element)
        path = None if show_all else self.coverage_path_mm()
        for p in (self.xz, self.yz):
            if show_all:
                p.set_all(scene, indices)
            else:
                p.set_law(scene, self.nav.current)
            p.set_central(path)
        self._all_drawn = show_all
        if show_all:
            self.lbl_angle.setText(f"All {len(self.focal_points)} Laws")
            if self.is_matrix:
                self.lbl_skew.setText("")


class DelayTab(LawTab):
    """Delay profile: bar chart for linear probes, per-array delay maps for matrix probes."""

    def __init__(self):
        super().__init__()
        self.global_max_delay = None
        self._layout_key = None

    def _make_view(self, lay):
        self.view = pg.GraphicsLayoutWidget()
        lay.addWidget(self.view, 1)
        self.items = {}
        # One handler for the life of the view: it reads the current layout, so a rebuilt
        # layout never leaves handlers bound to removed plots.
        self.view.scene().sigMouseClicked.connect(self._scene_clicked)

    def _blank_view(self):
        self.view.clear()
        self.items = {}
        self._layout_key = None

    def update_plot(self, solver, focal_points, wave_type, global_max_delay=None, results=None,
                    is_matrix=False):
        self.global_max_delay = global_max_delay
        self._layout_key = None
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def _vmax(self, delays):
        v = self.global_max_delay
        if v is not None and np.isfinite(v) and v > 0:
            return float(v)
        finite = delays[np.isfinite(delays)]
        return float(finite.max()) if finite.size and finite.max() > 0 else 1.0

    def _build(self, probe, delays):
        """The plots for this probe (once per calculation)."""
        self.view.clear()
        self.items = {}
        vmax = self._vmax(delays)
        n = len(delays)
        if probe.num_elements_y == 1:
            p = self.view.addPlot(title="Delay profile")
            p.setLabel("bottom", "Element ID")
            p.setLabel("left", "Delay (µs)")
            p.showGrid(y=True, alpha=0.3)
            bars = pg.BarGraphItem(x=[], height=[], width=0.8, brush=pg.mkBrush("#87ceeb"), pen=pg.mkPen("k"))
            p.addItem(bars)
            inactive = pg.ScatterPlotItem(symbol="x", size=8, pen=pg.mkPen(COLOR_ELEMENT_INACTIVE), brush=None)
            p.addItem(inactive)
            pick = pg.ScatterPlotItem(symbol="t", size=12, brush=pg.mkBrush(PICK_COLOUR), pen=pg.mkPen("k"))
            p.addItem(pick)
            if hasattr(probe, "array_separation"):
                p.addItem(pg.InfiniteLine(pos=n / 2 + 0.5, angle=90, pen=pg.mkPen("#64748b", style=QtCore.Qt.DotLine)))
            p.setXRange(0.5, n + 0.5, padding=0)
            p.setYRange(0, vmax * 1.1, padding=0)
            self.items = {"plot": p, "bars": bars, "inactive": inactive, "pick": pick}
            return
        nx, ny = probe.num_elements, probe.num_elements_y
        per = nx * ny
        n_arrays = probe.total_elements // per
        numbers = user_element_numbers(probe)
        cmap = pg.colormap.get("viridis")
        images, texts, picks = [], [], []
        names = ["Tx array", "Rx array"] if n_arrays == 2 else ["Aperture"]
        plots = []
        title = self.view.addLabel("", colspan=n_arrays + 1)
        self.view.nextRow()
        for b in range(n_arrays):
            p = self.view.addPlot(title=names[b])
            p.setAspectLocked(True)
            p.setLabel("bottom", "X element index")
            p.setLabel("left", "Y element index")
            bg = QtWidgets.QGraphicsRectItem(0.5, 0.5, nx, ny)
            bg.setBrush(QtGui.QBrush(QtGui.QColor("#e2e8f0")))
            bg.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            p.addItem(bg)
            img = pg.ImageItem(np.zeros((nx, ny)), axisOrder="col-major")
            img.setColorMap(cmap)
            img.setRect(QtCore.QRectF(0.5, 0.5, nx, ny))     # after the image: its size sets the scale
            p.addItem(img)
            cell_texts = []
            if per <= 256:
                nums = numbers[b * per:(b + 1) * per].reshape(nx, ny)
                for ix in range(nx):
                    for iy in range(ny):
                        t = pg.TextItem(str(nums[ix, iy]), anchor=(0.5, 0.5))
                        t.setFont(QtGui.QFont("", 7))
                        t.setPos(ix + 1, iy + 1)
                        p.addItem(t)
                        cell_texts.append(t)
            pick = QtWidgets.QGraphicsRectItem(0, 0, 1, 1)
            pen = QtGui.QPen(QtGui.QColor(PICK_COLOUR))
            pen.setWidth(3)
            pen.setCosmetic(True)
            pick.setPen(pen)
            pick.setVisible(False)
            p.addItem(pick)
            images.append(img)
            texts.append(cell_texts)
            picks.append(pick)
            plots.append(p)
        bar = pg.ColorBarItem(values=(0, vmax), colorMap=cmap, interactive=False, label="Delay (µs)")
        bar.setImageItem(images, insert_in=plots[-1])
        for p in plots:
            p.setRange(xRange=(0.5, nx + 0.5), yRange=(0.5, ny + 0.5), padding=0.02)
        self.items = {"plots": plots, "images": images, "texts": texts, "picks": picks, "bar": bar,
                      "shape": (nx, ny, per), "vmax": vmax, "title": title}

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        probe = self.solver.probe
        delays = np.asarray(self.current_result()["delays_us"], dtype=float)
        key = (probe.total_elements, probe.num_elements_y)
        if self._layout_key != key:
            self._build(probe, delays)
            self._layout_key = key
            self.highlight_element(self.selected_element)
        title = "Delay profile - dragged focus" if self.custom else f"Delay profile - law {self.nav.current + 1}"
        active = np.isfinite(delays)
        # One scale across the sweep, widened while a dragged focus needs more; the sweep's
        # scale returns with the sweep.
        vmax = self._vmax(delays)
        if self.custom and active.any():
            vmax = max(vmax, float(np.nanmax(delays)))
        if "bars" in self.items:
            ids = np.arange(1, len(delays) + 1)
            self.items["bars"].setOpts(x=ids[active], height=delays[active], width=0.8)
            self.items["inactive"].setData(ids[~active], np.zeros((~active).sum()))
            self.items["plot"].setYRange(0, vmax * 1.1, padding=0)
            self.items["plot"].setTitle(title)
        else:
            nx, ny, per = self.items["shape"]
            self.items["vmax"] = vmax
            for b, (img, texts) in enumerate(zip(self.items["images"], self.items["texts"])):
                grid = delays[b * per:(b + 1) * per].reshape(nx, ny)
                img.setImage(grid, levels=(0, vmax), autoLevels=False)
                img.setRect(QtCore.QRectF(0.5, 0.5, nx, ny))
                for k, t in enumerate(texts):
                    v = grid.ravel()[k]
                    t.setColor("#475569" if not np.isfinite(v) else ("k" if v > 0.6 * vmax else "w"))
            self.items["bar"].setLevels((0, vmax))
            self.items["title"].setText(f"{title} (numbering: {probe.element_order})")
        self.highlight_element(self.selected_element)     # the marker follows the law's delays

    def highlight_element(self, idx):
        super().highlight_element(idx)
        if not self.items or self._stale_layout():
            return      # applied by refresh_plot after the layout is rebuilt
        if idx is not None and not 0 <= idx < self.solver.probe.total_elements:
            return
        if "bars" in self.items:
            if idx is None:
                self.items["pick"].setData([], [])
            else:
                d = np.asarray(self.current_result()["delays_us"], dtype=float)[idx]
                self.items["pick"].setData([idx + 1], [d if np.isfinite(d) else 0.0])
            return
        nx, ny, per = self.items["shape"]
        for r in self.items["picks"]:
            r.setVisible(False)
        if idx is not None:
            block, local = divmod(int(idx), per)
            ix, iy = divmod(local, ny)
            r = self.items["picks"][block]
            r.setRect(ix + 0.5, iy + 0.5, 1, 1)
            r.setVisible(True)

    def element_at_scene(self, scene_pos):
        """The element under a scene position in the current layout (a bar or a map cell), or None."""
        if not self.items or self._stale_layout():
            return None
        if "bars" in self.items:
            plot = self.items["plot"]
            if not plot.vb.sceneBoundingRect().contains(scene_pos):
                return None
            pos = plot.vb.mapSceneToView(scene_pos)
            k = int(round(pos.x()))
            n = self.solver.probe.total_elements
            return k - 1 if 1 <= k <= n and abs(pos.x() - k) <= 0.4 else None
        nx, ny, per = self.items["shape"]
        for block, plot in enumerate(self.items["plots"]):
            if plot.vb.sceneBoundingRect().contains(scene_pos):
                pos = plot.vb.mapSceneToView(scene_pos)
                ix, iy = int(round(pos.x())) - 1, int(round(pos.y())) - 1
                if 0 <= ix < nx and 0 <= iy < ny:
                    return block * per + ix * ny + iy
        return None

    def _scene_clicked(self, ev):
        idx = self.element_at_scene(ev.scenePos())
        if idx is not None:
            self.highlight_element(idx)
            self.element_selected.emit(idx)

    def _stale_layout(self):
        """True while the plots were built for another probe (this tab not yet redrawn)."""
        if self.solver is None:
            return True
        p = self.solver.probe
        return self._layout_key != (p.total_elements, p.num_elements_y)
