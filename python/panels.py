import tkinter as tk
from tkinter import ttk
import json
import os

def load_materials():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "materials.json")
        with open(json_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load materials.json: {e}")
        return {"components": [], "wedges": []}

MATERIALS = load_materials()

class ParameterPanel(ttk.LabelFrame):
    """
    Base class for a panel of parameters.
    """
    def __init__(self, parent, title, params):
        super().__init__(parent, text=title, padding=10)
        self.entries = {}
        self.row_idx = 0
        
        for key, default_val, label_text in params:
            self.add_entry(key, default_val, label_text)

    def add_entry(self, key, default_val, label_text):
        lbl = ttk.Label(self, text=label_text)
        lbl.grid(row=self.row_idx, column=0, sticky="e", padx=5, pady=2)
        
        var = tk.DoubleVar(value=default_val)
        entry = ttk.Entry(self, textvariable=var, width=10)
        entry.grid(row=self.row_idx, column=1, sticky="w", padx=5, pady=2)
        
        self.entries[key] = var
        self.row_idx += 1
        return var # Return var for robust access if needed

    def get_values(self):
        return {key: var.get() for key, var in self.entries.items()}

    def set_values(self, values):
        """
        Updates the panel variables with values from a dictionary.
        Keys in `values` that match `self.entries` will be updated.
        """
        for key, val in values.items():
            if key in self.entries:
                try:
                    self.entries[key].set(val)
                except Exception as e:
                    print(f"Error setting {key}: {e}")

class ProbePanel(ParameterPanel):
    def __init__(self, parent):
        super().__init__(parent, "Probe Settings", [])
        
        # Probe Type Combobox
        ttk.Label(self, text="Probe Type:").grid(row=self.row_idx, column=0, sticky="e", padx=5, pady=2)
        self.probe_type_var = tk.StringVar(value="Linear")
        self.cb_type = ttk.Combobox(self, textvariable=self.probe_type_var, 
                                    values=["Linear", "Matrix", "Dual Linear", "Dual Matrix"], 
                                    state="readonly", width=15)
        self.cb_type.grid(row=self.row_idx, column=1, sticky="w", padx=5, pady=2)
        self.cb_type.bind("<<ComboboxSelected>>", self.on_type_changed)
        self.row_idx += 1
        
        # Store references to widgets for showing/hiding
        self.rows = {}
        
        # Params definition
        params = [
            ("num_elements", 16, "Primary Elements (X):"),
            ("pitch_mm", 0.5, "Primary Pitch (mm):"),
            ("num_elements_y", 1, "Passive Elements (Y):"),
            ("pitch_y_mm", 0.0, "Passive Pitch (mm):"),
            ("freq_mhz", 5.0, "Frequency (MHz):")
        ]
        
        for key, default_val, label_text in params:
            lbl = ttk.Label(self, text=label_text)
            lbl.grid(row=self.row_idx, column=0, sticky="e", padx=5, pady=2)
            
            var = tk.DoubleVar(value=default_val)
            entry = ttk.Entry(self, textvariable=var, width=10)
            entry.grid(row=self.row_idx, column=1, sticky="w", padx=5, pady=2)
            
            self.entries[key] = var
            self.rows[key] = (lbl, entry)
            self.row_idx += 1
            
        self.on_type_changed() # Trigger initial visibility

    def on_type_changed(self, event=None):
        ptype = self.probe_type_var.get()
        
        # Define which keys are visible by mode
        visible_keys = ["num_elements", "pitch_mm", "freq_mhz"]
        if ptype in ["Matrix", "Dual Matrix"]:
            visible_keys.extend(["num_elements_y", "pitch_y_mm"])
            
        # Apply visibility
        for key, (lbl, entry) in self.rows.items():
            if key in visible_keys:
                lbl.grid()
                entry.grid()
            else:
                lbl.grid_remove()
                entry.grid_remove()
                
        # Emit event for other panels
        self.event_generate("<<ProbeTypeChanged>>")
        
    def get_values(self):
        vals = super().get_values()
        vals["probe_type"] = self.probe_type_var.get()
        return vals
        
    def set_values(self, values):
        super().set_values(values)
        if "probe_type" in values:
            self.probe_type_var.set(values["probe_type"])
            self.on_type_changed()

class WedgePanel(ParameterPanel):
    def __init__(self, parent):
        # Add Material Selector First
        super().__init__(parent, "Wedge Settings", [])
        
        # Material Combo
        ttk.Label(self, text="Material:").grid(row=self.row_idx, column=0, sticky="e", padx=5, pady=2)
        self.mat_var = tk.StringVar(value="Custom")
        wedge_names = [m["name"] for m in MATERIALS.get("wedges", [])]
        cb = ttk.Combobox(self, textvariable=self.mat_var, values=wedge_names, state="readonly", width=15)
        cb.grid(row=self.row_idx, column=1, sticky="w", padx=5, pady=2)
        cb.bind("<<ComboboxSelected>>", self.on_material_select)
        self.row_idx += 1

        # Store references to widgets for showing/hiding
        self.rows = {}

        # Standard Params
        self.add_entry("angle_deg", 36.0, "Wedge Angle (deg):")
        self.add_entry("height_mm", 15.0, "Height @ El.1 (mm):")
        self.vel_var = self.add_entry("velocity_ms", 2330.0, "Velocity (m/s):")
        self.add_entry("offset_mm", 0.0, "Probe Offset X (mm):")

        # Conditional Dual Params
        dual_params = [
            ("array_sep_mm", 0.0, "Array Separation (mm):"),
            ("roof_angle_deg", 0.0, "Roof Angle (deg):")
        ]
        for key, default_val, label_text in dual_params:
            lbl = ttk.Label(self, text=label_text)
            lbl.grid(row=self.row_idx, column=0, sticky="e", padx=5, pady=2)
            var = tk.DoubleVar(value=default_val)
            entry = ttk.Entry(self, textvariable=var, width=10)
            entry.grid(row=self.row_idx, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = var
            self.rows[key] = (lbl, entry)
            self.row_idx += 1
            
        # Hide dual params initially
        for lbl, entry in self.rows.values():
            lbl.grid_remove()
            entry.grid_remove()

    def update_visibility(self, probe_type):
        is_dual = probe_type in ["Dual Linear", "Dual Matrix"]
        for key, (lbl, entry) in self.rows.items():
            if is_dual:
                lbl.grid()
                entry.grid()
            else:
                lbl.grid_remove()
                entry.grid_remove()

    def on_material_select(self, event):
        name = self.mat_var.get()
        for m in MATERIALS.get("wedges", []):
            if m["name"] == name:
                self.vel_var.set(m["vl"])
                break

class MaterialPanel(ParameterPanel):
    def __init__(self, parent):
        super().__init__(parent, "Component Settings", [])
        
        # Material Combo
        ttk.Label(self, text="Material:").grid(row=self.row_idx, column=0, sticky="e", padx=5, pady=2)
        self.mat_var = tk.StringVar(value="Custom")
        comp_names = [m["name"] for m in MATERIALS.get("components", [])]
        cb = ttk.Combobox(self, textvariable=self.mat_var, values=comp_names, state="readonly", width=15)
        cb.grid(row=self.row_idx, column=1, sticky="w", padx=5, pady=2)
        cb.bind("<<ComboboxSelected>>", self.on_material_select)
        self.row_idx += 1

        self.vl_var = self.add_entry("vel_long_ms", 5920.0, "L-Wave Vel (m/s):")
        self.vs_var = self.add_entry("vel_shear_ms", 3240.0, "S-Wave Vel (m/s):")

    def on_material_select(self, event):
        name = self.mat_var.get()
        for m in MATERIALS.get("components", []):
            if m["name"] == name:
                self.vl_var.set(m["vl"])
                self.vs_var.set(m["vs"])
                break

class ScanPanel(ttk.LabelFrame):
    def __init__(self, parent):
        super().__init__(parent, text="Scan Settings", padding=10)
        self.entries = {}
        row = 0
        
        # Focus Mode (Moved to top for visibility)
        ttk.Label(self, text="Focus Type:").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.focus_mode = tk.StringVar(value="Constant Depth")
        cb_focus = ttk.Combobox(self, textvariable=self.focus_mode, values=["Constant Depth", "Vertical Line", "Constant Sound Path"], state="readonly", width=18)
        cb_focus.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        cb_focus.bind("<<ComboboxSelected>>", self.update_focus_label)
        row += 1

        # Wave Type
        ttk.Label(self, text="Wave Type:").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.wave_type = tk.StringVar(value="Longitudinal")
        cb_wave = ttk.Combobox(self, textvariable=self.wave_type, values=["Longitudinal", "Shear"], state="readonly", width=18)
        cb_wave.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        self.rows = {}
        
        # Standard Params
        # Start/End/Step Angle
        for key, val, txt in [("start_angle", 40.0, "Start Angle (deg):"), 
                              ("end_angle", 70.0, "End Angle (deg):"), 
                              ("step_angle", 1.0, "Step (deg):")]:
            lbl = ttk.Label(self, text=txt)
            lbl.grid(row=row, column=0, sticky="e", padx=5, pady=2)
            var = tk.DoubleVar(value=val)
            entry = ttk.Entry(self, textvariable=var, width=10)
            entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = var
            row += 1

        # Skew Params (Matrix / Dual Matrix only)
        for key, val, txt in [("start_skew", 0.0, "Start Skew (deg):"),
                              ("end_skew", 0.0, "End Skew (deg):"),
                              ("step_skew", 1.0, "Skew Step (deg):")]:
            lbl = ttk.Label(self, text=txt)
            lbl.grid(row=row, column=0, sticky="e", padx=5, pady=2)
            var = tk.DoubleVar(value=val)
            entry = ttk.Entry(self, textvariable=var, width=10)
            entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = var
            self.rows[key] = (lbl, entry)
            row += 1
            
        # Hide skew params initially
        for lbl, entry in self.rows.values():
            lbl.grid_remove()
            entry.grid_remove()
            
        # Y Focus Settings
        self.lbl_y_focus = ttk.Label(self, text="Y Focus Mode:")
        self.lbl_y_focus.grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.y_focus_mode = tk.StringVar(value="Derived from Skew")
        self.cb_y_focus = ttk.Combobox(self, textvariable=self.y_focus_mode, 
                                       values=["Derived from Skew", "Fixed Y", "Y Sweep"], 
                                       state="readonly", width=18)
        self.cb_y_focus.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.cb_y_focus.bind("<<ComboboxSelected>>", self.on_y_mode_changed)
        self.row_y_focus = row
        row += 1
        
        # Y Focus Params
        self.y_rows = {}
        y_params = [
            ("target_y_mm", 0.0, "Target Y (mm):", ["Fixed Y"]),
            ("y_start_mm", 0.0, "Y Start (mm):", ["Y Sweep"]),
            ("y_end_mm", 0.0, "Y End (mm):", ["Y Sweep"]),
            ("y_step_mm", 1.0, "Y Step (mm):", ["Y Sweep"])
        ]
        
        for key, val, txt, active_modes in y_params:
            lbl = ttk.Label(self, text=txt)
            lbl.grid(row=row, column=0, sticky="e", padx=5, pady=2)
            var = tk.DoubleVar(value=val)
            entry = ttk.Entry(self, textvariable=var, width=10)
            entry.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = var
            self.y_rows[key] = (lbl, entry, active_modes)
            row += 1

        # Dynamic Focus Parameter
        self.lbl_focus = ttk.Label(self, text="Target Depth (mm):")
        self.lbl_focus.grid(row=row, column=0, sticky="e", padx=5, pady=2)
        
        self.focus_val = tk.DoubleVar(value=50.0)
        ttk.Entry(self, textvariable=self.focus_val, width=10).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.entries["param_val"] = self.focus_val
        row += 1

    def update_focus_label(self, event=None):
        mode = self.focus_mode.get()
        if mode == "Constant Depth":
            self.lbl_focus.config(text="Target Depth (mm):")
            # Enable Fixed Y
            self.cb_y_focus.config(values=["Derived from Skew", "Fixed Y", "Y Sweep"])
        elif mode == "Vertical Line":
            self.lbl_focus.config(text="Target X (Global, mm):")
            self.cb_y_focus.config(values=["Derived from Skew", "Fixed Y", "Y Sweep"])
        elif mode == "Constant Sound Path":
            self.lbl_focus.config(text="Focal Distance (mm):")
            # Disable Fixed Y (overconstrains sphere)
            self.cb_y_focus.config(values=["Derived from Skew", "Y Sweep"])
            if self.y_focus_mode.get() == "Fixed Y":
                self.y_focus_mode.set("Derived from Skew")
                self.on_y_mode_changed()
                
    def on_y_mode_changed(self, event=None):
        mode = self.y_focus_mode.get()
        # For matrix/dual matrix, toggle sub-fields
        ptype = self.master.probe_type if hasattr(self.master, "probe_type") else "Matrix" # Handled in update_visibility
        
        for key, (lbl, entry, active_modes) in self.y_rows.items():
            if mode in active_modes and self.has_skew:
                lbl.grid()
                entry.grid()
            else:
                lbl.grid_remove()
                entry.grid_remove()
            
    def update_visibility(self, probe_type):
        self.master.probe_type = probe_type
        self.has_skew = probe_type in ["Matrix", "Dual Matrix"]
        
        # Toggle Skew fields
        for key, (lbl, entry) in self.rows.items():
            if self.has_skew:
                lbl.grid()
                entry.grid()
            else:
                lbl.grid_remove()
                entry.grid_remove()
                
                # Toggle Y Focus Combobox
        cb_widgets = [self.cb_y_focus, self.lbl_y_focus]
                
        for w in cb_widgets:
            if self.has_skew:
                w.grid()
            else:
                w.grid_remove()
                
        # Toggle Y Focus Sub-fields
        self.on_y_mode_changed()
    
    def get_values(self):
        vals = {key: var.get() for key, var in self.entries.items()}
        vals["focus_mode"] = self.focus_mode.get()
        vals["wave_type"] = self.wave_type.get()
        vals["y_focus_mode"] = self.y_focus_mode.get()
        return vals

    def set_values(self, values):
        for key, val in values.items():
            if key in self.entries:
                try:
                    self.entries[key].set(val)
                except Exception as e:
                    print(f"Error setting {key}: {e}")
        
        if "focus_mode" in values:
            self.focus_mode.set(values["focus_mode"])
            self.update_focus_label() # Trigger label update
            
        if "wave_type" in values:
            self.wave_type.set(values["wave_type"])

class SubAperturePanel(ttk.LabelFrame):
    """
    Panel for sub-aperture element selection settings.
    """
    def __init__(self, parent):
        super().__init__(parent, text="Sub-Aperture Settings", padding=10)
        self.entries = {}
        self.rows = {}
        row = 0
        
        # Start Element (1-indexed)
        ttk.Label(self, text="Start Element:").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.start_el_var = tk.IntVar(value=1)
        ttk.Entry(self, textvariable=self.start_el_var, width=10).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.entries["start_element"] = self.start_el_var
        row += 1
        
        # Number of Active Elements (0 = All)
        ttk.Label(self, text="Active Elements:").grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.num_active_var = tk.IntVar(value=0)
        entry_active = ttk.Entry(self, textvariable=self.num_active_var, width=10)
        entry_active.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.entries["num_active_elements"] = self.num_active_var
        row += 1
        
        # Hint label
        self.hint_lbl = ttk.Label(self, text="(0 = All elements)", font=("Segoe UI", 8))
        self.hint_lbl.grid(row=row, column=0, columnspan=2, sticky="w", padx=5)
        row += 1
        
        # Element Order (Matrix probes only)
        self.lbl_order = ttk.Label(self, text="Element Order:")
        self.lbl_order.grid(row=row, column=0, sticky="e", padx=5, pady=2)
        self.element_order_var = tk.StringVar(value="Column-first")
        self.cb_order = ttk.Combobox(self, textvariable=self.element_order_var, 
                                      values=["Column-first", "Row-first"], 
                                      state="readonly", width=15)
        self.cb_order.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        self.rows["element_order"] = (self.lbl_order, self.cb_order)
        row += 1
        
        # Hide element order initially (linear probes)
        self.lbl_order.grid_remove()
        self.cb_order.grid_remove()
        
    def update_visibility(self, probe_type):
        """Show/hide Element Order based on probe type."""
        is_matrix = probe_type in ["Matrix", "Dual Matrix"]
        for key, (lbl, widget) in self.rows.items():
            if is_matrix:
                lbl.grid()
                widget.grid()
            else:
                lbl.grid_remove()
                widget.grid_remove()
                
    def get_values(self):
        return {
            "start_element": self.start_el_var.get(),
            "num_active_elements": self.num_active_var.get(),
            "element_order": self.element_order_var.get().lower()
        }
        
    def set_values(self, values):
        if "start_element" in values:
            self.start_el_var.set(int(values["start_element"]))
        if "num_active_elements" in values:
            self.num_active_var.set(int(values["num_active_elements"]))
        if "element_order" in values:
            # Accept either 'column-first' or 'Column-first'
            val = values["element_order"]
            display_val = val.capitalize() if val[0].islower() else val
            # Normalize to title case for combobox
            if display_val.lower() == "column-first":
                self.element_order_var.set("Column-first")
            elif display_val.lower() == "row-first":
                self.element_order_var.set("Row-first")

