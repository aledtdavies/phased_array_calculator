"""
Write tests/focal_rule_cases.json: focal-rule cases and the Python targets for each, the shared
table MATLAB's testFocalRules checks FocalRules.targets against (Python/MATLAB parity of the
physics, owner decision D1). test_focal_rules.py checks that the file is current.

    python make_focal_rule_cases.py
"""
import json
import os

from delay_law import DelayLaw
from focal_rules import Target, focal_targets
from material import Material
from probe import create_probe_assembly
from wedge import Wedge

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "focal_rule_cases.json")

LIN = {"type": "Linear", "n": 16, "pitch": 0.6e-3, "start": 1, "active": 0}
LIN_SUB = dict(LIN, start=5, active=8)
MAT = {"type": "Matrix", "n": 8, "pitch": 1.0e-3, "ny": 4, "pitch_y": 1.2e-3, "start": 3,
       "active": 20, "order": "row-first"}
MAT_FULL = dict(MAT, start=1, active=0, order="column-first")
DUAL = {"type": "Dual Matrix", "n": 8, "pitch": 1.0e-3, "ny": 2, "pitch_y": 1.5e-3, "sep": 10e-3,
        "start": 1, "active": 0, "order": "column-first"}
WEDGE = {"angle": 30.0, "height": 0.012, "velocity": 2330.0, "offset": 0.003, "roof": 0.0}
WEDGE_ROOF = dict(WEDGE, roof=4.0)
STEEL = {"vl": 5920.0, "vs": 3240.0}
SLOW = {"vl": 2000.0, "vs": 1000.0}

CASES = [
    ("depth linear", LIN, WEDGE, STEEL, "constant-depth", 0.03, [-20, 0, 40, 70], [0], "longitudinal", "from-skew", None),
    ("depth linear sub-aperture shear", LIN_SUB, WEDGE, STEEL, "constant-depth", 0.02, [40, 55, 70], [0], "shear", "from-skew", None),
    ("vertical line linear", LIN, WEDGE, STEEL, "vertical-line", 0.04, [-10, 0, 10, 45], [0], "longitudinal", "from-skew", None),
    ("sound path linear", LIN, WEDGE, STEEL, "sound-path", 0.035, [0, 30, 60], [0], "shear", "from-skew", None),
    ("critical angle", LIN, WEDGE, SLOW, "constant-depth", 0.03, [20, 80], [0], "longitudinal", "from-skew", None),
    ("depth matrix skew", MAT, WEDGE, STEEL, "constant-depth", 0.025, [40, 60], [-20, 0, 15], "longitudinal", "from-skew", None),
    ("vertical matrix skew", MAT, WEDGE, STEEL, "vertical-line", 0.03, [30, 50], [-30, 0, 90], "longitudinal", "from-skew", None),
    ("path matrix skew", MAT, WEDGE, STEEL, "sound-path", 0.04, [35, 55], [-10, 10], "shear", "from-skew", None),
    ("depth matrix fixed y", MAT, WEDGE, STEEL, "constant-depth", 0.025, [45], [-10, 10], "longitudinal", "fixed", [0.003]),
    ("vertical matrix y sweep", MAT, WEDGE, STEEL, "vertical-line", 0.035, [40, 60], [0, 10], "longitudinal", "sweep", [-0.004, 0.0, 0.004]),
    ("path matrix y sweep", MAT, WEDGE, STEEL, "sound-path", 0.04, [30, 60], [-20, 0, 20], "longitudinal", "sweep", [0.0, 0.01, 0.2]),
    ("path y sweep at 0 deg (no reach), centre Y = 0", LIN, WEDGE, STEEL, "sound-path", 0.04, [0, 30], [0], "longitudinal", "sweep", [0.0, 0.01]),
    ("vertical line reached only with skew", MAT_FULL, WEDGE, STEEL, "vertical-line", 0.00872776354658795, [40], [0, 60], "longitudinal", "from-skew", None),
    ("zero sound path y sweep", MAT_FULL, WEDGE, STEEL, "sound-path", 0.0, [30], [0], "longitudinal", "sweep", [0.0, 0.002]),
    ("depth dual matrix roof", DUAL, WEDGE_ROOF, STEEL, "constant-depth", 0.02, [45, 60], [-10, 10], "longitudinal", "from-skew", None),
]


def make_solver(p, w, m):
    probe = create_probe_assembly(p["type"], p["n"], p["pitch"], 5e6, num_elements_y=p.get("ny", 1),
                                  pitch_y=p.get("pitch_y", 0.0), array_separation=p.get("sep", 0.0),
                                  start_element=p["start"], num_active_elements=p["active"],
                                  element_order=p.get("order", "column-first"))
    return DelayLaw(probe, Wedge(w["angle"], w["height"], w["velocity"], w["offset"], w["roof"]),
                    Material(m["vl"], m["vs"]))


def build_cases():
    cases = []
    for name, p, w, m, mode, value, angles, skews, wave, y_mode, y_values in CASES:
        ts = focal_targets(make_solver(p, w, m), mode, value, angles, skews, wave=wave,
                           y_mode=y_mode, y_values=y_values)
        out = []
        for t in ts:
            if isinstance(t, Target):
                out.append({"angle": t.angle_deg, "skew": t.skew_deg, "x": t.x, "y": t.y, "z": t.z})
            else:
                out.append({"angle": t.angle_deg, "skew": t.skew_deg, "reason": t.reason})
        cases.append({"name": name,
                      "inputs": {"probe": p, "wedge": w, "material": m, "mode": mode, "value": value,
                                 "angles": angles, "skews": skews, "wave": wave, "y_mode": y_mode,
                                 "y_values": y_values},
                      "targets": out})
    return {"about": "Focal-rule cases and their Python targets (python/make_focal_rule_cases.py). "
                     "SI units, angles in degrees, global frame (X along the wedge, Y across, Z down).",
            "cases": cases}


if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(build_cases(), f, indent=1)
        f.write("\n")
    print(os.path.normpath(OUT))
