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
        params = [
            ("num_elements", 16, "Num Elements:"),
            ("pitch_mm", 0.6, "Pitch (mm):"),
            ("freq_mhz", 5.0, "Frequency (MHz):")
        ]
        super().__init__(parent, "Probe Settings", params)

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

        # Standard Params
        self.add_entry("angle_deg", 36.0, "Wedge Angle (deg):")
        self.add_entry("height_mm", 15.0, "Height @ El.1 (mm):")
        self.vel_var = self.add_entry("velocity_ms", 2330.0, "Velocity (m/s):")
        self.add_entry("offset_mm", 0.0, "Probe Offset X (mm):")

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
        
        # Standard Params
        # Start/End/Step
        for key, val, txt in [("start_angle", 40.0, "Start Angle (deg):"), 
                              ("end_angle", 70.0, "End Angle (deg):"), 
                              ("step_angle", 1.0, "Step (deg):")]:
            ttk.Label(self, text=txt).grid(row=row, column=0, sticky="e", padx=5, pady=2)
            var = tk.DoubleVar(value=val)
            ttk.Entry(self, textvariable=var, width=10).grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.entries[key] = var
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
        elif mode == "Vertical Line":
            self.lbl_focus.config(text="Target X (Global, mm):")
        elif mode == "Constant Sound Path":
            self.lbl_focus.config(text="Focal Distance (mm):")
    
    def get_values(self):
        vals = {key: var.get() for key, var in self.entries.items()}
        vals["focus_mode"] = self.focus_mode.get()
        vals["wave_type"] = self.wave_type.get()
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
