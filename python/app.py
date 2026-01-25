import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
import csv
import json
import numpy as np

# Files are in the same directory now
from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw

from panels import ProbePanel, WedgePanel, MaterialPanel, ScanPanel
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
        
        # Calculate Button
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        self.calc_btn = ttk.Button(btn_frame, text="Calculate Laws", command=self.run_calculation)
        self.calc_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        self.export_btn = ttk.Button(btn_frame, text="Export CSV", command=self.export_csv, state="disabled")
        self.export_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)
        
        # Status Label (Fixed at bottom of left_container, outside scroll)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(left_container, textvariable=self.status_var, relief=tk.SUNKEN).pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

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
        cols = ("ID", "Angle", "Fx", "Fz", "MinD", "MaxD")
        self.tree = ttk.Treeview(self.data_tab, columns=cols, show="headings")
        
        # Headers
        self.tree.heading("ID", text="#")
        self.tree.heading("Angle", text="Angle (°)")
        self.tree.heading("Fx", text="Fx (mm)")
        self.tree.heading("Fz", text="Fz (mm)")
        self.tree.heading("MinD", text="Min Delay (µs)")
        self.tree.heading("MaxD", text="Max Delay (µs)")
        
        # Column width
        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Angle", width=70, anchor="center")
        self.tree.column("Fx", width=70, anchor="center")
        self.tree.column("Fz", width=70, anchor="center")
        self.tree.column("MinD", width=90, anchor="center")
        self.tree.column("MaxD", width=90, anchor="center")
        
        # Scrollbar
        vsb = ttk.Scrollbar(self.data_tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind select
        self.tree.bind("<<TreeviewSelect>>", self.on_table_select)

        self.last_results = None

    def create_menu(self):
        menubar = tk.Menu(self)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Configuration", command=self.save_config)
        file_menu.add_command(label="Load Configuration", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        self.config(menu=menubar)

    def save_config(self):
        config = {
            "probe": self.probe_panel.get_values(),
            "wedge": self.wedge_panel.get_values(),
            "material": self.mat_panel.get_values(),
            "scan": self.scan_panel.get_values()
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
                
                self.status_var.set(f"Configuration loaded from {os.path.basename(fpath)}")
            except Exception as e:
                messagebox.showerror("Load Error", str(e))

    def get_solver(self):
        # 1. Probe
        pv = self.probe_panel.get_values()
        probe = Probe(
            num_elements=int(pv["num_elements"]),
            pitch=pv["pitch_mm"] * 1e-3,
            frequency=pv["freq_mhz"] * 1e6
        )
        
        # 2. Material
        mv = self.mat_panel.get_values()
        mat = Material(
            velocity_longitudinal=mv["vel_long_ms"],
            velocity_shear=mv["vel_shear_ms"]
        )
        
        # 3. Wedge
        wv = self.wedge_panel.get_values()
        wedge = Wedge(
            angle_degrees=wv["angle_deg"],
            height_at_element1=wv["height_mm"] * 1e-3,
            velocity=wv["velocity_ms"],
            probe_offset_x=wv["offset_mm"] * 1e-3
        )
        
        return DelayLaw(probe, wedge, mat)

    def run_calculation(self):
        try:
            solver = self.get_solver()
            sv = self.scan_panel.get_values()
            
            start = sv["start_angle"]
            end = sv["end_angle"]
            step = sv["step_angle"]
            param_val = sv["param_val"] * 1e-3 # Convert mm to meters
            
            focus_mode = sv["focus_mode"]
            wave_type = sv["wave_type"]
            
            # Determine Velocities for Snell's Law (Beam Steering)
            v_wedge = solver.wedge.velocity
            if wave_type == "Shear" and solver.material.velocity_shear:
                v_mat = solver.material.velocity_shear
            else:
                v_mat = solver.material.velocity_longitudinal # Default / L-wave
            
            # 1. Find Probe Center (Geometric Center of Array)
            elements = solver.wedge.get_transformed_elements(solver.probe)
            center_x = np.mean(elements[:, 0])
            center_z = np.mean(elements[:, 1]) # Should be negative (in wedge)
            
            # Dist to Interface (Vertical)
            # Wedge is at Z < 0, Interface at Z=0.
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
                     # Maybe insert error row or skip
                     # For table, let's insert Error
                     self.tree.insert("", "end", values=(i+1, f"{ang:.1f}", "Err", "Brit", "-", "-"))
                     continue
                 
                 alpha_rad = np.arcsin(sin_alpha)
                 
                 # 3. Beam Entry Point (P_int)
                 x_int = center_x + h_wedge * np.tan(alpha_rad)
                 
                 # 4. Focal Point (F)
                 if focus_mode == "Constant Depth":
                     fz = param_val
                     fx = x_int + fz * np.tan(beta_rad)
                     
                 elif focus_mode == "Vertical Line":
                     fx = param_val
                     if abs(np.tan(beta_rad)) < 1e-9:
                         fz = 1e6 
                     else:
                         fz = (fx - x_int) / np.tan(beta_rad)
                         
                 else: # Constant Sound Path
                     R = param_val
                     fx = x_int + R * np.sin(beta_rad)
                     fz = R * np.cos(beta_rad)
                 
                 if fz < 0:
                     self.tree.insert("", "end", values=(i+1, f"{ang:.1f}", "Err", "Z<0", "-", "-"))
                     continue

                 law = solver.calculate_law(fx, fz, wave_type=wave_type)
                 delays_us = law['delays'] * 1e6
                 
                 res_entry = {
                     'angle': ang,
                     'fx': fx,
                     'fz': fz,
                     'delays_us': delays_us,
                     'velocity_used': law['velocity_used']
                 }
                 results.append(res_entry)
                 focal_points.append((fx, fz))
                 
                 min_d = np.min(delays_us)
                 max_d = np.max(delays_us)
                 
                 self.tree.insert("", "end", values=(i+1, f"{ang:.1f}", f"{fx*1000:.2f}", f"{fz*1000:.2f}", f"{min_d:.2f}", f"{max_d:.2f}"), tags=(len(results)-1,))

            self.last_results = results
            
            # Update Plots
            if focal_points:
                global_max_delay = 0.0
                if results:
                    # results stores 'delays_us'
                    all_delays = [r['delays_us'] for r in results]
                    flat = np.concatenate(all_delays)
                    global_max_delay = np.max(flat)
                
                self.plot_tab.update_plot(solver, focal_points, wave_type)
                self.hist_tab.update_plot(solver, focal_points, wave_type, global_max_delay=global_max_delay)
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
        # Get index from tags
        tags = self.tree.item(item, 'tags')
        if tags:
            try:
                idx = int(tags[0])
                # Update Both Plot Sliders
                self.plot_tab.slider.set(idx)
                self.plot_tab.on_slider_change(idx)
                
                self.hist_tab.slider.set(idx)
                self.hist_tab.on_slider_change(idx)
            except:
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
                
                # Add setup info in manual header lines? Or columns?
                # Let's keep columnar format but maybe add velocity used
                header = ['LawID', 'Angle_Deg', 'Fx_mm', 'Fz_mm', 'Velocity_m_s'] + [f'El_{i+1}_us' for i in range(num_els)]
                writer.writerow(header)
                
                for i, res in enumerate(self.last_results):
                    row = [i+1, res['angle'], res['fx']*1000, res['fz']*1000, res['velocity_used']]
                    row.extend(res['delays_us'])
                    writer.writerow(row)
            
            messagebox.showinfo("Success", f"Exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    app = App()
    app.mainloop()
