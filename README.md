# Phased Array Focal Law Calculator

**Version 0.2.0** | Python & MATLAB Editions

Computes element-level time delays (focal laws) for ultrasonic phased array inspection. Implements Fermat's Principle across a planar wedge–component interface and supports 2D and full 3D geometry.

---

## Features

- **Four probe types**: Linear, Matrix, Dual Linear, Dual Matrix
- **Three focus modes**: Constant Depth, Vertical Line, Constant Sound Path
- **Wave types**: Longitudinal and Shear
- **3D beam steering** with azimuth and skew angles
- **Sub-aperture selection**: choose start element and active element count; configurable element numbering convention (Column-first / Row-first) for matrix arrays
- **Interactive GUI** with Ray Tracing, Data Table, and Delays histogram tabs
- **Export**: focal laws CSV, element coordinates (CSV / MAT / MATLAB script), configuration JSON
- **Python** (Tkinter GUI + importable library) and **MATLAB** (legacy-style GUI + classdef library) implementations with identical physics

---

## Quick Start

### Python

**Requirements:** Python 3.9+, `numpy`, `scipy`, `matplotlib`

```bash
pip install numpy scipy matplotlib
python python/app.py
```

Standalone executable:

```bash
pip install pyinstaller
python build_executable.py
```

### MATLAB

**Requirements:** MATLAB R2019b or later (no additional toolboxes required).

```matlab
run('matlab/main.m')
```

---

## GUI Overview

The left sidebar contains scrollable input panels:

| Panel | Fields |
|---|---|
| **Probe Settings** | Probe type, element count, pitch, frequency |
| **Wedge Settings** | Angle, height, velocity, offset; roof angle and array separation for dual probes |
| **Component Settings** | L-wave and S-wave velocities |
| **Scan Settings** | Focus type, wave type, angle/skew sweep, Y focus mode |
| **Sub-Aperture Settings** | Start element, active element count, element order (matrix only) |

Click **Calculate Laws** to compute. Select any row in the Data Table to display the corresponding ray paths and delay profile.

---

## Sub-Aperture Selection

Operators can restrict which elements fire by setting **Start Element** and **Active Elements** (0 = all). For matrix probes, **Element Order** selects the numbering convention:

| Convention | Description |
|---|---|
| **Column-first** *(default)* | Elements numbered along rows (X increments fastest) |
| **Row-first** | Elements numbered up columns (Y increments fastest) |

Inactive elements produce `NaN` entries in exported delay arrays.

---

## Python API — Quick Reference

```python
from probe import create_probe_assembly
from wedge import Wedge
from material import Material
from delay_law import DelayLaw

probe = create_probe_assembly(
    'Linear',              # probe type
    16,                    # num_elements
    0.6e-3,                # pitch (m)
    5e6,                   # frequency (Hz)
    start_element=5,       # first active element (1-indexed)
    num_active_elements=8  # number to fire (0 = all)
)

wedge  = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0)
mat    = Material(velocity_longitudinal=5920.0, velocity_shear=3240.0)
solver = DelayLaw(probe, wedge, mat)

result = solver.calculate_law(0.05, 0.0, 0.05)
# result['delays']        — NaN for inactive elements
# result['active_indices'] — 0-based active element indices
```

---

## MATLAB API — Quick Reference

```matlab
probe  = Probe(16, 0.6e-3, 5e6, 1, 0.0, 5, 8, 'column-first');
wedge  = Wedge(36.0, 15e-3, 2330.0);
mat    = Material(5920.0, 3240.0);
solver = DelayLaw(probe, wedge, mat);

result = solver.calculateLaw(0.05, 0.0, 0.05, 'longitudinal');
disp(result.Delays * 1e6)       % NaN for inactive elements
disp(result.ActiveIndices)      % 1-based active element list
```

---

## Source Structure

```
phased_array_calculator/
├── python/
│   ├── app.py          — GUI application
│   ├── probe.py        — Probe, DualProbe, sub-aperture logic
│   ├── delay_law.py    — Fermat solver, focal law calculation
│   ├── wedge.py        — Wedge geometry and coordinate transform
│   ├── material.py     — Material velocities
│   ├── panels.py       — Input panels (incl. SubAperturePanel)
│   └── plotting.py     — Ray tracing and histogram panels
├── matlab/
│   ├── PhasedArrayGUI.m — GUI
│   ├── Probe.m          — Probe class with sub-aperture support
│   ├── DualProbe.m      — DualProbe subclass
│   ├── DelayLaw.m       — Focal law solver
│   ├── Wedge.m          — Wedge class
│   └── Material.m       — Material class
├── UserManual.md        — Full user manual
└── CHANGELOG.md         — Version history
```

---

## Documentation

See [UserManual.md](UserManual.md) for full parameter reference, physics background, coordinate conventions, and troubleshooting.

---

*Contact: aled.t.davies@gmail.com*