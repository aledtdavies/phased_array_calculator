"""
The calculator's work behind any window: build the solver from panel values, run a sweep into
laws and table rows, write the focal-law CSV, and keep catalogue references with a setup.

Toolkit-free: the Tk window (app.py) and the Qt window (qt_app.py) both call this, so they
calculate, label and export identically. Panel values use the GUI's keys and units (mm, MHz,
degrees, m/s); everything returned in SI unless a key says otherwise.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from delay_law import DelayLaw
from focal_rules import Target, angle_sweep, focal_targets, swept_values
from material import Material
from probe import create_probe_assembly
from wedge import Wedge

# Scan panel focus modes and Y modes (the combobox labels)
FOCUS_CONSTANT_DEPTH = "Constant Depth"
FOCUS_VERTICAL_LINE = "Vertical Line"
FOCUS_CONSTANT_SOUND_PATH = "Constant Sound Path"
Y_MODE_DERIVED_FROM_SKEW = "Derived from Skew"
Y_MODE_FIXED_Y = "Fixed Y"
Y_MODE_Y_SWEEP = "Y Sweep"
PROBE_TYPES = ["Linear", "Matrix", "Dual Linear", "Dual Matrix"]
MATRIX_PROBE_TYPES = ["Matrix", "Dual Matrix"]
DUAL_PROBE_TYPES = ["Dual Linear", "Dual Matrix"]

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
TABLE_COLUMNS = ("ID", "Angle", "Skew", "Fx", "Fy", "Fz", "MinD", "MaxD")
TABLE_HEADINGS = ("#", "Angle (°)", "Skew (°)", "Fx (mm)", "Fy (mm)", "Fz (mm)",
                  "Min Delay (µs)", "Max Delay (µs)")


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


def build_solver(pv, wv, mv, sav) -> DelayLaw:
    """
    DelayLaw from the probe, wedge, component and sub-aperture panel values. Array separation
    and roof angle apply to dual probes only: the panels hide them for single arrays, so a
    value left there from a dual setup is not applied unseen (as the MATLAB GUI reads them).
    """
    dual = pv.get("probe_type", "Linear") in DUAL_PROBE_TYPES
    probe = create_probe_assembly(
        probe_type=pv.get("probe_type", "Linear"),
        num_elements=int(pv["num_elements"]),
        pitch=pv["pitch_mm"] * 1e-3,
        freq=pv["freq_mhz"] * 1e6,
        num_elements_y=int(pv.get("num_elements_y", 1)),
        pitch_y=pv.get("pitch_y_mm", 0.0) * 1e-3,
        array_separation=wv.get("array_sep_mm", 0.0) * 1e-3 if dual else 0.0,
        start_element=sav.get("start_element", 1),
        num_active_elements=sav.get("num_active_elements", 0),
        element_order=sav.get("element_order", "column-first"))
    mat = Material(velocity_longitudinal=mv["vel_long_ms"], velocity_shear=mv["vel_shear_ms"])
    wedge = Wedge(angle_degrees=wv["angle_deg"], height_at_element1=wv["height_mm"] * 1e-3,
                  velocity=wv["velocity_ms"], probe_offset_x=wv["offset_mm"] * 1e-3,
                  roof_angle_degrees=wv.get("roof_angle_deg", 0.0) if dual else 0.0)
    return DelayLaw(probe, wedge, mat)


@dataclass
class Calculation:
    """One sweep's laws (results), table rows and what the views need."""
    solver: DelayLaw
    results: list            # dicts: angle, skew, fx, fy, fz (m), delays_us, tof_us, velocity_used, interface_points
    rows: list               # (values tuple for the table, law index or None for a refused law)
    focal_points: list       # (x, y, z) m per law
    is_matrix: bool
    wave_type: str           # as the scan panel gives it ('Longitudinal' / 'Shear')
    global_max_delay: Optional[float]


