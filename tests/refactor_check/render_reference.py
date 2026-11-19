"""Render reference images and the data table text (see README.md). Run at two commits, then compare.py."""
import json, os, sys
src, out, catdir = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, src)
os.makedirs(out, exist_ok=True)
import numpy as np
import matplotlib
from matplotlib.figure import Figure
from tkinter import messagebox
messagebox.showinfo = messagebox.showwarning = lambda *a, **k: None
messagebox.showerror = lambda *a, **k: (_ for _ in ()).throw(RuntimeError(a))
from delay_law import DelayLaw
from material import Material
from probe import create_probe_assembly
from wedge import Wedge
from catalog import Catalog
from scene import draw_projection, draw_scene_3d, draw_aperture_maps

steel = Material(5920, 3240)
wc = Catalog(os.path.join(catdir, "wedges.json")).wedge("evident-SA2-N55S")
outline = wc.outline_global_mm()
setups = {
    "lin_cat": (create_probe_assembly("Linear", 64, 0.75e-3, 2.25e6, start_element=17, num_active_elements=32),
                Wedge(wc.angle_deg, wc.height_at_element1, wc.velocity, wc.probe_offset_x), outline),
    "lin_full": (create_probe_assembly("Linear", 16, 0.6e-3, 5e6), Wedge(36, 0.015, 2330), None),
    "matrix_rf": (create_probe_assembly("Matrix", 8, 1e-3, 5e6, num_elements_y=4, pitch_y=1e-3,
                                        start_element=3, num_active_elements=20, element_order="row-first"),
                  Wedge(20, 0.008, 2330), None),
    "dual_lin": (create_probe_assembly("Dual Linear", 16, 0.5e-3, 5e6, array_separation=8e-3,
                                       start_element=5, num_active_elements=20),
                 Wedge(15, 0.006, 2330, roof_angle_degrees=3), None),
    "dual_mat_contact": (create_probe_assembly("Dual Matrix", 4, 1e-3, 5e6, num_elements_y=2, pitch_y=1e-3,
                                               array_separation=10e-3, start_element=2, num_active_elements=12),
                         Wedge(0, 0.0, 2330), None),
    "flat_delayline": (create_probe_assembly("Linear", 16, 0.6e-3, 5e6), Wedge(0, 0.01, 2330), None),
    "long_toe": (create_probe_assembly("Linear", 8, 0.6e-3, 5e6), Wedge(5, 0.02, 2330), None),
}
for name, (probe, wedge, ol) in setups.items():
    s = DelayLaw(probe, wedge, steel)
    cx, cy, _ = s.aperture_centre()
    fps = [(cx + 0.02, cy + 0.002, 0.03), (cx + 0.03, cy, 0.03), (cx + 0.04, cy - 0.001, 0.025)]
    laws = [s.calculate_law(*fp) for fp in fps]
    get = lambda i: (laws[i]["interface_points"] * 1e3, np.array(fps[i]) * 1e3)
    for dim in (0, 1):
        for show_all, idx in ((False, [1]), (True, [0, 1, 2])):
            fig = Figure(figsize=(6, 4), dpi=80)
            draw_projection(fig.add_subplot(111), s, get, idx, dim, "longitudinal", show_all,
                            component_thickness_mm=40 if show_all else 0.0, outline_mm=ol)
            fig.savefig(f"{out}/{name}_proj{dim}_{int(show_all)}.png")
    fig = Figure(figsize=(6, 5), dpi=80)
    draw_scene_3d(fig.add_subplot(111, projection="3d"), s, get(1), np.array(fps) * 1e3, 1,
                  "longitudinal", component_thickness_mm=40, outline_mm=ol, max_rays=10)
    fig.savefig(f"{out}/{name}_3d.png")
    if probe.num_elements_y > 1:
        fig = Figure(figsize=(6, 4), dpi=80)
        draw_aperture_maps(fig, probe, laws[0]["delays"] * 1e6, title="t")
        fig.savefig(f"{out}/{name}_map.png")

# GUI: focal rules + tabs, several scan modes
import app as appmod
a = appmod.App(); a.withdraw()
cases = {
    "depth_lin": ({"probe_type": "Linear", "num_elements": 16, "pitch_mm": 0.6},
                  {"focus_mode": "Constant Depth", "param_val": 30, "start_angle": 40, "end_angle": 80, "step_angle": 5}),
    "vline_lin": ({"probe_type": "Linear"},
                  {"focus_mode": "Vertical Line", "param_val": 40, "start_angle": -10, "end_angle": 70, "step_angle": 10}),
    "path_lin_shear": ({"probe_type": "Linear"},
                       {"focus_mode": "Constant Sound Path", "param_val": 35, "wave_type": "Shear",
                        "start_angle": 30, "end_angle": 80, "step_angle": 10}),
    "depth_mat_skew": ({"probe_type": "Matrix", "num_elements": 8, "num_elements_y": 4, "pitch_mm": 1, "pitch_y_mm": 1},
                       {"focus_mode": "Constant Depth", "wave_type": "Longitudinal", "param_val": 25, "start_angle": 40,
                        "end_angle": 60, "step_angle": 10, "start_skew": -10, "end_skew": 10, "step_skew": 10,
                        "y_focus_mode": "Derived from Skew"}),
    "vline_mat_fixedy": ({}, {"focus_mode": "Vertical Line", "param_val": 30, "y_focus_mode": "Fixed Y",
                              "target_y_mm": 3}),
    "depth_mat_ysweep": ({}, {"focus_mode": "Constant Depth", "param_val": 25, "y_focus_mode": "Y Sweep",
                              "y_start_mm": -4, "y_end_mm": 4, "y_step_mm": 4}),
    "path_mat_ysweep": ({}, {"focus_mode": "Constant Sound Path", "param_val": 40, "y_focus_mode": "Y Sweep",
                             "y_start_mm": 0, "y_end_mm": 30, "y_step_mm": 10, "start_angle": 30, "end_angle": 70,
                             "step_angle": 20}),
    "dual_sub": ({"probe_type": "Dual Matrix"}, {"focus_mode": "Constant Depth", "param_val": 20,
                                                 "y_focus_mode": "Derived from Skew"}),
}
a.sub_aperture_panel.set_values({"start_element": 1, "num_active_elements": 0})
table = {}
for name, (pv, sv) in cases.items():
    if pv: a.probe_panel.set_values(pv)
    if name == "dual_sub":
        a.wedge_panel.set_values({"array_sep_mm": 10, "roof_angle_deg": 3})
        a.sub_aperture_panel.set_values({"start_element": 3, "num_active_elements": 20, "element_order": "row-first"})
    a.scan_panel.set_values(sv)
    a.run_calculation()
    table[name] = [list(a.tree.item(r, "values")) for r in a.tree.get_children()]
    if a.last_results:
        for tab_name, tab in (("ray", a.plot_tab), ("hist", a.hist_tab), ("3d", a.scene3d_tab)):
            tab.show_law(min(2, len(a.last_results) - 1))
            tab.figure.savefig(f"{out}/gui_{name}_{tab_name}.png", dpi=60)
a.destroy()
json.dump(table, open(f"{out}/table.json", "w"), indent=0)
print("golden written:", len(os.listdir(out)))
