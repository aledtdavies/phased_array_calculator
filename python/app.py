import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
import csv
import json
import numpy as np

# from material import Material
from material import Material
from probe import Probe, create_probe_assembly
from wedge import Wedge
from delay_law import DelayLaw

from panels import ProbePanel, WedgePanel, MaterialPanel, ScanPanel, SubAperturePanel
from plotting import PlottingPanel, DelayHistogramPanel


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Binding MouseWheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _on_mousewheel(self, event):
        # Only scroll if the canvas is visible
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Phased Array Focal Law Calculator")
        self.geometry("1200x900")
        
        # Style Configuration
        style = ttk.Style(self)
        if 'clam' in style.theme_names():
            style.theme_use('clam')
            
        default_font = ("Segoe UI", 10)
        style.configure(".", font=default_font)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=2)
        style.configure("TEntry", padding=2)
        
        self.create_menu()
        
        # Main Layout: Left Sidebar Container, Right (Plot)
        left_container = ttk.Frame(self, padding=5)
        left_container.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        right_frame = ttk.Frame(self, padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # --- Left Sidebar (Scrollable) ---
        self.scroll_frame = ScrollableFrame(left_container)
        self.scroll_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Inner frame for widgets
        left_frame = self.scroll_frame.scrollable_frame
        
        self.probe_panel = ProbePanel(left_frame)
        self.probe_panel.pack(fill=tk.X, pady=5)
        
        self.wedge_panel = WedgePanel(left_frame)
        self.wedge_panel.pack(fill=tk.X, pady=5)
        
        self.mat_panel = MaterialPanel(left_frame)
        self.mat_panel.pack(fill=tk.X, pady=5)
        
        self.scan_panel = ScanPanel(left_frame)
        self.scan_panel.pack(fill=tk.X, pady=5)
        
        self.sub_aperture_panel = SubAperturePanel(left_frame)
        self.sub_aperture_panel.pack(fill=tk.X, pady=5)
        
        # Calculate Button
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        self.calc_btn = ttk.Button(btn_frame, text="Calculate Laws", command=self.run_calculation)
        self.calc_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.export_btn = ttk.Button(btn_frame, text="Export CSV", command=self.export_csv, state="disabled")
        self.export_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        # Status Label (Fixed at bottom of left_container, outside scroll)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(left_container, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        # Wire up dynamic panel visibility based on Probe Type
        self.probe_panel.bind("<<ProbeTypeChanged>>", self.on_probe_type_changed)
        
        # --- Right Area ---
        # Notebook for Plot and Data
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Ray Tracing
        self.plot_tab = PlottingPanel(self.notebook)
        self.notebook.add(self.plot_tab, text="Ray Tracing")
        
        # Tab 2: Data Table
        self.data_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.data_tab, text="Data Table")
        
        # Tab 3: Delays Histogram (New)
        self.hist_tab = DelayHistogramPanel(self.notebook)
        self.notebook.add(self.hist_tab, text="Delays")

        # Treeview setup (Tab 2 content)
        cols = ("ID", "Angle", "Skew", "Fx", "Fy", "Fz", "MinD", "MaxD")
        self.tree = ttk.Treeview(self.data_tab, columns=cols, show="headings")
        
        # Headers
        self.tree.heading("ID", text="#")
        self.tree.heading("Angle", text="Angle (°)")
        self.tree.heading("Skew", text="Skew (°)")
        self.tree.heading("Fx", text="Fx (mm)")
        self.tree.heading("Fy", text="Fy (mm)")
        self.tree.heading("Fz", text="Fz (mm)")
        self.tree.heading("MinD", text="Min Delay (µs)")
        self.tree.heading("MaxD", text="Max Delay (µs)")
        
        # Column width
        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Angle", width=60, anchor="center")
        self.tree.column("Skew", width=60, anchor="center")
        self.tree.column("Fx", width=60, anchor="center")
        self.tree.column("Fy", width=60, anchor="center")
        self.tree.column("Fz", width=60, anchor="center")
        self.tree.column("MinD", width=80, anchor="center")
        self.tree.column("MaxD", width=80, anchor="center")
        
        # Scrollbar
        vsb = ttk.Scrollbar(self.data_tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind select
        self.tree.bind("<<TreeviewSelect>>", self.on_table_select)

        self.last_results = None

    def on_probe_type_changed(self, event=None):
        vals = self.probe_panel.get_values()
        ptype = vals.get("probe_type", "Linear")
        self.wedge_panel.update_visibility(ptype)
        self.scan_panel.update_visibility(ptype)
        self.sub_aperture_panel.update_visibility(ptype)

    def create_menu(self):
        menubar = tk.Menu(self)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Configuration", command=self.save_config)
        file_menu.add_command(label="Load Configuration", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Export Element Coordinates", command=self.export_element_coords)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        self.config(menu=menubar)

    def save_config(self):
        config = {
            "probe": self.probe_panel.get_values(),
            "wedge": self.wedge_panel.get_values(),
            "material": self.mat_panel.get_values(),
            "scan": self.scan_panel.get_values(),
            "sub_aperture": self.sub_aperture_panel.get_values()
        }
        
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Config", "*.json"), ("All Files", "*.*")]
        )
        if fpath:
            try:
                with open(fpath, 'w') as f:
                    json.dump(config, f, indent=4)
                self.status_var.set(f"Configuration saved to {os.path.basename(fpath)}")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))

    def load_config(self):
        fpath = filedialog.askopenfilename(
            filetypes=[("JSON Config", "*.json"), ("All Files", "*.*")]
        )
        if fpath:
            try:
                with open(fpath, 'r') as f:
                    config = json.load(f)
                
                if "probe" in config: self.probe_panel.set_values(config["probe"])
                if "wedge" in config: self.wedge_panel.set_values(config["wedge"])
                if "material" in config: self.mat_panel.set_values(config["material"])
                if "scan" in config: self.scan_panel.set_values(config["scan"])
                if "sub_aperture" in config: self.sub_aperture_panel.set_values(config["sub_aperture"])
                
                self.status_var.set(f"Configuration loaded from {os.path.basename(fpath)}")
            except Exception as e:
                messagebox.showerror("Load Error", str(e))

    def export_element_coords(self):
        try:
            solver = self.get_solver()
        except Exception as e:
            messagebox.showerror("Export Error", f"Cannot formulate probe geometry: {e}")
            return
            
        fpath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV File", "*.csv"), 
                ("MATLAB MAT File", "*.mat"),
                ("MATLAB Script", "*.m"),
                ("All Files", "*.*")
            ],
            title="Export Element Coordinates"
        )
        
        if fpath:
            try:
                solver.export_element_positions(fpath)
                self.status_var.set(f"Element coordinates exported to {os.path.basename(fpath)}")
                messagebox.showinfo("Success", f"Exported element coordinates to {os.path.basename(fpath)}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    def get_solver(self):
        # 1. Probe
        pv = self.probe_panel.get_values()
        wv = self.wedge_panel.get_values()
        sav = self.sub_aperture_panel.get_values()
        
        ptype = pv.get("probe_type", "Linear")
        probe = create_probe_assembly(
            probe_type=ptype,
            num_elements=int(pv["num_elements"]),
            pitch=pv["pitch_mm"] * 1e-3,
            freq=pv["freq_mhz"] * 1e6,
            num_elements_y=int(pv.get("num_elements_y", 1)),
            pitch_y=pv.get("pitch_y_mm", 0.0) * 1e-3,
            array_separation=wv.get("array_sep_mm", 0.0) * 1e-3,
            start_element=sav.get("start_element", 1),
            num_active_elements=sav.get("num_active_elements", 0),
            element_order=sav.get("element_order", "column-first")
        )
        
        # 2. Material
        mv = self.mat_panel.get_values()
        mat = Material(
            velocity_longitudinal=mv["vel_long_ms"],
            velocity_shear=mv["vel_shear_ms"]
        )
        
        # 3. Wedge
        wedge = Wedge(
            angle_degrees=wv["angle_deg"],
            height_at_element1=wv["height_mm"] * 1e-3,
            velocity=wv["velocity_ms"],
            probe_offset_x=wv["offset_mm"] * 1e-3,
            roof_angle_degrees=wv.get("roof_angle_deg", 0.0)
        )
        
        return DelayLaw(probe, wedge, mat)

    def run_calculation(self):
        try:
            solver = self.get_solver()
            sv = self.scan_panel.get_values()
            
            start = sv["start_angle"]
            end = sv["end_angle"]
            step = sv["step_angle"]
            
            # Determine skew angles based on probe type
            ptype = self.probe_panel.get_values().get("probe_type", "Linear")
            is_matrix = ptype in ["Matrix", "Dual Matrix"]
            
            if is_matrix:
                s_start = sv.get("start_skew", 0.0)
                s_end = sv.get("end_skew", 0.0)
                s_step = sv.get("step_skew", 1.0)
            else:
                s_start, s_end, s_step = 0.0, 0.0, 1.0
                
            skew_angles = []
            if s_step > 0:
                skew_angles = np.arange(s_start, s_end + s_step, s_step)
                if skew_angles[-1] < s_end:
                    skew_angles = np.append(skew_angles, s_end)
            else:
                skew_angles = np.array([s_start])

            # Determine Y Focus targets
            y_mode = sv.get("y_focus_mode", "Derived from Skew")
            fy_overrides = None
            if is_matrix:
                if y_mode == "Fixed Y":
                    fy_overrides = [sv.get("target_y_mm", 0.0) * 1e-3]
                elif y_mode == "Y Sweep":
                    y_s = sv.get("y_start_mm", 0.0) * 1e-3
                    y_e = sv.get("y_end_mm", 0.0) * 1e-3
                    y_st = sv.get("y_step_mm", 1.0) * 1e-3
                    if y_st > 0:
                        y_sweep = np.arange(y_s, y_e + y_st, y_st)
                        if y_sweep[-1] < y_e:
                            y_sweep = np.append(y_sweep, y_e)
                        fy_overrides = y_sweep.tolist()
                    else:
                        fy_overrides = [y_s]
            
            param_val = sv["param_val"] * 1e-3 # Convert mm to meters
            
            focus_mode = sv["focus_mode"]
            wave_type = sv["wave_type"]
            
            # Determine Velocities for Snell's Law (Beam Steering)
            v_wedge = solver.wedge.velocity
            if wave_type == "Shear" and solver.material.velocity_shear:
                v_mat = solver.material.velocity_shear
            else:
                v_mat = solver.material.velocity_longitudinal
            
            # 1. Find Probe Center (Geometric Center of Array)
            elements = solver.wedge.get_transformed_elements(solver.probe)
            center_x = np.mean(elements[:, 0])
            center_y = np.mean(elements[:, 1])
            center_z = np.mean(elements[:, 2])
            
            # Dist to Interface (Vertical)
            h_wedge = abs(center_z) 
            
            # Generate Angles
            angles = np.arange(start, end + step, step)
            if step > 0 and angles[-1] < end:
                angles = np.append(angles, end)
                
            results = []
            focal_points = []
            
            self.status_var.set("Calculating...")
            self.update_idletasks()
            
            # Clear Tree
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            for i, ang in enumerate(angles):
                 beta_deg = ang
                 beta_rad = np.radians(beta_deg)
                 
                 # 2. Snell's Law to find Incident Angle (Alpha) in Wedge
                 # sin(alpha) / v1 = sin(beta) / v2
                 sin_alpha = (v_wedge / v_mat) * np.sin(beta_rad)
                 
                 if abs(sin_alpha) > 1.0:
                     # Critical Angle Exceeded
                     for skew_deg in skew_angles:
                         self.tree.insert("", "end", values=(len(results)+1, f"{ang:.1f}", f"{skew_deg:.1f}", "Err", "Brit", "-", "-", "-"))
                     continue
                 
                 alpha_rad = np.arcsin(sin_alpha)
                 
                 # 3. Beam Entry Point (P_int)
                 x_int = center_x + h_wedge * np.tan(alpha_rad)
                 
                 # 4. Focal Point (F) base
                 if focus_mode == "Constant Depth":
                     fz = param_val
                     f_primary = fz * np.tan(beta_rad)
                     
                 elif focus_mode == "Vertical Line":
                     fx = param_val
                     if abs(np.tan(beta_rad)) < 1e-9:
                         fz = 1e6
                         f_primary = 0
                     else:
                         f_primary = fx - x_int
                         fz = f_primary / np.tan(beta_rad)
                         
                 else: # Constant Sound Path
                     R = param_val
                     fz = R * np.cos(beta_rad)
                     f_primary = R * np.sin(beta_rad)
                 
                 if fz < 0:
                     for skew_deg in skew_angles:
                         self.tree.insert("", "end", values=(len(results)+1, f"{ang:.1f}", f"{skew_deg:.1f}", "Err", "-", "Z<0", "-", "-"))
                     continue

                 # Loop over skews (permutations)
                 for skew_deg in skew_angles:
                     skew_rad = np.radians(skew_deg)
                     
                     # Determine 3D Focal point coordinates based on Focus Mode and Y mode
                     if focus_mode == "Constant Depth":
                         lx = x_int + f_primary * np.cos(skew_rad)
                         fy_list = fy_overrides if fy_overrides is not None else [center_y + f_primary * np.sin(skew_rad)]
                         fz_current = fz
                         
                     elif focus_mode == "Vertical Line":
                         # To keep X constant in 3D space, f_primary must extend further as skew increases
                         lx = fx
                         cos_s = np.cos(skew_rad)
                         f_primary_3d = (fx - x_int) / cos_s if abs(cos_s) > 1e-9 else f_primary
                         fz_current = f_primary_3d / np.tan(beta_rad) if abs(np.tan(beta_rad)) > 1e-9 else 1e6
                         fy_list = fy_overrides if fy_overrides is not None else [center_y + f_primary_3d * np.sin(skew_rad)]
                         
                     else: # Constant Sound Path
                         lx = x_int + f_primary * np.cos(skew_rad)
                         fz_current = fz
                         if fy_overrides is not None and y_mode == "Y Sweep":
                             # y sweep bypasses the explicit skew angles array completely!
                             fy_list = fy_overrides
                         else:
                             # default: derived from skew
                             fy_list = [center_y + f_primary * np.sin(skew_rad)]
                         
                     for ly in fy_list:
                         
                         if focus_mode == "Constant Sound Path" and fy_overrides is not None and y_mode == "Y Sweep":
                             # For Y sweep in const path, we back-calculate the effective skew for display
                             # sin(skew) = (ly - center_y) / f_primary
                             val = (ly - center_y) / f_primary if f_primary > 1e-9 else 0.0
                             if abs(val) <= 1.0:
                                 eff_skew_rad = np.arcsin(val)
                                 eff_skew_deg = np.degrees(eff_skew_rad)
                                 lx = x_int + f_primary * np.cos(eff_skew_rad)
                             else:
                                 # Y target unreachable with this path length
                                 self.tree.insert("", "end", values=(len(results)+1, f"{ang:.1f}", "-", "Err", "Y out", "of reach", "-", "-"))
                                 continue
                         else:
                             eff_skew_deg = skew_deg

                         law = solver.calculate_law(lx, ly, fz_current, wave_type=wave_type)
                         delays_us = law['delays'] * 1e6
                         
                         res_entry = {
                             'angle': ang,
                             'skew': eff_skew_deg,
                             'fx': lx,
                             'fy': ly,
                             'fz': fz_current,
                             'delays_us': delays_us,
                             'velocity_used': law['velocity_used']
                         }
                         results.append(res_entry)
                         idx = len(results) - 1
                         focal_points.append((lx, ly, fz_current))
                         
                         min_d = np.min(delays_us)
                         max_d = np.max(delays_us)
                         
                         self.tree.insert("", "end", values=(idx+1, f"{ang:.1f}", f"{eff_skew_deg:.1f}", f"{lx*1000:.2f}", f"{ly*1000:.2f}", f"{fz_current*1000:.2f}", f"{min_d:.2f}", f"{max_d:.2f}"), tags=(idx,))
                         
                     if focus_mode == "Constant Sound Path" and fy_overrides is not None and y_mode == "Y Sweep":
                         # In this specific case, the sweep handles all Ys for this angle, 
                         # we don't need to iterate the outer explicit skew loop anymore.
                         break

            self.last_results = results
            
            # Update Plots
            if focal_points:
                global_max_delay = 0.0
                if results:
                    # results stores 'delays_us'
                    all_delays = [r['delays_us'] for r in results]
                    flat = np.concatenate(all_delays)
                    global_max_delay = np.max(flat)
                
                self.plot_tab.update_plot(solver, focal_points, wave_type, results=results, is_matrix=is_matrix)
                self.hist_tab.update_plot(solver, focal_points, wave_type, global_max_delay=global_max_delay, results=results, is_matrix=is_matrix)
            else:
                self.plot_tab.ax.clear()
                self.plot_tab.canvas.draw()
                self.hist_tab.ax.clear()
                self.hist_tab.canvas.draw()
            
            if not results:
                 messagebox.showwarning("No Results", "No valid focal laws could be calculated.\nPlease check your geometry, angles, and target coordinates.")
                 self.status_var.set("Calculation complete. 0 laws generated.")
                 self.export_btn.config(state="disabled")
            else:
                 self.status_var.set(f"Calculation complete. {len(results)} laws generated.")
                 self.export_btn.config(state="normal")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set("Error during calculation.")
            print(e)
            
    def on_table_select(self, event):
        selected = self.tree.selection()
        if not selected:
             return
        
        item = selected[0]
        # The values are: ID, Angle, Skew, Fx, Fy, Fz, MinD, MaxD
        vals = self.tree.item(item, 'values')
        
        try:
            angle_val = float(vals[1])
            skew_val = float(vals[2])
            
            # Update Both Plot Sliders
            if hasattr(self.plot_tab, 'set_sliders'):
                self.plot_tab.set_sliders(angle_val, skew_val)
            if hasattr(self.hist_tab, 'set_sliders'):
                self.hist_tab.set_sliders(angle_val, skew_val)
        except Exception:
            pass

    def export_csv(self):
        if not self.last_results:
            messagebox.showinfo("Export", "No data to export.")
            return
            
        filename = "focal_laws_gui.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Header
                sv = self.scan_panel.get_values()
                num_els = len(self.last_results[0]['delays_us'])
                
                header = ['LawID', 'Angle_Deg', 'Skew_Deg', 'Fx_mm', 'Fy_mm', 'Fz_mm', 'Velocity_m_s'] + [f'El_{i+1}_us' for i in range(num_els)]
                writer.writerow(header)
                
                for i, res in enumerate(self.last_results):
                    row = [i+1, res['angle'], res.get('skew', 0.0), res['fx']*1000, res.get('fy', 0.0)*1000, res['fz']*1000, res['velocity_used']]
                    row.extend(res['delays_us'])
                    writer.writerow(row)
            
            messagebox.showinfo("Success", f"Exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    app = App()
    app.mainloop()
