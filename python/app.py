import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
import csv
import json
import numpy as np

from material import Material
from probe import Probe, create_probe_assembly
from wedge import Wedge
from delay_law import DelayLaw

from panels import ProbePanel, WedgePanel, MaterialPanel, ScanPanel, SubAperturePanel
from plotting import PlottingPanel, DelayHistogramPanel, Scene3DPanel
from catalog import Catalog, CatalogError, default_catalog_dir
from focal_rules import Target, angle_sweep, focal_targets, swept_values

# Scan Panel focus modes (must match ScanPanel's combobox values)
FOCUS_CONSTANT_DEPTH = "Constant Depth"
FOCUS_VERTICAL_LINE = "Vertical Line"
FOCUS_CONSTANT_SOUND_PATH = "Constant Sound Path"

# Scan Panel Y-focus modes (must match ScanPanel's combobox values)
Y_MODE_DERIVED_FROM_SKEW = "Derived from Skew"
Y_MODE_FIXED_Y = "Fixed Y"
Y_MODE_Y_SWEEP = "Y Sweep"

MATRIX_PROBE_TYPES = ["Matrix", "Dual Matrix"]


# GUI labels -> focal_rules names
FOCUS_MODE_NAMES = {FOCUS_CONSTANT_DEPTH: "constant-depth",
                    FOCUS_VERTICAL_LINE: "vertical-line",
                    FOCUS_CONSTANT_SOUND_PATH: "sound-path"}
Y_MODE_NAMES = {Y_MODE_DERIVED_FROM_SKEW: "from-skew", Y_MODE_FIXED_Y: "fixed",
                Y_MODE_Y_SWEEP: "sweep"}
# Table text for a refused law: (Fx, Fy, Fz) columns
REFUSED_TEXT = {"critical angle": ("Err", "Crit", "-"),
                "focus not below surface": ("Err", "-", "Z<0"),
                "beam parallel to line": ("Err", "Parallel", "-"),
                "Y out of reach": ("Err", "Y out", "of reach")}


