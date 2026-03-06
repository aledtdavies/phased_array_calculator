import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon
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
        
        # 2. Controls Area
        controls = ttk.Frame(self)
        controls.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Label to show current Angle/Index
        self.lbl_info = ttk.Label(controls, text="Index: 0", width=15)
        self.lbl_info.pack(side=tk.LEFT, padx=5)
        
        # Slider
        self.slider = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Play/Pause
        self.is_playing = False
        self.play_btn = ttk.Button(controls, text="Play", command=self.toggle_play)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        # Show All Toggle
        self.show_all_var = tk.BooleanVar(value=False)
        self.chk_show_all = ttk.Checkbutton(controls, text="Show All", variable=self.show_all_var, command=self.refresh_plot)
        self.chk_show_all.pack(side=tk.LEFT, padx=5)
        
        # Internal State
        self.solver = None
        self.focal_points = []
        self.wave_type = 'longitudinal'
        self.current_idx = 0
        self.anim_job = None
        
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

    def update_plot(self, solver, focal_points, wave_type='longitudinal'):
        """
        Called by App when calculation is done.
        """
        self.solver = solver
        self.focal_points = focal_points
        self.wave_type = wave_type
        
        # Reset Controls
        num_laws = len(focal_points)
        if num_laws > 0:
            self.slider.config(to=num_laws - 1)
            self.slider.set(0)
            self.current_idx = 0
            self.lbl_info.config(text=f"Law 1 / {num_laws}")
        
        self.refresh_plot()

    def on_slider_change(self, val):
        self.current_idx = int(val)
        # Only refresh if not playing (animation handles refresh) OR if triggered manually
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
            
        self.ax.clear()
        
        # 1. Plot Geometry
        elements = self.solver.wedge.get_transformed_elements(self.solver.probe)
        el_x = elements[:, 0] * 1000
        el_z = elements[:, 1] * 1000
        
        # Define basic probe extent for fallback and roof line calc
        padding_basic = 5.0
        w_min_x = np.min(el_x) - padding_basic
        w_max_x = np.max(el_x) + padding_basic

        # Calculate Roof Line Equation: Z = m*X + c
        if len(elements) > 1:
            p1 = elements[0] * 1000
            p2 = elements[-1] * 1000
            denom = (p2[0] - p1[0])
            if abs(denom) < 1e-9:
                 m = 0
                 c_offset = p1[1]
            else:
                 m = (p2[1] - p1[1]) / denom
                 c_offset = p1[1] - m * p1[0]
        else:
            m = 0
            c_offset = el_z[0]

        # A. Wedge Polygon (Extended to cover beams)
        # We need the wedge to cover the probe AND the beam entry points.
        
        # Gather all interface points
        all_int_x = []
        for fp in self.focal_points:
            law = self.solver.calculate_law(fp[0], fp[1], wave_type=self.wave_type)
            if 'interface_points' in law:
                all_int_x.extend([p[0]*1000 for p in law['interface_points']])
        
        min_int_x = np.min(all_int_x) if all_int_x else w_min_x
        max_int_x = np.max(all_int_x) if all_int_x else w_max_x
        
        # Wedge Boundaries
        # Extend past the furthest element or beam
        padding = 15.0 # mm
        w_bound_min = min(w_min_x, min_int_x) - padding
        w_bound_max = max(w_max_x, max_int_x) + padding
        
        # Calculate Roof Line Z at these bounds
        z_roof_left = m * w_bound_min + c_offset
        z_roof_right = m * w_bound_max + c_offset
        
        # Clamp Z to 0 (Interface) if it goes into material
        z_roof_left = min(z_roof_left, 0)
        z_roof_right = min(z_roof_right, 0)
        
        # Vertical Faces
        wedge_pts = [
            [w_bound_min, 0],              # Bottom Left
            [w_bound_max, 0],              # Bottom Right
            [w_bound_max, z_roof_right],   # Top Right
            [w_bound_min, z_roof_left]     # Top Left
        ]
        
        wedge_patch = Polygon(wedge_pts, closed=True, facecolor='cyan', alpha=0.3, label='Wedge', zorder=1)
        self.ax.add_patch(wedge_patch)
            
        self.ax.axhline(0, color='k', linestyle='-', linewidth=2, zorder=2) # Interface
        
        # B. Component Polygon (Dynamic Size)
        # Determine bounds based on all rays
        all_fx = [fp[0]*1000 for fp in self.focal_points]
        all_fz = [fp[1]*1000 for fp in self.focal_points]
        
        # We need to account for the beam spread (X)
        if all_fx:
            min_beam_x = np.min(all_fx)
            max_beam_x = np.max(all_fx)
            max_beam_z = np.max(all_fz)
        else:
            min_beam_x = w_min_x
            max_beam_x = w_max_x
            max_beam_z = 50.0 # Default
            
        # Component Box should cover from somewhat left of everything to somewhat right
        # And down to max depth.
        # Ensure it covers the wedge area too (coupling)
        c_min_x = min(w_min_x, min_beam_x) - 10
        c_max_x = max(w_max_x, max_beam_x) + 10
        c_max_z = max_beam_z + 10
        
        comp_pts = [
            [c_min_x, 0],
            [c_max_x, 0],
            [c_max_x, c_max_z],
            [c_min_x, c_max_z]
        ]
        comp_patch = Polygon(comp_pts, closed=True, facecolor='lightgray', alpha=0.3, label='Component', zorder=0)
        self.ax.add_patch(comp_patch)

        # Plot Elements (on top of wedge)
        self.ax.plot(el_x, el_z, 'rs', markersize=4, label='Elements', zorder=3)
        
        # 2. Decide what to plot
        indices = []
        show_all = self.show_all_var.get()
        num_points = len(self.focal_points)
        
        if show_all:
            indices = range(num_points)
        else:
            indices = [self.current_idx]
            
        # Colormap
        cmap = cm.get_cmap('jet')
        norm = mcolors.Normalize(vmin=0, vmax=num_points-1)
        
        # Plot Rays
        for idx in indices:
            fp = self.focal_points[idx]
            
            # Determine color
            if show_all:
                c = cmap(norm(idx))
                alpha = 0.5
            else:
                c = 'b' # Default blue for single view
                alpha = 1.0
            
            # Recalculate Ray (fast enough for 32 rays)
            law = self.solver.calculate_law(fp[0], fp[1], wave_type=self.wave_type)
            int_pts = law['interface_points']
            target = law['focal_point']
            
            # Plot rays for Outer Elements
            p_el_start = elements[0] * 1000
            p_int_start = int_pts[0] * 1000
            
            p_el_end = elements[-1] * 1000
            p_int_end = int_pts[-1] * 1000
            
            p_tgt = target * 1000
            
            # Ray 1 (Element 1)
            self.ax.plot([p_el_start[0], p_int_start[0]], [p_el_start[1], p_int_start[1]], color=c, alpha=alpha, linewidth=1)
            self.ax.plot([p_int_start[0], p_tgt[0]], [p_int_start[1], p_tgt[1]], color=c, alpha=alpha, linewidth=1)
            
            # Ray N (Element N)
            self.ax.plot([p_el_end[0], p_int_end[0]], [p_el_end[1], p_int_end[1]], color=c, alpha=alpha, linewidth=1)
            self.ax.plot([p_int_end[0], p_tgt[0]], [p_int_end[1], p_tgt[1]], color=c, alpha=alpha, linewidth=1)
            
            # Mark Target
            self.ax.plot(p_tgt[0], p_tgt[1], marker='o' if show_all else 'x', color=c, markersize=3 if show_all else 8)

        # Update Info Label
        if not show_all:
             self.lbl_info.config(text=f"Law {self.current_idx + 1} / {num_points}")
        else:
             self.lbl_info.config(text=f"All {num_points} Laws")

        # Titles and Axes
        self.ax.set_title(f"Ray Tracing ({self.wave_type})")
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Z Depth (mm)")
        self.ax.invert_yaxis()
        self.ax.grid(True)
        self.ax.axis('equal')
        
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
        
        # 2. Controls Area
        controls = ttk.Frame(self)
        controls.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Label to show current Angle/Index
        self.lbl_info = ttk.Label(controls, text="Index: 0", width=15)
        self.lbl_info.pack(side=tk.LEFT, padx=5)
        
        # Slider
        self.slider = tk.Scale(controls, from_=0, to=1, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Internal State
        self.solver = None
        self.focal_points = []
        self.wave_type = 'longitudinal'
        self.current_idx = 0
        
        self._setup_axes()

    def _setup_axes(self):
        self.ax.clear()
        self.ax.set_title("Delay Profile")
        self.ax.set_xlabel("Element ID")
        self.ax.set_ylabel("Delay (microseconds)")
        self.ax.grid(True)

    def update_plot(self, solver, focal_points, wave_type='longitudinal', global_max_delay=None):
        """
        Called by App when calculation is done.
        """
        self.solver = solver
        self.focal_points = focal_points
        self.wave_type = wave_type
        self.global_max_delay = global_max_delay
        
        # Reset Controls
        num_laws = len(focal_points)
        if num_laws > 0:
            self.slider.config(to=num_laws - 1)
            self.slider.set(0)
            self.current_idx = 0
            self.lbl_info.config(text=f"Law 1 / {num_laws}")
        
        self.refresh_plot()

    def on_slider_change(self, val):
        self.current_idx = int(val)
        self.refresh_plot()
        
    def refresh_plot(self):
        if not self.solver or not self.focal_points:
            return
            
        self.ax.clear()
        
        # Get Current Law
        fp = self.focal_points[self.current_idx]
        law = self.solver.calculate_law(fp[0], fp[1], wave_type=self.wave_type)
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
        
        self.lbl_info.config(text=f"Law {self.current_idx + 1} / {len(self.focal_points)}")
        
        self.canvas.draw()
