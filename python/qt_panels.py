"""
Qt input panels: probe, wedge, component, scan and sub-aperture settings.

Same keys, units, defaults and visibility rules as the Tk panels (panels.py), so a configuration
saved by either window loads in the other. Numbers are typed text, read exactly (no spin-box
rounding); a field that is not a number is refused by name when its panel is read.
"""
from __future__ import annotations

import json
import os

from qtpy import QtCore, QtGui, QtWidgets

from session import (DUAL_PROBE_TYPES, FOCUS_CONSTANT_DEPTH, FOCUS_CONSTANT_SOUND_PATH,
                     FOCUS_VERTICAL_LINE, MATRIX_PROBE_TYPES, PROBE_TYPES,
                     Y_MODE_DERIVED_FROM_SKEW, Y_MODE_FIXED_Y, Y_MODE_Y_SWEEP)


def load_materials():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "materials.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


MATERIALS = load_materials()


class NumberField(QtWidgets.QLineEdit):
    """A number typed as text; value() is exactly what was typed."""

    def __init__(self, value, label, integer=False):
        super().__init__()
        self.label = label.rstrip(":")
        self.integer = integer
        v = QtGui.QIntValidator() if integer else QtGui.QDoubleValidator()
        if not integer:
            v.setNotation(QtGui.QDoubleValidator.ScientificNotation)
            v.setLocale(QtCore.QLocale.c())
        self.setValidator(v)
        self.setMaximumWidth(110)
        self.setValue(value)

    def value(self):
        text = self.text().strip()
        try:
            return int(text) if self.integer else float(text)
        except ValueError:
            raise ValueError(f"{self.label}: '{text}' is not a number") from None

    def setValue(self, v):
        if self.integer:
            self.setText(str(int(v)))
        else:
            v = float(v)
            self.setText(str(int(v)) if v.is_integer() and abs(v) < 1e15 else repr(v))


class Panel(QtWidgets.QGroupBox):
    """A titled form of NumberFields and combo boxes, with rows that can be hidden."""

    def __init__(self, title):
        super().__init__(title)
        self.form = QtWidgets.QFormLayout(self)
        self.form.setLabelAlignment(QtCore.Qt.AlignRight)
        self.entries = {}       # key -> NumberField

    def add_number(self, key, default, label, integer=False):
        field = NumberField(default, label, integer)
        self.form.addRow(label, field)
        self.entries[key] = field
        return field

    def add_combo(self, label, items, current=None):
        c = QtWidgets.QComboBox()
        c.addItems(items)
        if current is not None:
            c.setCurrentText(current)
        self.form.addRow(label, c)
        return c

    def set_row_visible(self, widget, visible):
        self.form.setRowVisible(widget, visible)

    def get_values(self):
        return {k: f.value() for k, f in self.entries.items()}

    def set_values(self, values):
        for k, v in values.items():
            if k in self.entries:
                self.entries[k].setValue(v)


class ProbePanel(Panel):
    probe_type_changed = QtCore.Signal(str)

    def __init__(self):
        super().__init__("Probe Settings")
        self.type_combo = self.add_combo("Probe Type:", PROBE_TYPES, "Linear")
        self.add_number("num_elements", 16, "Primary Elements (X):")
        self.add_number("pitch_mm", 0.5, "Primary Pitch (mm):")
        self.add_number("num_elements_y", 1, "Passive Elements (Y):")
        self.add_number("pitch_y_mm", 0.0, "Passive Pitch (mm):")
        self.add_number("freq_mhz", 5.0, "Frequency (MHz):")
        self.type_combo.currentTextChanged.connect(self._type_changed)
        self._type_changed(self.type_combo.currentText())

    def _type_changed(self, ptype):
        matrix = ptype in MATRIX_PROBE_TYPES
        for key in ("num_elements_y", "pitch_y_mm"):
            self.set_row_visible(self.entries[key], matrix)
        self.probe_type_changed.emit(ptype)

    def get_values(self):
        vals = super().get_values()
        vals["probe_type"] = self.type_combo.currentText()
        return vals

    def set_values(self, values):
        super().set_values(values)
        if "probe_type" in values:
            self.type_combo.setCurrentText(values["probe_type"])


