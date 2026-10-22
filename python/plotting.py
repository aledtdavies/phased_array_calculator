import tkinter as tk
from tkinter import ttk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

from scene import draw_projection


class LawNavigatorPanel(ttk.Frame):
    """
    Base panel: a matplotlib canvas plus angle/skew sliders that map the
    selected (angle, skew) pair to a flat law index. Subclasses implement
    refresh_plot().
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
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

    def update_navigation(self, solver, focal_points, wave_type, results, is_matrix):
        """Rebuild the (angle, skew) -> law index mapping and slider ranges."""
        self.solver = solver
        self.focal_points = focal_points
        self.wave_type = wave_type
        self.is_matrix = is_matrix
        self.results = results if results else []

        if self.results:
            self.angle_values = sorted({r['angle'] for r in self.results})
            self.skew_values = sorted({r.get('skew', 0.0) for r in self.results})

            self.slider.config(to=max(0, len(self.angle_values) - 1))
            self.slider_skew.config(to=max(0, len(self.skew_values) - 1))
            self.slider.set(0)
            self.slider_skew.set(0)

            self.index_map = {
                (r['angle'], r.get('skew', 0.0)): i
                for i, r in enumerate(self.results)
            }
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

    def set_sliders(self, angle_val, skew_val):
        if angle_val in self.angle_values:
            self.slider.set(self.angle_values.index(angle_val))
        if skew_val in self.skew_values:
            self.slider_skew.set(self.skew_values.index(skew_val))
        self.on_slider_change()

    def on_slider_change(self, val=None):
        i_az = int(self.slider.get())
        i_sk = int(self.slider_skew.get()) if self.is_matrix else 0

        if self.angle_values:
            az_val = self.angle_values[i_az]
            self.lbl_az_info.config(text=f"Angle: {az_val:.1f}°")
            sk_val = (self.skew_values[i_sk]
                      if self.skew_values and i_sk < len(self.skew_values) else 0.0)
            self.lbl_sk_info.config(text=f"Skew: {sk_val:.1f}°")
            self.current_idx = self.index_map.get((az_val, sk_val), 0)
        else:
            self.current_idx = i_az
            self.lbl_az_info.config(text=f"Index: {self.current_idx + 1}")

        if not self.is_playing:
            self.refresh_plot()

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


class PlottingPanel(LawNavigatorPanel):
    def __init__(self, parent):
        super().__init__(parent)

        # Extra controls: Play + Show All on the angle-slider row
        self.play_btn = ttk.Button(self.controls, text="Play", command=self.toggle_play)
        self.play_btn.grid(row=0, column=2, padx=5, pady=2)

        self.show_all_var = tk.BooleanVar(value=False)
        self.chk_show_all = ttk.Checkbutton(self.controls, text="Show All",
                                            variable=self.show_all_var,
                                            command=self.refresh_plot)
        self.chk_show_all.grid(row=0, column=3, padx=5, pady=2)

        self.anim_job = None
        self.component_thickness_mm = 0.0
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
                    is_matrix=False, component_thickness_mm=0.0):
        """Called by App when calculation is done."""
        self.component_thickness_mm = component_thickness_mm
        self.update_navigation(solver, focal_points, wave_type, results, is_matrix)

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
        self.current_idx += 1
        if self.current_idx >= len(self.focal_points):
            self.current_idx = 0
        self.slider.set(self.current_idx)
        self.refresh_plot()
        self.anim_job = self.after(100, self.animate)

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
                            component_thickness_mm=self.component_thickness_mm)

        if show_all:
            self.lbl_az_info.config(text=f"All {num_points} Laws")
            if self.is_matrix:
                self.lbl_sk_info.config(text="")

        self.figure.tight_layout()
        self.canvas.draw_idle()


class DelayHistogramPanel(LawNavigatorPanel):
    """
    Panel to display the Delay Profile (Histogram of Delay vs Element) for a
    selected law.
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

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return

        self.ax.clear()

        # Reuse delays already computed by App.run_calculation where possible
        if (self.current_idx < len(self.results)
                and 'delays_us' in self.results[self.current_idx]):
            delays = self.results[self.current_idx]['delays_us']
        else:
            fp = self.focal_points[self.current_idx]
            law = self.solver.calculate_law(fp[0], fp[1], fp[2],
                                            wave_type=self.wave_type)
            delays = law['delays'] * 1e6

        num_elements = len(delays)
        element_ids = range(1, num_elements + 1)

        self.ax.bar(element_ids, delays, color='skyblue', edgecolor='black')

        self.ax.set_title(f"Delay Profile - Law {self.current_idx + 1}")
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (μs)")
        self.ax.set_xlim(0.5, num_elements + 0.5)

        if self.global_max_delay:
            self.ax.set_ylim(0, self.global_max_delay * 1.1)

        self.ax.grid(True, axis='y', linestyle='--', alpha=0.7)

        self.canvas.draw_idle()
