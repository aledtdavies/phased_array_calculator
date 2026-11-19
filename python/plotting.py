import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np

from scene import (draw_projection, draw_scene_3d, draw_aperture_maps, VIEW_PRESETS,
                   COLOR_ELEMENT_INACTIVE)


class LawNavigatorPanel(ttk.Frame):
    """
    Base panel: a matplotlib canvas plus law navigation. The angle/skew
    sliders pick the first law with that (angle, skew); the step buttons
    walk every law in order, including laws that share an angle and skew
    (Y-sweep targets). Subclasses implement refresh_plot().
    """

    def __init__(self, parent, projection=None, toolbar=False):
        super().__init__(parent)

        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.figure.add_subplot(111, projection=projection)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        if toolbar:
            bar = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            bar.update()
            bar.pack(side=tk.TOP, fill=tk.X)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.controls = ttk.Frame(self)
        self.controls.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.lbl_az_info = ttk.Label(self.controls, text="Angle: 0.0°", width=15)
        self.lbl_az_info.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.slider = tk.Scale(self.controls, from_=0, to=1, orient=tk.HORIZONTAL,
                               command=self.on_slider_change, showvalue=0)
        self.slider.grid(row=0, column=1, sticky="ew", padx=5)

        self.lbl_sk_info = ttk.Label(self.controls, text="Skew: 0.0°", width=15)
        self.lbl_sk_info.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.slider_skew = tk.Scale(self.controls, from_=0, to=1, orient=tk.HORIZONTAL,
                                    command=self.on_slider_change, showvalue=0)
        self.slider_skew.grid(row=1, column=1, sticky="ew", padx=5)

        step = ttk.Frame(self.controls)
        step.grid(row=2, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Button(step, text="◀", width=3, command=lambda: self.step_law(-1)).pack(side=tk.LEFT)
        ttk.Button(step, text="▶", width=3, command=lambda: self.step_law(1)).pack(side=tk.LEFT)
        self.lbl_law = ttk.Label(step, text="")
        self.lbl_law.pack(side=tk.LEFT, padx=8)

        self.controls.columnconfigure(1, weight=1)

        # Navigation state
        self.solver = None
        self.focal_points = []
        self.wave_type = 'longitudinal'
        self.current_idx = 0
        self.is_playing = False
        self.results = []
        self.angle_values = []
        self.skew_values = []
        self.index_map = {}
        self.is_matrix = False
        self._pinned_idx = None     # law chosen by index, honoured by the next slider event

    def update_navigation(self, solver, focal_points, wave_type, results, is_matrix):
        """Rebuild the (angle, skew) -> law index mapping and slider ranges."""
        self.solver = solver
        self.focal_points = focal_points
        self.wave_type = wave_type
        self.is_matrix = is_matrix
        self.results = results if results else []
        self._pinned_idx = None
        self.current_idx = 0        # a new law set: never keep an index from the old one

        if self.results:
            self.angle_values = sorted({r['angle'] for r in self.results})
            self.skew_values = sorted({r.get('skew', 0.0) for r in self.results})

            self.slider.config(to=max(0, len(self.angle_values) - 1))
            self.slider_skew.config(to=max(0, len(self.skew_values) - 1))
            self.slider.set(0)
            self.slider_skew.set(0)

            # First law for each (angle, skew); later laws with the same pair
            # (Y-sweep targets) are reached with the step buttons.
            self.index_map = {}
            for i, r in enumerate(self.results):
                self.index_map.setdefault((r['angle'], r.get('skew', 0.0)), i)
        else:
            self.angle_values = []
            self.skew_values = []
            self.slider.config(to=max(0, len(focal_points) - 1))
            self.slider.set(0)
            self.index_map = {}

        if is_matrix:
            self.lbl_sk_info.grid()
            self.slider_skew.grid()
        else:
            self.lbl_sk_info.grid_remove()
            self.slider_skew.grid_remove()

        self.on_slider_change()

    def clear_laws(self):
        """Forget the law set (a calculation gave no laws) and blank the plot."""
        if getattr(self, "is_playing", False):
            self.toggle_play()
        self.solver = None
        self.focal_points = []
        self.results = []
        self.angle_values = []
        self.skew_values = []
        self.index_map = {}
        self.current_idx = 0
        self._pinned_idx = None
        self.lbl_law.config(text="")
        projection = "3d" if self.ax.name == "3d" else None
        self.figure.clear()
        self.ax = self.figure.add_subplot(111, projection=projection)
        self.canvas.draw_idle()

    def set_sliders(self, angle_val, skew_val):
        if angle_val in self.angle_values:
            self.slider.set(self.angle_values.index(angle_val))
        if skew_val in self.skew_values:
            self.slider_skew.set(self.skew_values.index(skew_val))
        self.on_slider_change()

    def show_law(self, idx, redraw=True):
        """Select law idx directly (table row, step buttons, animation)."""
        if not self.focal_points:
            return
        idx = int(idx) % len(self.focal_points)
        self._pinned_idx = idx
        if idx < len(self.results):
            r = self.results[idx]
            if r['angle'] in self.angle_values:
                self.slider.set(self.angle_values.index(r['angle']))
            sk = r.get('skew', 0.0)
            if sk in self.skew_values:
                self.slider_skew.set(self.skew_values.index(sk))
        else:
            self.slider.set(idx)
        self.current_idx = idx
        self._update_labels()
        if redraw:
            self.refresh_plot()

    def step_law(self, delta):
        self.show_law(self.current_idx + delta)

    def on_slider_change(self, val=None):
        i_az = int(self.slider.get())
        i_sk = int(self.slider_skew.get()) if self.is_matrix else 0

        if self.angle_values:
            az_val = self.angle_values[min(i_az, len(self.angle_values) - 1)]
            sk_val = (self.skew_values[i_sk]
                      if self.skew_values and i_sk < len(self.skew_values) else 0.0)
            idx = self.index_map.get((az_val, sk_val))
            if idx is None:
                # Not every (angle, skew) pair exists (Constant Sound Path Y
                # sweeps give angle-dependent skews): take the first law at
                # this angle, else the first law.
                idx = next((i for i, r in enumerate(self.results) if r['angle'] == az_val), 0)
            # A law picked by index keeps its place while the sliders agree with it.
            pinned = self._pinned_idx
            if pinned is not None and pinned < len(self.results):
                r = self.results[pinned]
                if (r['angle'], r.get('skew', 0.0)) == (az_val, sk_val):
                    idx = pinned
                else:
                    self._pinned_idx = None
            self.current_idx = idx
        else:
            self.current_idx = i_az
        if self.focal_points:
            self.current_idx = min(max(self.current_idx, 0), len(self.focal_points) - 1)
        self._update_labels()

        if not self.is_playing:
            self.refresh_plot()

    def _update_labels(self):
        n = len(self.focal_points)
        if self.results and self.current_idx < len(self.results):
            r = self.results[self.current_idx]
            self.lbl_az_info.config(text=f"Angle: {r['angle']:.1f}°")
            self.lbl_sk_info.config(text=f"Skew: {r.get('skew', 0.0):.1f}°")
            self.lbl_law.config(text=(f"Law {self.current_idx + 1}/{n}  "
                                      f"F = ({r['fx']*1e3:.1f}, {r.get('fy', 0.0)*1e3:.1f}, "
                                      f"{r['fz']*1e3:.1f}) mm"))
        elif n:
            self.lbl_az_info.config(text=f"Index: {self.current_idx + 1}")
            self.lbl_law.config(text=f"Law {self.current_idx + 1}/{n}")

    def _get_law_data(self, idx):
        """
        Returns (interface_points_mm, target_mm) for focal_points[idx],
        reusing the delay law already computed by App.run_calculation
        where available instead of re-solving the Fermat problem.
        """
        fp = self.focal_points[idx]
        if idx < len(self.results) and 'interface_points' in self.results[idx]:
            int_pts = self.results[idx]['interface_points']
            target = np.array(fp)
        else:
            law = self.solver.calculate_law(fp[0], fp[1], fp[2],
                                            wave_type=self.wave_type)
            int_pts = law['interface_points']
            target = law['focal_point']
        return int_pts * 1000, np.asarray(target) * 1000

    def refresh_plot(self):
        raise NotImplementedError


class PlayMixin:
    """Play/Pause animation over every law in order."""

    def _add_play(self, column):
        self.play_btn = ttk.Button(self.controls, text="Play", command=self.toggle_play)
        self.play_btn.grid(row=0, column=column, padx=5, pady=2)
        self.anim_job = None

    def toggle_play(self):
        if self.is_playing:
            self.is_playing = False
            self.play_btn.config(text="Play")
            if self.anim_job:
                self.after_cancel(self.anim_job)
                self.anim_job = None
        else:
            self.is_playing = True
            self.play_btn.config(text="Pause")
            self.animate()

    def animate(self):
        if not self.is_playing or not self.focal_points:
            return
        # Walk the flat law index; show_law keeps the sliders in step with it.
        self.show_law(self.current_idx + 1)
        self.anim_job = self.after(100, self.animate)


class PlottingPanel(PlayMixin, LawNavigatorPanel):
    def __init__(self, parent):
        super().__init__(parent, toolbar=True)

        self._add_play(column=2)
        self.show_all_var = tk.BooleanVar(value=False)
        self.chk_show_all = ttk.Checkbutton(self.controls, text="Show All",
                                            variable=self.show_all_var,
                                            command=self.refresh_plot)
        self.chk_show_all.grid(row=0, column=3, padx=5, pady=2)

        self.component_thickness_mm = 0.0
        self.outline_mm = None
        self._setup_axes()

    def _setup_axes(self):
        self.ax.clear()
        self.ax.set_title("Ray Tracing Preview")
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Z (mm)")
        self.ax.invert_yaxis()
        self.ax.grid(True)
        self.ax.set_aspect("equal")

    def update_plot(self, solver, focal_points, wave_type, results=None,
                    is_matrix=False, component_thickness_mm=0.0, outline_mm=None):
        """Called by App when calculation is done."""
        self.component_thickness_mm = component_thickness_mm
        self.outline_mm = outline_mm
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return

        self.figure.clear()

        probe = self.solver.probe
        is_linear = (getattr(probe, "num_elements_y", 1) == 1
                     and not hasattr(probe, "array_separation"))

        if is_linear:
            self.ax = self.figure.add_subplot(111)
            axes_list = [(self.ax, 0)]
        else:
            ax_x = self.figure.add_subplot(121)
            ax_y = self.figure.add_subplot(122)
            axes_list = [(ax_x, 0), (ax_y, 1)]
            self.ax = ax_x

        show_all = self.show_all_var.get()
        num_points = len(self.focal_points)
        indices = list(range(num_points)) if show_all else [self.current_idx]

        for ax, dim_idx in axes_list:
            draw_projection(ax, self.solver, self._get_law_data, indices,
                            dim_idx, self.wave_type, show_all,
                            component_thickness_mm=self.component_thickness_mm,
                            outline_mm=self.outline_mm)

        if show_all:
            self.lbl_az_info.config(text=f"All {num_points} Laws")
            if self.is_matrix:
                self.lbl_sk_info.config(text="")

        self.figure.tight_layout()
        self.canvas.draw_idle()


class Scene3DPanel(PlayMixin, LawNavigatorPanel):
    """3D view of the selected law: elements, wedge, interface, rays and the sweep's focal points."""

    MAX_RAYS = 48

    def __init__(self, parent):
        super().__init__(parent, projection="3d")
        self._add_play(column=2)
        views = ttk.Frame(self.controls)
        views.grid(row=1, column=2, columnspan=2, padx=5, sticky="w")
        for name in VIEW_PRESETS:
            ttk.Button(views, text=name, width=5,
                       command=lambda n=name: self.set_view(n)).pack(side=tk.LEFT, padx=1)
        self.show_locus_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.controls, text="Sweep focal points", variable=self.show_locus_var,
                        command=self.refresh_plot).grid(row=0, column=3, padx=5)
        self.component_thickness_mm = 0.0
        self.outline_mm = None
        self.view = VIEW_PRESETS["Iso"]
        self.ax.set_title("3D ray scene: calculate laws to populate")

    def update_plot(self, solver, focal_points, wave_type, results=None,
                    is_matrix=False, component_thickness_mm=0.0, outline_mm=None):
        self.component_thickness_mm = component_thickness_mm
        self.outline_mm = outline_mm
        # The skew slider is useful for any probe here, but skew only sweeps for matrices.
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def set_view(self, name):
        self.view = VIEW_PRESETS[name]
        self.ax.view_init(*self.view)
        self.canvas.draw_idle()

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
        if self.ax.name == "3d":
            # Keep the user's last camera when redrawing.
            self.view = (self.ax.elev, self.ax.azim)
        self.figure.clear()
        self.ax = self.figure.add_subplot(111, projection="3d")
        focal_mm = np.asarray(self.focal_points, dtype=float) * 1000
        draw_scene_3d(self.ax, self.solver, self._get_law_data(self.current_idx), focal_mm,
                      self.current_idx, self.wave_type,
                      component_thickness_mm=self.component_thickness_mm,
                      outline_mm=self.outline_mm, max_rays=self.MAX_RAYS,
                      show_locus=self.show_locus_var.get())
        self.ax.view_init(*self.view)
        self.canvas.draw_idle()