class WedgePanel(Panel):
    def __init__(self):
        super().__init__("Wedge Settings")
        self.material = self.add_combo("Material:", ["Custom"] + [m["name"] for m in MATERIALS.get("wedges", [])])
        self.add_number("angle_deg", 36.0, "Wedge Angle (deg):")
        self.add_number("height_mm", 15.0, "Height @ El.1 (mm):")
        self.add_number("velocity_ms", 2330.0, "Velocity (m/s):")
        self.add_number("offset_mm", 0.0, "Probe Offset X (mm):")
        self.add_number("array_sep_mm", 0.0, "Array Separation (mm):")
        self.add_number("roof_angle_deg", 0.0, "Roof Angle (deg):")
        self.material.activated.connect(self._material_chosen)
        self.update_visibility("Linear")

    def _material_chosen(self, _index):
        for m in MATERIALS.get("wedges", []):
            if m["name"] == self.material.currentText():
                self.entries["velocity_ms"].setValue(m["vl"])

    def update_visibility(self, probe_type):
        dual = probe_type in DUAL_PROBE_TYPES
        for key in ("array_sep_mm", "roof_angle_deg"):
            self.set_row_visible(self.entries[key], dual)


class MaterialPanel(Panel):
    def __init__(self):
        super().__init__("Component Settings")
        self.material = self.add_combo("Material:", ["Custom"] + [m["name"] for m in MATERIALS.get("components", [])])
        self.add_number("vel_long_ms", 5920.0, "L-Wave Vel (m/s):")
        self.add_number("vel_shear_ms", 3240.0, "S-Wave Vel (m/s):")
        # Display-only: frames the component fill/backwall in the ray plot. 0 = auto.
        self.add_number("thickness_mm", 0.0, "Thickness (mm, 0=auto):")
        self.material.activated.connect(self._material_chosen)

    def _material_chosen(self, _index):
        for m in MATERIALS.get("components", []):
            if m["name"] == self.material.currentText():
                self.entries["vel_long_ms"].setValue(m["vl"])
                self.entries["vel_shear_ms"].setValue(m["vs"])


Y_MODES_ALL = [Y_MODE_DERIVED_FROM_SKEW, Y_MODE_FIXED_Y, Y_MODE_Y_SWEEP]
Y_FIELDS = {"target_y_mm": [Y_MODE_FIXED_Y], "y_start_mm": [Y_MODE_Y_SWEEP],
            "y_end_mm": [Y_MODE_Y_SWEEP], "y_step_mm": [Y_MODE_Y_SWEEP]}
FOCUS_LABELS = {FOCUS_CONSTANT_DEPTH: "Target Depth (mm):",
                FOCUS_VERTICAL_LINE: "Target X (Global, mm):",
                FOCUS_CONSTANT_SOUND_PATH: "Focal Distance (mm):"}