def panel_matches(want, have):
    """True when every catalogue-given panel value is still in the panel (numbers to 1e-9 relative)."""
    for k, v in want.items():
        if k not in have:
            return False
        if isinstance(v, str):
            if have[k] != v:
                return False
        elif abs(float(have[k]) - float(v)) > 1e-9 * max(1.0, abs(float(v))):
            return False
    return True


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

        # Only capture the mouse wheel while the pointer is over this widget,
        # so it doesn't hijack scrolling on other widgets (Treeview, plot
        # canvases) elsewhere in the app.
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")

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
        
        # Tab 3: Delays (bar chart, or aperture map for matrix probes)
        self.hist_tab = DelayHistogramPanel(self.notebook)
        self.notebook.add(self.hist_tab, text="Delays")

        # Tab 4: 3D scene
        self.scene3d_tab = Scene3DPanel(self.notebook)
        self.notebook.add(self.scene3d_tab, text="3D View")

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
        # Catalogue assets applied to the panels: {'probe': ProbeAsset, 'wedge': WedgeAsset}
        self.catalog_assets = {}
        self.loaded_catalog_refs = None
        self.loaded_panel_values = {}

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
        file_menu.add_command(label="Load Probe from Catalogue...",
                              command=lambda: self.load_from_catalog("probe"))
        file_menu.add_command(label="Load Wedge from Catalogue...",
                              command=lambda: self.load_from_catalog("wedge"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        self.config(menu=menubar)

    def config_dict(self):
        """The full setup as saved: panel values and any catalogue references."""
        config = {
            "probe": self.probe_panel.get_values(),
            "wedge": self.wedge_panel.get_values(),
            "material": self.mat_panel.get_values(),
            "scan": self.scan_panel.get_values(),
            "sub_aperture": self.sub_aperture_panel.get_values()
        }
        refs = self.catalog_status()
        if refs:
            config["catalog"] = refs
        return config

    def apply_config(self, config):
        """Set the panels from a saved configuration (see config_dict)."""
        if "probe" in config: self.probe_panel.set_values(config["probe"])
        if "wedge" in config: self.wedge_panel.set_values(config["wedge"])
        if "material" in config: self.mat_panel.set_values(config["material"])
        if "scan" in config: self.scan_panel.set_values(config["scan"])
        if "sub_aperture" in config: self.sub_aperture_panel.set_values(config["sub_aperture"])
        # Catalogue references are not re-read from their files: the loaded
        # values stand on their own, and the references travel on with the
        # configuration when it is saved again. The panel values as loaded are
        # kept so that a later edit makes a restored reference's values_match false.
        self.catalog_assets = {}
        self.loaded_catalog_refs = config.get("catalog")
        self.loaded_panel_values = {"probe": self.probe_panel.get_values(),
                                    "wedge": self.wedge_panel.get_values()}

    def save_config(self):
        config = self.config_dict()

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
                self.apply_config(config)
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

    def load_from_catalog(self, kind):
        """Fill the probe or wedge panel from a buildFE or nde-knowledge catalogue entry."""
        from catalog_dialog import CatalogPicker
        fpath = filedialog.askopenfilename(
            title=f"Open a {kind} catalogue (buildFE catalog/{kind}s.json or nde-knowledge export)",
            initialdir=default_catalog_dir() or os.getcwd(),
            filetypes=[("JSON catalogue", "*.json"), ("All Files", "*.*")])
        if not fpath:
            return
        try:
            cat = Catalog(fpath)
            if not cat.entries(kind):
                raise CatalogError(f"{os.path.basename(fpath)} has no {kind}s")
            picker = CatalogPicker(self, cat, kind)
            self.wait_window(picker)
            if picker.selected is None:
                return
            asset = cat.probe(picker.selected) if kind == "probe" else cat.wedge(picker.selected)
        except CatalogError as e:
            messagebox.showerror("Catalogue", str(e))
            return

        if kind == "probe":
            self.probe_panel.set_values(asset.panel_values())
        else:
            self.wedge_panel.set_values(asset.panel_values())
            self.wedge_panel.mat_var.set("Custom")
        self.catalog_assets[kind] = asset
        if self.loaded_catalog_refs:
            self.loaded_catalog_refs.pop(kind, None)

        lines = [f"{kind.capitalize()}: {asset.ref.label()}"]
        if asset.ref.stamp == "changed":
            lines.append("WARNING: the entry's values no longer give its stamped hash; "
                         "buildFE treats it as a different asset.")
        if asset.missing:
            lines.append("Not in the catalogue, enter by hand: " + ", ".join(asset.missing))
        lines += asset.notes
        self.status_var.set(f"{kind.capitalize()} from catalogue: {asset.ref.id}")
        messagebox.showinfo("Catalogue entry applied", "\n".join(lines))

    def catalog_status(self):
        """
        Catalogue references for the current setup: each asset's reference and
        whether the panels still hold its values ('values_match'). References
        loaded with a saved configuration are passed through unchanged.
        """
        refs = {}
        current = {"probe": self.probe_panel.get_values(), "wedge": self.wedge_panel.get_values()}
        for kind, asset in self.catalog_assets.items():
            refs[kind] = dict(asset.ref.as_dict(),
                              values_match=panel_matches(asset.panel_values(), current[kind]),
                              missing=list(asset.missing), notes=list(asset.notes))
        for kind, ref in (self.loaded_catalog_refs or {}).items():
            if kind in refs or kind not in current:
                continue
            ref = dict(ref)
            snapshot = self.loaded_panel_values.get(kind)
            ref["values_match"] = bool(ref.get("values_match")) and snapshot is not None                 and panel_matches(snapshot, current[kind])
            refs[kind] = ref
        return refs

    def wedge_outline_mm(self):
        """The catalogue wedge outline (global X-Z, mm) while the wedge panel still matches it."""
        asset = self.catalog_assets.get("wedge")
        if asset is None or asset.outline is None:
            return None
        wv = self.wedge_panel.get_values()
        if not panel_matches(asset.panel_values(), wv) or wv.get("roof_angle_deg", 0.0):
            return None
        return asset.outline_global_mm()

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

    def _insert_refused_row(self, refused):
        """A law the focal rule refused: no law number, its reason in the Fx/Fy/Fz columns."""
        skew = "-" if refused.skew_deg is None else f"{refused.skew_deg:.1f}"
        fx_t, fy_t, fz_t = REFUSED_TEXT[refused.reason]
        self.tree.insert("", "end", values=("-", f"{refused.angle_deg:.1f}", skew, fx_t, fy_t, fz_t, "-", "-"))

    def run_calculation(self):
        try:
            solver = self.get_solver()
            sv = self.scan_panel.get_values()

            start = sv["start_angle"]
            end = sv["end_angle"]
            step = sv["step_angle"]

            # Determine skew angles based on probe type
            ptype = self.probe_panel.get_values().get("probe_type", "Linear")
            is_matrix = ptype in MATRIX_PROBE_TYPES

            if is_matrix:
                s_start = sv.get("start_skew", 0.0)
                s_end = sv.get("end_skew", 0.0)
                s_step = sv.get("step_skew", 1.0)
            else:
                s_start, s_end, s_step = 0.0, 0.0, 1.0
            skew_angles = swept_values(s_start, s_end, s_step, s_start)

            # Y focus (matrix probes only)
            y_mode = Y_MODE_NAMES[sv.get("y_focus_mode", Y_MODE_DERIVED_FROM_SKEW)] if is_matrix else "from-skew"
            y_values = None
            if y_mode == "fixed":
                y_values = [sv.get("target_y_mm", 0.0) * 1e-3]
            elif y_mode == "sweep":
                y_s = sv.get("y_start_mm", 0.0) * 1e-3
                y_e = sv.get("y_end_mm", 0.0) * 1e-3
                y_st = sv.get("y_step_mm", 1.0) * 1e-3
                y_values = swept_values(y_s, y_e, y_st, y_s).tolist()

            wave_type = sv["wave_type"]
            targets = focal_targets(solver, FOCUS_MODE_NAMES[sv["focus_mode"]],
                                    sv["param_val"] * 1e-3, angle_sweep(start, end, step),
                                    skew_angles, wave=wave_type.lower(), y_mode=y_mode,
                                    y_values=y_values)

            results = []
            focal_points = []

            self.status_var.set("Calculating...")
            self.update_idletasks()

            # Clear Tree
            for item in self.tree.get_children():
                self.tree.delete(item)

            for t in targets:
                if not isinstance(t, Target):
                    self._insert_refused_row(t)
                    continue
                law = solver.calculate_law(t.x, t.y, t.z, wave_type=wave_type)
                delays_us = law['delays'] * 1e6
                results.append({
                    'angle': t.angle_deg,
                    'skew': t.skew_deg,
                    'fx': t.x,
                    'fy': t.y,
                    'fz': t.z,
                    'delays_us': delays_us,
                    'velocity_used': law['velocity_used'],
                    'interface_points': law['interface_points']
                })
                idx = len(results) - 1
                focal_points.append(t.point)

                # Inactive elements are NaN
                min_d = np.nanmin(delays_us)
                max_d = np.nanmax(delays_us)
                self.tree.insert("", "end", values=(idx+1, f"{t.angle_deg:.1f}", f"{t.skew_deg:.1f}",
                                                    f"{t.x*1000:.2f}", f"{t.y*1000:.2f}", f"{t.z*1000:.2f}",
                                                    f"{min_d:.2f}", f"{max_d:.2f}"), tags=(idx,))

            self.last_results = results
            
            # Update Plots
            if focal_points:
                global_max_delay = 0.0
                if results:
                    # results stores 'delays_us'
                    global_max_delay = max(np.nanmax(r['delays_us']) for r in results)
                
                thickness_mm = self.mat_panel.get_values().get("thickness_mm", 0.0)
                outline_mm = self.wedge_outline_mm()
                self.plot_tab.update_plot(solver, focal_points, wave_type, results=results, is_matrix=is_matrix,
                                          component_thickness_mm=thickness_mm, outline_mm=outline_mm)
                self.scene3d_tab.update_plot(solver, focal_points, wave_type, results=results,
                                             is_matrix=is_matrix, component_thickness_mm=thickness_mm,
                                             outline_mm=outline_mm)
                self.hist_tab.update_plot(solver, focal_points, wave_type, global_max_delay=global_max_delay, results=results, is_matrix=is_matrix)
            else:
                # No laws: no tab may keep showing (or stepping through) the previous set.
                for tab in (self.plot_tab, self.hist_tab, self.scene3d_tab):
                    tab.clear_laws()
            
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
        
        # Valid law rows carry their law index as a tag; error rows carry none.
        tags = self.tree.item(selected[0], 'tags')
        if not tags:
            return
        idx = int(tags[0])
        for tab in (self.plot_tab, self.hist_tab, self.scene3d_tab):
            tab.show_law(idx)

    def export_csv(self):
        if not self.last_results:
            messagebox.showinfo("Export", "No data to export.")
            return

        fpath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="focal_laws_gui.csv",
            filetypes=[("CSV File", "*.csv"), ("All Files", "*.*")],
            title="Export Focal Laws"
        )
        if not fpath:
            return

        try:
            with open(fpath, 'w', newline='') as f:
                writer = csv.writer(f)

                # Header
                num_els = len(self.last_results[0]['delays_us'])

                header = ['LawID', 'Angle_Deg', 'Skew_Deg', 'Fx_mm', 'Fy_mm', 'Fz_mm', 'Velocity_m_s'] + [f'El_{i+1}_us' for i in range(num_els)]
                writer.writerow(header)

                for i, res in enumerate(self.last_results):
                    row = [i+1, res['angle'], res.get('skew', 0.0), res['fx']*1000, res.get('fy', 0.0)*1000, res['fz']*1000, res['velocity_used']]
                    row.extend(res['delays_us'])
                    writer.writerow(row)

            self.status_var.set(f"Exported to {os.path.basename(fpath)}")
            messagebox.showinfo("Success", f"Exported to {os.path.basename(fpath)}")

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    app = App()
    app.mainloop()