def scan_targets(solver, sv, probe_type):
    """Focal targets for the scan panel values (see focal_rules.focal_targets)."""
    is_matrix = probe_type in MATRIX_PROBE_TYPES
    if is_matrix:
        s_start, s_end, s_step = sv.get("start_skew", 0.0), sv.get("end_skew", 0.0), sv.get("step_skew", 1.0)
    else:
        s_start, s_end, s_step = 0.0, 0.0, 1.0
    skew_angles = swept_values(s_start, s_end, s_step, s_start)
    y_mode = Y_MODE_NAMES[sv.get("y_focus_mode", Y_MODE_DERIVED_FROM_SKEW)] if is_matrix else "from-skew"
    y_values = None
    if y_mode == "fixed":
        y_values = [sv.get("target_y_mm", 0.0) * 1e-3]
    elif y_mode == "sweep":
        y_s = sv.get("y_start_mm", 0.0) * 1e-3
        y_e = sv.get("y_end_mm", 0.0) * 1e-3
        y_st = sv.get("y_step_mm", 1.0) * 1e-3
        y_values = swept_values(y_s, y_e, y_st, y_s).tolist()
    return focal_targets(solver, FOCUS_MODE_NAMES[sv["focus_mode"]], sv["param_val"] * 1e-3,
                         angle_sweep(sv["start_angle"], sv["end_angle"], sv["step_angle"]),
                         skew_angles, wave=sv["wave_type"].lower(), y_mode=y_mode,
                         y_values=y_values)


def refused_row(refused):
    """Table values of a refused law: no law number, the reason in the Fx/Fy/Fz columns."""
    skew = "-" if refused.skew_deg is None else f"{refused.skew_deg:.1f}"
    fx_t, fy_t, fz_t = REFUSED_TEXT[refused.reason]
    return ("-", f"{refused.angle_deg:.1f}", skew, fx_t, fy_t, fz_t, "-", "-")


def law_result(solver, point, wave_type, angle=None, skew=None):
    """One law for focus point (m) as a result dict (the fields calculate() gives each law)."""
    law = solver.calculate_law(point[0], point[1], point[2], wave_type=wave_type)
    return {'angle': angle, 'skew': skew, 'fx': point[0], 'fy': point[1], 'fz': point[2],
            'delays_us': law['delays'] * 1e6, 'tof_us': law['tof'] * 1e6,
            'velocity_used': law['velocity_used'], 'interface_points': law['interface_points']}


def fan_key(t, focus_mode, y_mode):
    """
    Which coverage fan a law belongs to (laws of one fan differ only in refracted angle):
    a normal or fixed-Y sweep, by skew; a constant-depth or vertical-line Y sweep, by skew and
    Y target; a sound-path Y sweep (skew solved per Y), by Y target.
    """
    if y_mode == "sweep" and focus_mode == "sound-path":
        return ("y", round(t.y, 12))
    if y_mode == "sweep":
        return ("skew-y", round(t.skew_deg, 9), round(t.y, 12))
    return ("skew", round(t.skew_deg, 9))


def calculate(solver, sv, probe_type) -> Calculation:
    """Every law of the scan, in sweep order, with its table row."""
    wave_type = sv["wave_type"]
    focus_mode = FOCUS_MODE_NAMES[sv["focus_mode"]]
    y_mode = (Y_MODE_NAMES[sv.get("y_focus_mode", Y_MODE_DERIVED_FROM_SKEW)]
              if probe_type in MATRIX_PROBE_TYPES else "from-skew")
    results, rows, focal_points = [], [], []
    for t in scan_targets(solver, sv, probe_type):
        if not isinstance(t, Target):
            rows.append((refused_row(t), None))
            continue
        results.append(law_result(solver, t.point, wave_type, t.angle_deg, t.skew_deg))
        results[-1]['fan'] = fan_key(t, focus_mode, y_mode)
        delays_us = results[-1]['delays_us']
        idx = len(results) - 1
        focal_points.append(t.point)
        # Inactive elements are NaN
        rows.append(((idx + 1, f"{t.angle_deg:.1f}", f"{t.skew_deg:.1f}",
                      f"{t.x*1000:.2f}", f"{t.y*1000:.2f}", f"{t.z*1000:.2f}",
                      f"{np.nanmin(delays_us):.2f}", f"{np.nanmax(delays_us):.2f}"), idx))
    gmax = max(np.nanmax(r['delays_us']) for r in results) if results else None
    return Calculation(solver, results, rows, focal_points, probe_type in MATRIX_PROBE_TYPES,
                       wave_type, gmax)