class ScanPanel(Panel):
    def __init__(self):
        super().__init__("Scan Settings")
        self.focus_mode = self.add_combo("Focus Type:", list(FOCUS_LABELS), FOCUS_CONSTANT_DEPTH)
        self.wave_type = self.add_combo("Wave Type:", ["Longitudinal", "Shear"], "Longitudinal")
        self.add_number("start_angle", 40.0, "Start Angle (deg):")
        self.add_number("end_angle", 70.0, "End Angle (deg):")
        self.add_number("step_angle", 1.0, "Step (deg):")
        self.add_number("start_skew", 0.0, "Start Skew (deg):")
        self.add_number("end_skew", 0.0, "End Skew (deg):")
        self.add_number("step_skew", 1.0, "Skew Step (deg):")
        self.y_focus_mode = self.add_combo("Y Focus Mode:", Y_MODES_ALL, Y_MODE_DERIVED_FROM_SKEW)
        self.add_number("target_y_mm", 0.0, "Target Y (mm):")
        self.add_number("y_start_mm", 0.0, "Y Start (mm):")
        self.add_number("y_end_mm", 0.0, "Y End (mm):")
        self.add_number("y_step_mm", 1.0, "Y Step (mm):")
        self.focus_field = self.add_number("param_val", 50.0, FOCUS_LABELS[FOCUS_CONSTANT_DEPTH])
        self.has_skew = False
        self.focus_mode.currentTextChanged.connect(self._focus_changed)
        self.y_focus_mode.currentTextChanged.connect(lambda _: self._y_changed())
        self.update_visibility("Linear")

    def _focus_changed(self, mode):
        self.form.labelForField(self.focus_field).setText(FOCUS_LABELS[mode])
        # A fixed Y over-constrains the sound-path focus: not offered there.
        allowed = [m for m in Y_MODES_ALL if not (mode == FOCUS_CONSTANT_SOUND_PATH and m == Y_MODE_FIXED_Y)]
        current = self.y_focus_mode.currentText()
        self.y_focus_mode.blockSignals(True)
        self.y_focus_mode.clear()
        self.y_focus_mode.addItems(allowed)
        self.y_focus_mode.setCurrentText(current if current in allowed else Y_MODE_DERIVED_FROM_SKEW)
        self.y_focus_mode.blockSignals(False)
        self._y_changed()

    def _y_changed(self):
        mode = self.y_focus_mode.currentText()
        for key, modes in Y_FIELDS.items():
            self.set_row_visible(self.entries[key], self.has_skew and mode in modes)

    def update_visibility(self, probe_type):
        self.has_skew = probe_type in MATRIX_PROBE_TYPES
        for key in ("start_skew", "end_skew", "step_skew"):
            self.set_row_visible(self.entries[key], self.has_skew)
        self.set_row_visible(self.y_focus_mode, self.has_skew)
        self._y_changed()

    def get_values(self):
        vals = super().get_values()
        vals["focus_mode"] = self.focus_mode.currentText()
        vals["wave_type"] = self.wave_type.currentText()
        vals["y_focus_mode"] = self.y_focus_mode.currentText()
        return vals

    def set_values(self, values):
        super().set_values(values)
        if "focus_mode" in values:
            self.focus_mode.setCurrentText(values["focus_mode"])
        if "wave_type" in values:
            self.wave_type.setCurrentText(values["wave_type"])
        if "y_focus_mode" in values:
            if self.y_focus_mode.findText(values["y_focus_mode"]) < 0:
                raise ValueError(f"Y focus mode '{values['y_focus_mode']}' is not available "
                                 f"with focus type '{self.focus_mode.currentText()}'")
            self.y_focus_mode.setCurrentText(values["y_focus_mode"])


class SubAperturePanel(Panel):
    def __init__(self):
        super().__init__("Sub-Aperture Settings")
        self.add_number("start_element", 1, "Start Element:", integer=True)
        self.add_number("num_active_elements", 0, "Active Elements:", integer=True)
        hint = QtWidgets.QLabel("(0 = All elements)")
        hint.setStyleSheet("font-size: 8pt")
        self.form.addRow("", hint)
        self.order = self.add_combo("Element Order:", ["Column-first", "Row-first"], "Column-first")
        self.update_visibility("Linear")

    def update_visibility(self, probe_type):
        self.set_row_visible(self.order, probe_type in MATRIX_PROBE_TYPES)

    def get_values(self):
        vals = super().get_values()
        vals["element_order"] = self.order.currentText().lower()
        return vals

    def set_values(self, values):
        super().set_values(values)
        if "element_order" in values:
            v = values["element_order"].lower()
            if v not in ("column-first", "row-first"):
                raise ValueError(f"element order '{values['element_order']}' is not column-first or row-first")
            self.order.setCurrentText("Column-first" if v == "column-first" else "Row-first")
