# Phased Array Focal Law Calculator — User Manual

**Python & MATLAB Editions | Version 0.2.0**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Installation & Launch](#2-installation--launch)
3. [Graphical User Interface](#3-graphical-user-interface)
   - [3.1 Probe Settings](#31-probe-settings)
   - [3.2 Wedge Settings](#32-wedge-settings)
   - [3.3 Component Settings](#33-component-settings)
   - [3.4 Scan Settings](#34-scan-settings)
   - [3.5 Sub-Aperture Settings](#35-sub-aperture-settings)
4. [Step-by-Step Workflow](#4-step-by-step-workflow)
5. [Results & Visualisation](#5-results--visualisation)
6. [Export Formats](#6-export-formats)
7. [Python API Reference](#7-python-api-reference)
8. [MATLAB API Reference](#8-matlab-api-reference)
9. [Physics & Mathematics](#9-physics--mathematics)
   - [9.1 Fermat's Principle](#91-fermats-principle)
   - [9.2 2D Solver — Linear Probes](#92-2d-solver--linear-probes)
   - [9.3 3D Solver — Matrix & Dual Probes](#93-3d-solver--matrix--dual-probes)
   - [9.4 Delay Calculation](#94-delay-calculation)
   - [9.5 Coordinate Convention](#95-coordinate-convention)
   - [9.6 Wedge Coordinate Transform](#96-wedge-coordinate-transform)
10. [Known Limitations](#10-known-limitations)
11. [Troubleshooting](#11-troubleshooting)
12. [Source File Reference](#12-source-file-reference)

---

## 1. Overview

The Phased Array Focal Law Calculator computes the element-level time delays (focal laws) required to steer and focus an ultrasonic phased array beam to a specified target point in a component. It implements **Fermat's Principle of least time** across a planar wedge–component interface and supports four probe configurations in fully 3D geometry:

| Probe Type | Description |
|---|---|
| **Linear** | Single row of elements — 2D beam steering in the X-Z plane |
| **Matrix** | Rectangular N×M element grid — full 3D volumetric steering |
| **Dual Linear** | Two parallel linear sub-arrays separated in Y |
| **Dual Matrix** | Two parallel matrix sub-arrays separated in Y |

Both **Python** (Tkinter GUI + importable library) and **MATLAB** (App Designer GUI + classdef library) implementations are provided with identical physics, parameter conventions, and export formats.

---

## 2. Installation & Launch

### Python

**Requirements:** Python 3.9+, `numpy`, `scipy`, `matplotlib`, `tkinter`

```bash
pip install numpy scipy matplotlib
python python/app.py
```

To build a standalone executable:

```bash
pip install pyinstaller
python build_executable.py
# Output: phased_array_calculator_executable/ (next to project directory)
```

### MATLAB

**Requirements:** MATLAB R2019b or later (no additional toolboxes needed for core calculations).

```matlab
run('matlab/main.m')
```

---

## 3. Graphical User Interface

The GUI is divided into a **scrollable left sidebar** of input panels and a **right area** with three tabs: *Ray Tracing*, *Data Table*, and *Delays*. A status bar at the bottom of the sidebar shows progress and law count.

### 3.1 Probe Settings

| Field | Description | Units |
|---|---|---|
| Probe Type | Linear / Matrix / Dual Linear / Dual Matrix | — |
| Primary Elements (X) | Element count along the primary scan axis | count |
| Primary Pitch (X) | Centre-to-centre spacing in X | mm |
| Passive Elements (Y) | Element count along the passive axis *(Matrix / Dual Matrix only)* | count |
| Passive Pitch (Y) | Centre-to-centre spacing in Y *(Matrix / Dual Matrix only)* | mm |
| Frequency | Nominal transducer centre frequency | MHz |

> **Note:** The Y-axis fields are hidden automatically when Probe Type is Linear or Dual Linear.

### 3.2 Wedge Settings

| Field | Description | Units |
|---|---|---|
| Material | Preset wedge material — sets velocity automatically | — |
| Wedge Angle | Tilt of the probe relative to the interface (determines refraction angle in wedge) | degrees |
| Height @ El.1 | Vertical distance from Element 1 to the wedge–component interface | mm |
| Velocity | Longitudinal wave speed in the wedge material | m/s |
| Probe Offset X | Global X position of Element 1 | mm |
| Array Separation | Y-axis gap between the two sub-array centres *(Dual probes only)* | mm |
| Roof Angle | Roll tilt of the array plane about the X axis *(Dual probes only)* | degrees |

### 3.3 Component Settings

| Field | Description | Units |
|---|---|---|
| Material | Preset component material | — |
| L-Wave Velocity | Longitudinal wave speed in the component | m/s |
| S-Wave Velocity | Shear wave speed *(used when Wave Type = Shear)* | m/s |

### 3.4 Scan Settings

| Field | Description | Units |
|---|---|---|
| Focus Type | Constant Depth / Vertical Line / Constant Sound Path | — |
| Wave Type | Longitudinal or Shear | — |
| Start / End / Step Angle | Refracted beam angle sweep range (azimuth, in component) | degrees |
| Start / End / Step Skew | Skew angle sweep *(Matrix / Dual Matrix only)* | degrees |
| Y Focus Mode | Derived from Skew / Fixed Y / Y Sweep *(Matrix / Dual Matrix only)* | — |
| Target Depth / X / Distance | Primary focus parameter (meaning depends on Focus Type — see below) | mm |

#### Focus Types

- **Constant Depth** — Focal point lies on a horizontal plane at the specified depth Z. As beam angle increases the focal point moves laterally at constant depth.
- **Vertical Line** — Focal point is constrained to a fixed X coordinate. Depth varies with angle.
- **Constant Sound Path** — Focal point lies on a sphere of radius R centred on the beam entry point. All laws have equal path length in the component.

#### Y Focus Modes *(Matrix / Dual Matrix only)*

- **Derived from Skew** — Y coordinate is computed automatically from the skew angle and primary focus distance. Standard mode for raster or sector scans.
- **Fixed Y** — Override the Y focal coordinate to a constant value, independent of skew. Useful for off-axis fixed targets.
- **Y Sweep** — Generate a sequence of focal laws sweeping Y from *Y Start* to *Y End* in *Y Step* increments at each beam angle, producing a 2D planar scan.

---

### 3.5 Sub-Aperture Settings

By default the calculator uses all probe elements. The Sub-Aperture panel restricts firing to a contiguous subset — for example to replicate hardware aperture limits or phased sub-aperture sequencing.

| Field | Description | Units |
|---|---|---|
| Start Element | First active element (1-indexed from Element 1) | count |
| Active Elements | Number of consecutive elements to fire. **0 = all elements** (full aperture). | count |
| Element Order | Numbering convention used to map element index to the 2D grid — shown for Matrix / Dual Matrix probes only | — |

#### Element Numbering Conventions *(Matrix / Dual Matrix only)*

For a matrix array with **Nx** elements in X and **Ny** elements in Y the element grid can be numbered in two ways:

| Convention | Description | Mapping of element 1, 2, 3 … |
|---|---|---|
| **Column-first** *(default)* | X increments fastest; elements are numbered along each row from left to right, then the next row | (X=1,Y=1), (X=2,Y=1), (X=3,Y=1) … |
| **Row-first** | Y increments fastest; elements are numbered up each column from bottom to top, then the next column | (X=1,Y=1), (X=1,Y=2), (X=1,Y=3) … |

> **Note:** Element order only controls which elements are *selected* — it does not affect element positions or physics. With Active Elements = 0, all elements fire regardless of the convention setting.

Inactive elements produce `NaN` entries in delay and time-of-flight arrays.

---

## 4. Step-by-Step Workflow

1. Select **Probe Type** — Y-axis and dual-array fields appear as needed.
2. Enter element counts, pitches, and frequency.
3. Configure the **Wedge**: angle, height at Element 1, material velocity, and X offset. For dual probes set the array separation and roof angle.
4. Select or enter the **Component** material velocities.
5. Set **Focus Type**, **Wave Type**, and the angle sweep range. For matrix probes configure the skew range and Y focus mode.
6. *(Optional)* In **Sub-Aperture Settings**, set Start Element and Active Elements to restrict which elements fire. For matrix probes select the Element Order convention.
7. Click **Calculate Laws**. Results populate the Data Table and both plot tabs update.
8. Click any row in the Data Table to highlight that beam's ray paths and delay profile.
9. Click **Export CSV** to save all focal laws to `focal_laws_gui.csv`.
10. Use **File → Export Element Coordinates** to save element positions as `.csv`, `.mat`, or `.m`.
11. Use **File → Save Configuration** to store the complete setup as JSON.

---

## 5. Results & Visualisation

### Ray Tracing Tab

Displays refracted ray paths from each probe element through the interface to the focal point.

- **Linear probes:** single X-Z projection.
- **Matrix / Dual probes:** side-by-side X-Z and Y-Z projections; an optional 3D scatter view is available.

The **angle/skew sliders** at the top of the tab allow interactive navigation through the computed law set without re-running the calculation.

### Data Table Tab

| Column | Description |
|---|---|
| # | Law index |
| Angle (°) | Refracted beam angle in the component |
| Skew (°) | Skew angle (0° for linear probes) |
| Fx / Fy / Fz (mm) | Focal point coordinates |
| Min Delay (µs) | Smallest element delay in the law |
| Max Delay (µs) | Largest element delay in the law |

Error conditions (critical angle exceeded, Z < 0, Y out of reach) are shown inline as text rows.

### Delays Tab

Bar chart of per-element delay values for the currently selected focal law, with all other laws overlaid in light grey. Useful for verifying delay profile shape and identifying outlier elements.

---

## 6. Export Formats

### Focal Laws CSV (`focal_laws_gui.csv`)

| Column | Description | Units |
|---|---|---|
| LawID | Sequential law index | — |
| Angle_Deg | Refracted beam angle | degrees |
| Skew_Deg | Skew angle | degrees |
| Fx_mm / Fy_mm / Fz_mm | Focal point coordinates | mm |
| Velocity_m_s | Wave velocity used for this law | m/s |
| El_1_us … El_N_us | Delay for each element — **`NaN`** for inactive (sub-aperture) elements | µs |

### Element Coordinates (File → Export Element Coordinates)

| Format | Variables / Columns | Notes |
|---|---|---|
| `.csv` | ElementID, Global_X_mm, Global_Y_mm, Global_Z_mm | Standard comma-separated |
| `.mat` | ElementID, Global_X_mm, Global_Y_mm, Global_Z_mm, Coordinates_mm | MATLAB workspace; `load('file.mat')` directly |
| `.m` | Same variables as named arrays | MATLAB script; run to populate workspace |

### Configuration JSON (File → Save / Load Configuration)

Stores all panel values — probe type, element counts, pitches, wedge geometry, material velocities, scan settings, and **sub-aperture settings** — as a structured JSON file for reproducible setups.

---

## 7. Python API Reference

### `create_probe_assembly` — `probe.py`

```python
from probe import create_probe_assembly

probe = create_probe_assembly(
    probe_type,              # str: 'Linear' | 'Matrix' | 'Dual Linear' | 'Dual Matrix'
    num_elements,            # int   — primary axis element count
    pitch,                   # float — primary pitch (metres)
    freq,                    # float — frequency (Hz)
    num_elements_y=1,        # int   — passive axis count (Matrix/Dual only)
    pitch_y=0.0,             # float — passive pitch (metres)
    array_separation=0.0,    # float — sub-array Y gap (Dual only, metres)
    start_element=1,         # int   — first active element (1-indexed)
    num_active_elements=0,   # int   — active count (0 = all)
    element_order='column-first'  # str — 'column-first' | 'row-first'
)
```

### `Wedge` — `wedge.py`

```python
from wedge import Wedge

wedge = Wedge(
    angle_degrees,            # float — wedge angle (degrees)
    height_at_element1,       # float — height at Element 1 (metres)
    velocity,                 # float — wedge L-wave velocity (m/s)
    probe_offset_x=0.0,       # float — global X of Element 1 (metres)
    roof_angle_degrees=0.0    # float — Y-Z roll angle (degrees)
)
```

### `Material` — `material.py`

```python
from material import Material

mat = Material(
    velocity_longitudinal,    # float — L-wave speed (m/s)
    velocity_shear=None       # float or None — S-wave speed (m/s)
)
```

### `DelayLaw` — `delay_law.py`

```python
from delay_law import DelayLaw

solver = DelayLaw(probe, wedge, material)

result = solver.calculate_law(
    focal_point_x,            # float — metres
    focal_point_y,            # float — metres
    focal_point_z,            # float — metres
    wave_type='longitudinal'  # str: 'longitudinal' | 'shear'
)
```

**Return value** — `dict` with:

| Key | Type | Description |
|---|---|---|
| `delays` | `ndarray (N,)` | Element delays in **seconds** — `NaN` for inactive elements |
| `tof` | `ndarray (N,)` | Times-of-flight in **seconds** — `NaN` for inactive elements |
| `interface_points` | `ndarray (N, 3)` | Interface refraction point per element (metres) |
| `focal_point` | `ndarray (3,)` | Target focal point (metres) |
| `velocity_used` | `float` | Wave velocity used (m/s) |
| `active_indices` | `ndarray` | 0-based indices of active elements |

### Export

```python
solver.export_element_positions('output.csv')   # CSV
solver.export_element_positions('output.mat')   # MATLAB .mat workspace
solver.export_element_positions('output.m')     # MATLAB script
```

### Scripting Example

```python
from probe import create_probe_assembly
from wedge import Wedge
from material import Material
from delay_law import DelayLaw
import numpy as np

# 8×8 matrix probe, 0.5 mm pitch, 5 MHz — fire elements 1–32 only (column-first)
probe  = create_probe_assembly('Matrix', 8, 0.5e-3, 5e6, num_elements_y=8, pitch_y=0.5e-3,
                               start_element=1, num_active_elements=32)
wedge  = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0)
mat    = Material(velocity_longitudinal=5920.0, velocity_shear=3240.0)
solver = DelayLaw(probe, wedge, mat)

# Compute law — 0° azimuth, 0° skew, 30 mm depth
result = solver.calculate_law(0.0, 0.0, 30e-3, wave_type='longitudinal')
print('Delays (µs):', result['delays'] * 1e6)   # NaN for inactive elements
print('Active indices:', result['active_indices'])
```

---

## 8. MATLAB API Reference

All classes mirror the Python API. Parameters use the same units and conventions.

### `Probe` / `DualProbe`

```matlab
p = Probe(numElements, pitch, frequency, numElementsY, pitchY, startElement, numActiveElements, elementOrder)
p = DualProbe(numElements, pitch, frequency, numElementsY, pitchY, arraySeparation, startElement, numActiveElements, elementOrder)
```

Defaults: `startElement = 1`, `numActiveElements = 0` (all), `elementOrder = 'column-first'`.

### `Wedge`

```matlab
w = Wedge(angleDegrees, heightAtElement1, velocity, probeOffsetX, roofAngleDegrees)
```

### `Material`

```matlab
m = Material(velocityLongitudinal, velocityShear)
```

### `DelayLaw`

```matlab
solver = DelayLaw(probe, wedge, material);
result = solver.calculateLaw(focalX, focalY, focalZ, waveType);
```

**result** is a struct with fields: `Delays`, `ToF`, `InterfacePoints`, `FocalPoint`, `VelocityUsed`, `ActiveIndices`.

> `Delays` and `ToF` contain `NaN` for inactive elements.

### Export

```matlab
solver.exportElementPositions('output.csv')
solver.exportElementPositions('output.mat')
solver.exportElementPositions('output.m')
```

### Scripting Example

```matlab
% 8×8 matrix, fire first 32 elements only (column-first)
probe  = Probe(8, 0.5e-3, 5e6, 8, 0.5e-3, 1, 32, 'column-first');
wedge  = Wedge(36.0, 15e-3, 2330.0);
mat    = Material(5920.0, 3240.0);
solver = DelayLaw(probe, wedge, mat);

result = solver.calculateLaw(0.0, 0.0, 30e-3, 'longitudinal');
disp(result.Delays * 1e6)                          % NaN for inactive elements
disp(result.ActiveIndices)                         % 1-based active element list
```

---

## 9. Physics & Mathematics

### 9.1 Fermat's Principle

For an array element in wedge material (velocity **v₁**) insonifying a component (velocity **v₂**) through a planar interface, the time-of-flight via a candidate interface point **P** is:

```
T(P) = |element_i − P| / v₁  +  |P − focal_point| / v₂
```

Fermat's Principle requires `∇T = 0`, which enforces Snell's Law at the interface. The element delay is then `delay_i = max(TOF) − TOF_i`.

### 9.2 2D Solver — Linear Probes

When `num_elements_y = 1` and the focal Y coordinate is zero, the problem reduces to finding a scalar interface x-coordinate. Setting `dT/dx_i = 0` and rearranging (with offset `u = x_i − x_element`, lateral span `H`, wedge depth `h₁`, component depth `h₂`, velocity ratio `C = v₂/v₁`) yields a **quartic polynomial**:

```
(1 − C²)u⁴  −  2H(1 − C²)u³
  +  [(H² + h₁²) − C²(H² + h₂²)]u²  −  2Hh₁²u  +  H²h₁²  =  0
```

All real roots are evaluated; the one yielding minimum T is selected. This is a **closed-form, non-iterative** solution.

> **Special case — equal velocities (`v₁ = v₂`):** The leading coefficient vanishes and the polynomial degenerates to a cubic. This is handled naturally by `numpy.roots` / MATLAB `roots` without special-casing.

### 9.3 3D Solver — Matrix & Dual Probes

For 3D geometry the interface point has **two free coordinates** `(x_i, y_i)` and no closed-form solution exists. The stationarity conditions form a coupled 2×2 nonlinear system `∇T = 0`, solved by **Newton-Raphson** iteration using the analytical Hessian.

**Algorithm:**

1. **Initial guess** — linear interpolation by depth ratio:
   ```
   x_i⁰ = x₁ + (x₂ − x₁) · |z₁| / (|z₁| + |z₂|)
   y_i⁰ = y₁ + (y₂ − y₁) · |z₁| / (|z₁| + |z₂|)
   ```

2. **Newton-Raphson** — iterate `u ← u − H⁻¹ · ∇T` until `‖∇T‖ < 10⁻¹²` (max 20 iterations).

3. **Fallback** — if the Hessian is singular or convergence fails, fall back to `scipy.optimize.minimize` with L-BFGS-B (Python) or MATLAB `fminsearch`.

The analytical gradient and Hessian components (with distances `d₁`, `d₂` from element and focus to interface point respectively) are:

| Quantity | Expression |
|---|---|
| `∂T/∂x_i` | `Δx₁ / (v₁·d₁) − Δx₂ / (v₂·d₂)` |
| `∂T/∂y_i` | `Δy₁ / (v₁·d₁) − Δy₂ / (v₂·d₂)` |
| `∂²T/∂x_i²` | `(d₁² − Δx₁²)/(v₁·d₁³) + (d₂² − Δx₂²)/(v₂·d₂³)` |
| `∂²T/∂x_i∂y_i` | `−Δx₁Δy₁/(v₁·d₁³) − Δx₂Δy₂/(v₂·d₂³)` |

The objective function is strictly convex for all physically valid geometries, so convergence is guaranteed and typically achieved in **2–5 iterations** from the linear initial guess.

> **Degenerate geometry guard:** If the element and focal point share the same XY position (`‖p_start[:2] − p_end[:2]‖ < 10⁻⁹`), the solver returns the element XY position directly and computes a vertical TOF.

### 9.4 Delay Calculation

Once the TOF vector is assembled for the **active** elements:

```
delay_i = max(TOF over active elements) − TOF_i    [for active i]
delay_i = NaN                                       [for inactive i]
```

The active element with the longest path fires first (delay = 0); all others are delayed to produce simultaneous wavefront arrival at the focal point. The max-TOF reference is drawn only from active elements, so sub-aperture laws are internally consistent regardless of the disabled elements.

### 9.5 Coordinate Convention

| Axis | Direction | Notes |
|---|---|---|
| **X** | Primary scan axis | Along element row |
| **Y** | Passive / skew axis | Along element column for matrix arrays |
| **Z** | Depth | Z > 0 = component, Z < 0 = wedge, Z = 0 = interface |

### 9.6 Wedge Coordinate Transform

Element positions are computed in three steps:

1. **Local probe coordinates** — elements spaced by pitch along X, centred at origin, `z = 0`.
2. **Rotation about Y axis** by the wedge angle (squint/pitch). Optionally, additional rotation about X axis by the roof angle (roll).
3. **Translation** so that Element 1 arrives at `(probe_offset_x, 0, −height_at_element1)` in global coordinates.

The rotation matrices are:

```
Pitch (Y-axis rotation by θ):          Roll (X-axis rotation by φ):
[ cos θ   0   -sin θ ]                 [ 1     0       0   ]
[   0     1     0   ]                  [ 0   cos φ  -sin φ ]
[ sin θ   0    cos θ ]                 [ 0   sin φ   cos φ ]
```

---

## 10. Known Limitations

| Limitation | Detail |
|---|---|
| **Planar interface only** | The wedge–component interface is a flat plane at Z = 0. Curved surfaces, tapered wedges, and immersion setups are not supported. |
| **No diffraction or attenuation** | Geometric ray paths only. Beam spread, diffraction, frequency-dependent attenuation, and near-field effects are not modelled. |
| **Isotropic materials** | Both wedge and component are treated as acoustically isotropic. Anisotropic or textured materials require stiffness-matrix methods. |
| **Serial 3D solver** | The Newton-Raphson solver iterates over elements sequentially. For arrays larger than approximately 32×32 with long angle sweeps, calculation may take several seconds. Parallelisation is not yet implemented. |
| **Critical angle handling** | Beam angles beyond the first critical angle are flagged as errors in the Data Table. Mode-converted or head-wave paths are not computed. |

---

## 11. Troubleshooting

| Symptom | Likely Cause | Resolution |
|---|---|---|
| *"No valid focal laws"* warning | All beam angles exceed the critical angle for the material/wave mode combination | Reduce angle range, increase material velocity, or switch wave type |
| *Z < 0* error rows in table | Focus mode geometry produces negative depth for the chosen angle and parameter | Increase focal distance/depth, or narrow the angle range |
| Very long calculation times | Large matrix array (>16×16) with many angle/skew combinations | Reduce element count, narrow sweep range, or drive the library directly with `joblib` parallelism |
| NaN or Inf delays | Degenerate geometry (element directly above focal point, equal velocities) | Adjust probe offset or focal depth to avoid colinear geometry |
| MATLAB `load()` returns empty | `.mat` file saved but opened in wrong MATLAB version | Use `load('file.mat')` explicitly; ensure MATLAB R2019b or later |
| GUI unresponsive during calculation | Normal for large matrix sweeps — calculation runs on the main thread | Wait for *"Calculation complete"* status message |

---

## 12. Source File Reference

### Python (`python/`)

| File | Purpose |
|---|---|
| `delay_law.py` | Core solver: `solve_fermat_point`, `solve_fermat_point_3d`, `calculate_law` (active-element-only), `export_element_positions` |
| `probe.py` | `Probe` and `DualProbe` classes; `create_probe_assembly` factory; element grid generation; `get_active_element_indices()` |
| `wedge.py` | `Wedge` class; coordinate transform from probe-local to global frame |
| `material.py` | `Material` class storing longitudinal and shear velocities |
| `app.py` | Tkinter GUI application, scan engine, CSV export |
| `panels.py` | Input panels (Probe, Wedge, Material, Scan, SubAperture) |
| `plotting.py` | Ray tracing and delay histogram visualisation panels |
| `materials.json` | Built-in material velocity database |
| `verify_delays.py` | Standalone verification script |

### MATLAB (`matlab/`)

| File | Purpose |
|---|---|
| `DelayLaw.m` | Core solver class (mirrors Python `DelayLaw`) |
| `Probe.m` | `Probe` class |
| `DualProbe.m` | `DualProbe` subclass (extends `Probe`) |
| `Wedge.m` | `Wedge` class |
| `Material.m` | `Material` class |
| `PhasedArrayGUI.m` | App Designer GUI |
| `main.m` | Entry point / scripting demo |

---

*For bug reports or feature requests, open an issue on the project repository.*
