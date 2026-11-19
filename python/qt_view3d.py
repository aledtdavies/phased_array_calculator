"""
The Qt window's 3D tab on PyVista/VTK (pyvistaqt), plan step 3.

Draws scene_model's scene with scene_vtk: wedge (catalogue outline or schematic) and component
as translucent solids, element footprints at their catalogue size where known, the selected
law's rays, interface points and focus, and the sweep's foci. Camera presets keep depth
downward; axis views are parallel projections. A section plane through the active aperture's
centre cuts the solids open. Clicking near an element picks it: its number in the chosen
numbering convention, its array, grid position, delay and time of flight, and its ray drawn
bold. Navigation (sliders, steps, Play, table selection) as the other tabs.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from qtpy import QtWidgets

from qt_plotting import LawTab, PlayMixin
from scene_model import build_scene, user_element_numbers
from scene_vtk import VIEWS, add_law, add_setup, nearest_element, set_camera


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
    def _make_view(self, lay, projection, toolbar):
        self.plotter = QtInteractor(self)
        self.plotter.set_background("white")
        lay.addWidget(self.plotter.interactor, 1)
        self.plotter.enable_point_picking(callback=self._clicked, left_clicking=True,
                                          show_message=False, show_point=False, picker="cell")

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
        get = lambda i: (self.results[i]["interface_points"] * 1e3, np.asarray(self.focal_points[i]) * 1e3)
        return build_scene(self.solver, get, [cur], outline_mm=self.outline_mm, current=cur,
                           max_rays=self.MAX_RAYS,
                           sweep_focal_mm=np.asarray(self.focal_points) * 1e3 if self.chk_locus.isChecked() else None,
                           element_size_m=self.element_size_m)

    def _rebuild(self):
        self._setup_drawn = False
        self.refresh_plot()

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        self.scene = self._build_scene()
        pl = self.plotter
        if not self._setup_drawn:
            camera = pl.camera_position if self.bounds is not None else None
            pl.clear()
            self.bounds = add_setup(pl, self.scene, self.component_thickness_mm,
                                    section=self.chk_section.isChecked())
            add_law(pl, self.scene)
            pl.add_legend(bcolor="white", face="rectangle", size=(0.2, 0.26), loc="lower right")
            pl.show_axes()
            if camera is None:
                set_camera(pl, self.view, *self.bounds)
            else:
                pl.camera_position = camera      # keep the user's camera across recalculations
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
    def _clicked(self, point, *_):
        if self.scene is None or point is None:
            return
        probe = self.solver.probe
        reach = 0.75 * 1e3 * max(probe.pitch, probe.pitch_y or 0.0)
        idx = nearest_element(self.scene, point, reach)
        if idx is not None:
            self.pick_element(idx)

    def element_info(self, idx):
        """What the 3D tab reports for internal element idx in the current law."""
        probe = self.solver.probe
        per = probe.num_elements * probe.num_elements_y
        block, local = divmod(int(idx), per)
        ix, iy = divmod(local, probe.num_elements_y)
        array = ("Tx" if block == 0 else "Rx") if hasattr(probe, "array_separation") else ""
        r = self.results[self.nav.current]
        delay, tof = float(r["delays_us"][idx]), float(r["tof_us"][idx])
        return {"index": int(idx), "number": int(user_element_numbers(probe)[idx]), "array": array,
                "x_index": ix + 1, "y_index": iy + 1, "active": bool(np.isfinite(delay)),
                "delay_us": delay, "tof_us": tof}

    def pick_element(self, idx):
        self.picked = int(idx)
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
            r = self.results[self.nav.current]
            ip = r["interface_points"][idx] * 1e3
            fp = np.asarray(self.focal_points[self.nav.current]) * 1e3
            self.plotter.add_mesh(pv.lines_from_points(np.array([el, ip, fp])), color="#f59e0b",
                                  line_width=4, name="pick:ray")