class DelayHistogramPanel(LawNavigatorPanel):
    """
    Delay profile of the selected law: a bar chart against element number
    for linear probes, and a delay map over the element grid (one per
    array) for matrix probes, with element numbers in the chosen
    numbering convention.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.global_max_delay = None
        self._setup_axes()

    def _setup_axes(self):
        self.ax.clear()
        self.ax.set_title("Delay Profile")
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (microseconds)")
        self.ax.grid(True)

    def update_plot(self, solver, focal_points, wave_type, global_max_delay=None,
                    results=None, is_matrix=False):
        """Called by App when calculation is done."""
        self.global_max_delay = global_max_delay
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

    def _delays(self):
        # Reuse delays already computed by App.run_calculation where possible
        if (self.current_idx < len(self.results)
                and 'delays_us' in self.results[self.current_idx]):
            return np.asarray(self.results[self.current_idx]['delays_us'], dtype=float)
        fp = self.focal_points[self.current_idx]
        law = self.solver.calculate_law(fp[0], fp[1], fp[2], wave_type=self.wave_type)
        return law['delays'] * 1e6

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return

        delays = self._delays()
        probe = self.solver.probe
        vmax = self.global_max_delay
        vmax = vmax if (vmax is not None and np.isfinite(vmax) and vmax > 0) else None
        title = f"Delay Profile - Law {self.current_idx + 1}"

        self.figure.clear()
        if getattr(probe, "num_elements_y", 1) > 1:
            order = getattr(probe, "element_order", "column-first")
            draw_aperture_maps(self.figure, probe, delays, vmax=vmax,
                               title=f"{title} (numbering: {order})")
            self.ax = self.figure.axes[0]
            self.canvas.draw_idle()
            return

        self.ax = self.figure.add_subplot(111)
        num_elements = len(delays)
        element_ids = np.arange(1, num_elements + 1)
        active = np.isfinite(delays)
        self.ax.bar(element_ids[active], delays[active], color='skyblue', edgecolor='black',
                    label="Active")
        if (~active).any():
            self.ax.plot(element_ids[~active], np.zeros((~active).sum()), "x",
                         color=COLOR_ELEMENT_INACTIVE, label="Inactive")
            self.ax.legend(loc="upper right", fontsize=7)
        if hasattr(probe, "array_separation"):
            self.ax.axvline(num_elements / 2 + 0.5, color="#64748b", linestyle=":",
                            linewidth=1)

        self.ax.set_title(title)
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (μs)")
        self.ax.set_xlim(0.5, num_elements + 0.5)
        if vmax:
            self.ax.set_ylim(0, vmax * 1.1)
        self.ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        self.figure.tight_layout()
        self.canvas.draw_idle()
