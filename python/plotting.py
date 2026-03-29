import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np

class PlottingPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        
        # 1. Plot Area
        self.figure = plt.Figure(figsize=(6, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 2. Controls Area (Grid)
        controls = ttk.Frame(self)
        controls.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Row 0: Azimuth Slider
        self.lbl_az_info = ttk.Label(controls, text="Angle: 0.0°", width=15)
        self.lbl_az_info.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        self.slider = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slider.grid(row=0, column=1, sticky="ew", padx=5)
        
        self.play_btn = ttk.Button(controls, text="Play", command=self.toggle_play)
        self.play_btn.grid(row=0, column=2, padx=5, pady=2)
        
        self.show_all_var = tk.BooleanVar(value=False)
        self.chk_show_all = ttk.Checkbutton(controls, text="Show All", variable=self.show_all_var, command=self.refresh_plot)
        self.chk_show_all.grid(row=0, column=3, padx=5, pady=2)
        
        # Row 1: Skew Slider
        self.lbl_sk_info = ttk.Label(controls, text="Skew: 0.0°", width=15)
        self.lbl_sk_info.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        
        self.slider_skew = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slider_skew.grid(row=1, column=1, sticky="ew", padx=5)
        
        controls.columnconfigure(1, weight=1)
        
        # Internal State
        self.solver = None
        self.focal_points = []
        self.wave_type = 'longitudinal'
        self.current_idx = 0
        self.anim_job = None
        self.is_playing = False
        
        self.results = []
        self.angle_values = []
        self.skew_values = []
        self.index_map = {}
        self.is_matrix = False
        
        # Initial empty plot setup
        self._setup_axes()

    def _setup_axes(self):
        self.ax.clear()
        self.ax.set_title("Ray Tracing Preview")
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Z (mm)")
        self.ax.invert_yaxis()
        self.ax.grid(True)
        self.ax.axis('equal')

    def update_plot(self, solver, focal_points, wave_type, results=None, is_matrix=False):
        """
        Called by App when calculation is done.
        """
        self.solver = solver
        self.focal_points = focal_points
        self.wave_type = wave_type
        self.is_matrix = is_matrix
        self.results = results if results else []
        
        # Map values to indices
        if self.results:
            angles = set()
            skews = set()
            for r in self.results:
                angles.add(r['angle'])
                skews.add(r.get('skew', 0.0))
            
            self.angle_values = sorted(list(angles))
            self.skew_values = sorted(list(skews))
            
            self.slider.config(to=max(0, len(self.angle_values)-1))
            self.slider_skew.config(to=max(0, len(self.skew_values)-1))
            self.slider.set(0)
            self.slider_skew.set(0)
            
            # Map (angle_val, skew_val) -> flat index
            self.index_map = {}
            for i, r in enumerate(self.results):
                self.index_map[(r['angle'], r.get('skew', 0.0))] = i
        else:
            self.slider.config(to=max(0, len(focal_points)-1))
            self.slider.set(0)
            self.index_map = {}
            
        # UI Visibility
        if is_matrix:
            self.lbl_sk_info.grid()
            self.slider_skew.grid()
        else:
            self.lbl_sk_info.grid_remove()
            self.slider_skew.grid_remove()
            
        self.on_slider_change()
        
    def set_sliders(self, angle_val, skew_val):
        if angle_val in self.angle_values:
            idx = self.angle_values.index(angle_val)
            self.slider.set(idx)
        if skew_val in self.skew_values:
            idx = self.skew_values.index(skew_val)
            self.slider_skew.set(idx)
        self.on_slider_change()

    def on_slider_change(self, val=None):
        i_az = int(self.slider.get())
        if self.is_matrix:
            i_sk = int(self.slider_skew.get())
        else:
            i_sk = 0
            
        if self.angle_values:
            az_val = self.angle_values[i_az]
            self.lbl_az_info.config(text=f"Angle: {az_val:.1f}°")
            sk_val = self.skew_values[i_sk] if self.skew_values and i_sk < len(self.skew_values) else 0.0
            self.lbl_sk_info.config(text=f"Skew: {sk_val:.1f}°")
            self.current_idx = self.index_map.get((az_val, sk_val), 0)
        else:
            self.current_idx = i_az
            self.lbl_az_info.config(text=f"Index: {self.current_idx+1}")
            
        if not self.is_playing:
            self.refresh_plot()

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
        
        # Increment index
        self.current_idx += 1
        if self.current_idx >= len(self.focal_points):
            self.current_idx = 0
            
        self.slider.set(self.current_idx)
        self.refresh_plot()
        
        # Schedule next frame (e.g., 100ms)
        self.anim_job = self.after(100, self.animate)

    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
            
        self.figure.clear()
        
        # Check probe type logic
        probe = self.solver.probe
        is_linear = getattr(probe, "num_elements_y", 1) == 1 and not hasattr(probe, "array_separation")
        has_yz = not is_linear
        is_dual = hasattr(probe, "array_separation")
        
        if has_yz:
            ax_x = self.figure.add_subplot(121)
            ax_y = self.figure.add_subplot(122)
            axes_list = [(ax_x, 0), (ax_y, 1)]
            self.ax = ax_x # Keep reference for other things like clear()
        else:
            self.ax = self.figure.add_subplot(111)
            axes_list = [(self.ax, 0)]
            
        # 1. Plot Geometry
        elements = self.solver.wedge.get_transformed_elements(self.solver.probe)
        
        show_all = self.show_all_var.get()
        num_points = len(self.focal_points)
        
        if show_all:
            indices = range(num_points)
        else:
            indices = [self.current_idx]
            
        cmap = cm.get_cmap('jet')
        norm = mcolors.Normalize(vmin=0, vmax=max(1, num_points-1))
        
        for ax, dim_idx in axes_list:
            el_c = elements[:, dim_idx] * 1000
            el_z = elements[:, 2] * 1000
            
            # Interface
            ax.axhline(0, color='k', linestyle='-', linewidth=2, zorder=2)
            
            # Plot Elements
            if is_dual:
                n_half = len(el_c) // 2
                ax.plot(el_c[:n_half], el_z[:n_half], 'bs', markersize=4, label='Tx Array', zorder=3)
                ax.plot(el_c[n_half:], el_z[n_half:], 'rs', markersize=4, label='Rx Array', zorder=3)
            else:
                ax.plot(el_c, el_z, 'rs', markersize=4, label='Elements', zorder=3)
            
            # Plot Rays
            for idx in indices:
                fp = self.focal_points[idx]
                
                if show_all:
                    c = cmap(norm(idx))
                    alpha = 0.5
                else:
                    c = 'b'
                    alpha = 1.0
                
                law = self.solver.calculate_law(fp[0], fp[1], fp[2], wave_type=self.wave_type)
                int_pts = law['interface_points']
                target = law['focal_point'] * 1000
                
                # Outer Elements
                p_el_start = elements[0] * 1000
                p_int_start = int_pts[0] * 1000
                
                p_el_end = elements[-1] * 1000
                p_int_end = int_pts[-1] * 1000
                
                if is_dual:
                    n_half = len(elements) // 2
                    p_el_mid1 = elements[n_half - 1] * 1000
                    p_int_mid1 = int_pts[n_half - 1] * 1000
                    p_el_mid2 = elements[n_half] * 1000
                    p_int_mid2 = int_pts[n_half] * 1000
                    
                    # Tx/Rx colours (override jet cmap for dual)
                    c_tx = c if show_all else 'tab:blue'
                    c_rx = c if show_all else 'tab:red'
                    
                    # Array 1 (Tx) — Blue
                    ax.plot([p_el_start[dim_idx], p_int_start[dim_idx]], [p_el_start[2], p_int_start[2]], color=c_tx, alpha=alpha, linewidth=1)
                    ax.plot([p_int_start[dim_idx], target[dim_idx]], [p_int_start[2], target[2]], color=c_tx, alpha=alpha, linewidth=1)
                    ax.plot([p_el_mid1[dim_idx], p_int_mid1[dim_idx]], [p_el_mid1[2], p_int_mid1[2]], color=c_tx, alpha=alpha, linewidth=1)
                    ax.plot([p_int_mid1[dim_idx], target[dim_idx]], [p_int_mid1[2], target[2]], color=c_tx, alpha=alpha, linewidth=1)

                    # Array 2 (Rx) — Red
                    ax.plot([p_el_mid2[dim_idx], p_int_mid2[dim_idx]], [p_el_mid2[2], p_int_mid2[2]], color=c_rx, alpha=alpha, linewidth=1)
                    ax.plot([p_int_mid2[dim_idx], target[dim_idx]], [p_int_mid2[2], target[2]], color=c_rx, alpha=alpha, linewidth=1)
                    ax.plot([p_el_end[dim_idx], p_int_end[dim_idx]], [p_el_end[2], p_int_end[2]], color=c_rx, alpha=alpha, linewidth=1)
                    ax.plot([p_int_end[dim_idx], target[dim_idx]], [p_int_end[2], target[2]], color=c_rx, alpha=alpha, linewidth=1)
                else:
                    # Single Array Extents
                    ax.plot([p_el_start[dim_idx], p_int_start[dim_idx]], [p_el_start[2], p_int_start[2]], color=c, alpha=alpha, linewidth=1)
                    ax.plot([p_int_start[dim_idx], target[dim_idx]], [p_int_start[2], target[2]], color=c, alpha=alpha, linewidth=1)
                    ax.plot([p_el_end[dim_idx], p_int_end[dim_idx]], [p_el_end[2], p_int_end[2]], color=c, alpha=alpha, linewidth=1)
                    ax.plot([p_int_end[dim_idx], target[dim_idx]], [p_int_end[2], target[2]], color=c, alpha=alpha, linewidth=1)
                
                ax.plot(target[dim_idx], target[2], marker='o' if show_all else 'x', color=c, markersize=3 if show_all else 8)

            ax.set_title(f"Ray Tracing {'X-Z' if dim_idx==0 else 'Y-Z'} ({self.wave_type})")
            ax.set_xlabel("X (mm)" if dim_idx==0 else "Y (mm)")
            ax.set_ylabel("Z Depth (mm)")
            ax.invert_yaxis()
            ax.grid(True)
            ax.axis('equal')

        # Update Info Label
        if show_all:
             self.lbl_az_info.config(text=f"All {num_points} Laws")
             if self.is_matrix:
                 self.lbl_sk_info.config(text="")
        
        self.figure.tight_layout()
        self.canvas.draw()


class DelayHistogramPanel(ttk.Frame):
    """
    Panel to display the Delay Profile (Histogram of Delay vs Element) for a selected law.
    """
    def __init__(self, parent):
        super().__init__(parent)
        
        # 1. Plot Area
        self.figure = plt.Figure(figsize=(6, 5), dpi=100)
        self.ax = self.figure.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # 2. Controls Area (Grid)
        controls = ttk.Frame(self)
        controls.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Row 0: Azimuth Slider
        self.lbl_az_info = ttk.Label(controls, text="Angle: 0.0°", width=15)
        self.lbl_az_info.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        self.slider = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slider.grid(row=0, column=1, sticky="ew", padx=5)
        
        # Row 1: Skew Slider
        self.lbl_sk_info = ttk.Label(controls, text="Skew: 0.0°", width=15)
        self.lbl_sk_info.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        
        self.slider_skew = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slider_skew.grid(row=1, column=1, sticky="ew", padx=5)
        
        controls.columnconfigure(1, weight=1)
        
        # Internal State
        self.solver = None
        self.focal_points = []
        self.wave_type = 'longitudinal'
        self.current_idx = 0
        
        self.results = []
        self.angle_values = []
        self.skew_values = []
        self.index_map = {}
        self.is_matrix = False
        
        self._setup_axes()

    def _setup_axes(self):
        self.ax.clear()
        self.ax.set_title("Delay Profile")
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (microseconds)")
        self.ax.grid(True)

    def update_plot(self, solver, focal_points, wave_type, global_max_delay=None, results=None, is_matrix=False):
        """
        Called by App when calculation is done.
        """
        self.solver = solver
        self.focal_points = focal_points
        self.wave_type = wave_type
        self.global_max_delay = global_max_delay
        self.is_matrix = is_matrix
        self.results = results if results else []
        
        # Map values to indices
        if self.results:
            angles = set()
            skews = set()
            for r in self.results:
                angles.add(r['angle'])
                skews.add(r.get('skew', 0.0))
            
            self.angle_values = sorted(list(angles))
            self.skew_values = sorted(list(skews))
            
            self.slider.config(to=max(0, len(self.angle_values)-1))
            self.slider_skew.config(to=max(0, len(self.skew_values)-1))
            self.slider.set(0)
            self.slider_skew.set(0)
            
            # Map (angle_val, skew_val) -> flat index
            self.index_map = {}
            for i, r in enumerate(self.results):
                self.index_map[(r['angle'], r.get('skew', 0.0))] = i
        else:
            self.slider.config(to=max(0, len(focal_points)-1))
            self.slider.set(0)
            self.index_map = {}
            
        # UI Visibility
        if is_matrix:
            self.lbl_sk_info.grid()
            self.slider_skew.grid()
        else:
            self.lbl_sk_info.grid_remove()
            self.slider_skew.grid_remove()
            
        self.on_slider_change()

    def set_sliders(self, angle_val, skew_val):
        if angle_val in self.angle_values:
            idx = self.angle_values.index(angle_val)
            self.slider.set(idx)
        if skew_val in self.skew_values:
            idx = self.skew_values.index(skew_val)
            self.slider_skew.set(idx)
        self.on_slider_change()

    def on_slider_change(self, val=None):
        i_az = int(self.slider.get())
        if self.is_matrix:
            i_sk = int(self.slider_skew.get())
        else:
            i_sk = 0
            
        if self.angle_values:
            az_val = self.angle_values[i_az]
            self.lbl_az_info.config(text=f"Angle: {az_val:.1f}°")
            sk_val = self.skew_values[i_sk] if self.skew_values and i_sk < len(self.skew_values) else 0.0
            self.lbl_sk_info.config(text=f"Skew: {sk_val:.1f}°")
            self.current_idx = self.index_map.get((az_val, sk_val), 0)
        else:
            self.current_idx = i_az
            self.lbl_az_info.config(text=f"Index: {self.current_idx+1}")
            
        self.refresh_plot()
        
    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
            
        self.ax.clear()
        
        # Get Current Law
        fp = self.focal_points[self.current_idx]
        law = self.solver.calculate_law(fp[0], fp[1], fp[2], wave_type=self.wave_type)
        delays = law['delays'] * 1e6 # Convert to microseconds
        
        num_elements = len(delays)
        element_ids = range(1, num_elements + 1)
        
        # Bar Chart
        self.ax.bar(element_ids, delays, color='skyblue', edgecolor='black')
        
        # Formatting
        self.ax.set_title(f"Delay Profile - Law {self.current_idx+1}")
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (\u03bcs)") # micro symbol
        self.ax.set_xlim(0.5, num_elements + 0.5)
        
        if self.global_max_delay:
            # Add 10% headroom
            self.ax.set_ylim(0, self.global_max_delay * 1.1)
            
        self.ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        
        self.canvas.draw()
