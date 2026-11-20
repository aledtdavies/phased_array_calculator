"""
The Qt window's 3D tab on PyVista/VTK (pyvistaqt), plan step 3.

Draws scene_model's scene with scene_vtk: wedge (catalogue outline or schematic) and component
as translucent solids, element footprints at their catalogue size where known, the selected
law's rays, interface points and focus, and the sweep's foci. Camera presets keep depth
downward; axis views are parallel projections. A section plane through the active aperture's
centre cuts the solids open. Clicking on an element (in screen space) picks it: its number in the chosen
numbering convention, its array, grid position, delay and time of flight, and its ray drawn
bold. Navigation (sliders, steps, Play, table selection) as the other tabs.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from qtpy import QtWidgets

from qt_plotting import LawTab, PlayMixin
from scene_model import build_scene, coverage_prims, user_element_numbers
from scene_vtk import (VIEWS, add_axes, add_law, add_setup, element_at_display, refit_camera,
                       set_camera)


class Scene3DTab(PlayMixin, LawTab):
    MAX_RAYS = 48

    def __init__(self):
        super().__init__()
        self._add_play(0, 2)
        self.chk_locus = QtWidgets.QCheckBox("Sweep focal points")
        self.chk_locus.setChecked(True)
        self.chk_section = QtWidgets.QCheckBox("Section")
        self.chk_section.setToolTip("Cut the wedge and component at the active aperture's centre (X-Z plane)")
        self.controls.addWidget(self.chk_locus, 0, 3)
        self.controls.addWidget(self.chk_section, 0, 4)
        views = QtWidgets.QHBoxLayout()
        self.view_buttons = {}
        for name in VIEWS:
            b = QtWidgets.QPushButton(name)
            b.setFixedWidth(48)
            b.clicked.connect(lambda _=False, n=name: self.set_view(n))
            views.addWidget(b)
            self.view_buttons[name] = b
        self.controls.addLayout(views, 1, 2, 1, 3)
        self.lbl_pick = QtWidgets.QLabel("Click near an element to inspect it.")
        self.controls.addWidget(self.lbl_pick, 2, 2, 1, 3)
        self.chk_locus.toggled.connect(lambda _: self._rebuild())
        self.chk_section.toggled.connect(lambda _: self._rebuild())

        self.component_thickness_mm = 0.0
        self.outline_mm = None
        self.element_size_m = (None, None)
        self.view = "Iso"
        self.bounds = None
        self.scene = None
        self.picked = None
        self._setup_drawn = False

    # -- view ------------------------------------------------------------------------
    def _make_view(self, lay):
        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")
        lay.addWidget(self.plotter.interactor, 1)
        # Elements are picked in screen space (scene_vtk.element_at_display), not by ray
        # casting, so the translucent solids, rays and highlights never intercept a click.
        # A click is a left press and release at the same place; a drag (rotation) is not.
        # VTK swallows release events on the interactor; pyvista's add_observer registers
        # them on the interactor style instead (pyvista issue #4976).
        self._press_xy = None
        self.plotter.iren.add_observer("LeftButtonPressEvent", self._on_press)
        self.plotter.iren.add_observer("LeftButtonReleaseEvent", self._on_release)

    CLICK_SLOP_PX = 3

    def _event_xy(self):
        return self.plotter.iren.interactor.GetEventPosition()

    def _on_press(self, *_):
        self._press_xy = self._event_xy()

    def _on_release(self, *_):
        xy = self._event_xy()
        start, self._press_xy = self._press_xy, None
        if start is not None and max(abs(xy[0] - start[0]), abs(xy[1] - start[1])) <= self.CLICK_SLOP_PX:
            self._clicked(xy)

    def _blank_view(self):
        self.plotter.clear()
        self.plotter.render()
        self._setup_drawn = False
        self.scene = None
        self.picked = None
        self.lbl_pick.setText("Click near an element to inspect it.")

    def closeEvent(self, event):      # noqa: N802 - Qt's name
        self.plotter.close()
        super().closeEvent(event)

    # -- laws ------------------------------------------------------------------------
    def update_plot(self, solver, focal_points, wave_type, results=None, is_matrix=False,
                    component_thickness_mm=0.0, outline_mm=None, element_size_m=(None, None)):
        self.component_thickness_mm = component_thickness_mm
        self.outline_mm = outline_mm
        self.element_size_m = element_size_m
        self._setup_drawn = False
        self.picked = None
        self.lbl_pick.setText("Click near an element to inspect it.")
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def _build_scene(self):
        cur = self.nav.current
        scene = build_scene(self.solver, self._get_law_data, [cur], outline_mm=self.outline_mm, current=cur,
                           max_rays=self.MAX_RAYS,
                           sweep_focal_mm=np.asarray(self.focal_points) * 1e3 if self.chk_locus.isChecked() else None,
                           element_size_m=self.element_size_m)
        if self.coverage is not None:
            scene.prims += coverage_prims(self.coverage, self.coverage_path_mm())
        return scene

    def _coverage_changed(self):
        self._setup_drawn = False

    def _rebuild(self):
        self._setup_drawn = False
        self.refresh_plot()

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        self.scene = self._build_scene()
        pl = self.plotter
        if not self._setup_drawn:
            keep_camera = self.bounds is not None
            pl.clear()
            self.bounds = add_setup(pl, self.scene, self.component_thickness_mm,
                                    section=self.chk_section.isChecked())
            add_law(pl, self.scene)
            pl.add_legend(bcolor="white", face="rectangle", size=(0.2, 0.26), loc="lower right")
            add_axes(pl, *self.bounds)
            if keep_camera:
                refit_camera(pl, *self.bounds)   # keep the user's viewing angle, frame the new setup
            else:
                set_camera(pl, self.view, *self.bounds)
            self._setup_drawn = True
        else:
            add_law(pl, self.scene)
        if self.picked is not None:
            self._show_pick(self.picked)
        pl.render()

    def set_view(self, name):
        self.view = name
        if self.bounds is not None:
            set_camera(self.plotter, name, *self.bounds)
            self.plotter.render()

    # -- picking ---------------------------------------------------------------------
    def _clicked(self, xy, *_):
        """A left click at display position xy (pixels): pick the element drawn there, if any."""
        if self.scene is None or xy is None:
            return None
        idx = element_at_display(self.scene, self.plotter.renderer, xy)
        if idx is not None:
            self.pick_element(idx)
            self.element_selected.emit(idx)
        return idx

    def element_info(self, idx):
        """What the 3D tab reports for internal element idx in the current law."""
        probe = self.solver.probe
        per = probe.num_elements * probe.num_elements_y
        block, local = divmod(int(idx), per)
        ix, iy = divmod(local, probe.num_elements_y)
        array = ("Tx" if block == 0 else "Rx") if hasattr(probe, "array_separation") else ""
        r = self.current_result()
        delay, tof = float(r["delays_us"][idx]), float(r["tof_us"][idx])
        return {"index": int(idx), "number": int(user_element_numbers(probe)[idx]), "array": array,
                "x_index": ix + 1, "y_index": iy + 1, "active": bool(np.isfinite(delay)),
                "delay_us": delay, "tof_us": tof}

    def highlight_element(self, idx):
        """Selected in another tab: show it here too (now, or when this tab is next drawn)."""
        super().highlight_element(idx)
        self.picked = None if idx is None else int(idx)
        if idx is None:                                   # deselection
            self.plotter.remove_actor("pick:ray", render=False)
            self.plotter.remove_actor("pick:element", render=False)
            self.lbl_pick.setText("Click near an element to inspect it.")
            if self.scene is not None:
                self.plotter.render()
            return
        if self.scene is not None and self._setup_drawn and not self._stale:
            self.pick_element(idx)

    def pick_element(self, idx):
        self.picked = int(idx)
        self.selected_element = self.picked
        self._show_pick(self.picked)
        self.plotter.render()
        return self.element_info(idx)

    def _show_pick(self, idx):
        info = self.element_info(idx)
        parts = [info["array"]] if info["array"] else []
        if self.solver.probe.num_elements_y > 1:
            parts.append(f"X {info['x_index']} Y {info['y_index']}")
        name = f"Element {info['number']}" + (f" ({', '.join(parts)})" if parts else "")
        if info["active"]:
            text = f"{name}: delay {info['delay_us']:.4f} µs, time of flight {info['tof_us']:.3f} µs"
        else:
            text = f"{name}: inactive in this law"
        self.lbl_pick.setText(text)
        self.plotter.remove_actor("pick:ray", render=False)
        self.plotter.remove_actor("pick:element", render=False)
        el = self.solver.wedge.get_transformed_elements(self.solver.probe)[idx] * 1e3
        self.plotter.add_points(el[None, :], color="#f59e0b", point_size=14,
                                render_points_as_spheres=True, name="pick:element")
        if info["active"]:
            ip = self.current_result()["interface_points"][idx] * 1e3
            fp = self.current_focal() * 1e3
            self.plotter.add_mesh(pv.lines_from_points(np.array([el, ip, fp])), color="#f59e0b",
                                  line_width=4, name="pick:ray")