def write_laws_csv(path, results):
    """The focal-law CSV: one row per law, element delays in µs (NaN for inactive elements)."""
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        num_els = len(results[0]['delays_us'])
        writer.writerow(['LawID', 'Angle_Deg', 'Skew_Deg', 'Fx_mm', 'Fy_mm', 'Fz_mm', 'Velocity_m_s']
                        + [f'El_{i+1}_us' for i in range(num_els)])
        for i, res in enumerate(results):
            row = [i + 1, res['angle'], res.get('skew', 0.0), res['fx'] * 1000,
                   res.get('fy', 0.0) * 1000, res['fz'] * 1000, res['velocity_used']]
            row.extend(res['delays_us'])
            writer.writerow(row)


@dataclass
class CatalogLinks:
    """
    Catalogue references of the current setup. An asset applied from a catalogue keeps its
    reference while its panel values are unchanged ('values_match'). References loaded with a
    saved configuration travel on, and turn values_match false once the loaded values are edited.
    """
    assets: dict = field(default_factory=dict)          # kind -> ProbeAsset / WedgeAsset
    loaded_refs: Optional[dict] = None
    loaded_panel_values: dict = field(default_factory=dict)

    def apply(self, kind, asset):
        self.assets[kind] = asset
        if self.loaded_refs:
            self.loaded_refs.pop(kind, None)

    def loaded(self, config, panel_values):
        """After a configuration is applied: panel_values = {'probe': ..., 'wedge': ...} as loaded."""
        self.assets = {}
        self.loaded_refs = config.get("catalog")
        self.loaded_panel_values = panel_values

    def status(self, current):
        """current = {'probe': probe panel values, 'wedge': wedge panel values}."""
        refs = {}
        for kind, asset in self.assets.items():
            refs[kind] = dict(asset.ref.as_dict(),
                              values_match=panel_matches(asset.panel_values(), current[kind]),
                              missing=list(asset.missing), notes=list(asset.notes))
        for kind, ref in (self.loaded_refs or {}).items():
            if kind in refs or kind not in current:
                continue
            ref = dict(ref)
            snapshot = self.loaded_panel_values.get(kind)
            ref["values_match"] = (bool(ref.get("values_match")) and snapshot is not None
                                   and panel_matches(snapshot, current[kind]))
            refs[kind] = ref
        return refs

    def element_size_m(self, probe_values):
        """(element width, elevation) in metres from the catalogue probe while the probe panel
        still matches it; (None, None) otherwise (the 3D view then draws a schematic size)."""
        asset = self.assets.get("probe")
        if asset is None or not panel_matches(asset.panel_values(), probe_values):
            return None, None
        return asset.element_width, asset.elevation

    def wedge_outline_mm(self, wedge_values, probe_type="Linear"):
        """
        The catalogue wedge outline (global X-Z, mm) while the wedge panel still matches it and
        no roof tilts the arrays (a roof applies to dual probes only, see build_solver).
        """
        asset = self.assets.get("wedge")
        if asset is None or asset.outline is None:
            return None
        roof = wedge_values.get("roof_angle_deg", 0.0) if probe_type in DUAL_PROBE_TYPES else 0.0
        if not panel_matches(asset.panel_values(), wedge_values) or roof:
            return None
        return asset.outline_global_mm()


def asset_message(kind, asset):
    """The text shown after a catalogue entry is applied."""
    lines = [f"{kind.capitalize()}: {asset.ref.label()}"]
    if asset.ref.stamp == "changed":
        lines.append("WARNING: the entry's values no longer give its stamped hash; "
                     "buildFE treats it as a different asset.")
    if asset.missing:
        lines.append("Not in the catalogue, enter by hand: " + ", ".join(asset.missing))
    return "\n".join(lines + list(asset.notes))
