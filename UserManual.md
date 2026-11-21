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
   - [6a. Probe and Wedge Catalogues](#6a-probe-and-wedge-catalogues)
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

Both **Python** (Qt GUI + importable library) and **MATLAB** (App Designer GUI + classdef library) implementations are provided with identical physics, parameter conventions, and export formats.

---

## 2. Installation & Launch

### Python

**Requirements:** Python 3.9+ and `python/requirements.txt` (numpy, scipy, matplotlib, PySide6, qtpy, pyvista, pyvistaqt, pyqtgraph, ezdxf)

```bash
pip install numpy scipy matplotlib
python python/qt_app.py      # the window
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
| Thickness | Component thickness, display-only: frames the component fill and backwall line in the ray plot (0 = auto) | mm |

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
| **Column-first** *(default)* | Y increments fastest; elements are numbered up each column (fixed X) from Y=1, then the next column | (X=1,Y=1), (X=1,Y=2), (X=1,Y=3) … |
| **Row-first** | X increments fastest; elements are numbered along each row (fixed Y) from X=1, then the next row | (X=1,Y=1), (X=2,Y=1), (X=3,Y=1) … |

Dual matrix probes number the second array after the first (elements Nx·Ny+1 … 2·Nx·Ny), with the same convention inside each array.

> **Note:** Element order only controls which elements are *selected* — it does not affect element positions or physics. With Active Elements = 0, all elements fire regardless of the convention setting. Exported delays (`El_k_us`) and element coordinates are always listed in **column-first** order, whatever the setting; the Delays tab's aperture map shows each element's number in the chosen convention.

Inactive elements produce `NaN` entries in delay and time-of-flight arrays.

---

## 4. Step-by-Step Workflow

1. Select **Probe Type** — Y-axis and dual-array fields appear as needed.
2. Enter element counts, pitches, and frequency — or use **File → Load Probe from Catalogue…** (and **Load Wedge from Catalogue…** for step 3), see §6a.
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

Displays the inspection scene: the wedge body and schematic probe housing, the
component (grey fill, with a backwall line when a Thickness is set), active
elements (coloured squares) and inactive sub-aperture elements (grey open
squares), the envelope rays of the **active aperture** from element to
interface to focal point, and the focal-point marker. Wedge dimensions
(element-1 height, wedge angle) are annotated on the plot.

- **Linear probes:** single X-Z projection.
- **Matrix / Dual probes:** side-by-side X-Z and Y-Z projections.
- **Show All:** overlays every law in the sweep, coloured by law index.
- **Catalogue wedge:** when the wedge was loaded from a buildFE catalogue entry and its panel values are unchanged, the X-Z view draws the catalogue's wedge outline instead of the schematic silhouette.

The **angle/skew sliders** below each plot navigate the computed law set without re-running the calculation. They pick the first law with that angle and skew; the **◀ ▶** buttons step through every law in order (needed for Y-sweep laws, which share an angle and skew), and the readout shows the law number and focal point. **Play** animates through all laws. Selecting a row in the Data Table shows that exact law in every tab.

### 3D View Tab

**Qt window (PyVista/VTK).** The scene shows:
- the wedge and the component as translucent solids;
- element footprints at the catalogue's element width and elevation, or a labelled schematic size;
- the selected law's rays, interface points and focus, and the sweep's foci.

Drag to rotate, scroll to zoom. **Iso**, **X-Z**, **Y-Z** and **Top** set the camera, with depth always downward; the axis views are drawn in parallel projection. **Section** cuts the wedge and component at the active aperture's centre (an X-Z plane). Click near an element to inspect it: the readout gives its number in the chosen numbering convention, its array (Tx/Rx), its X/Y grid position, its delay and its time of flight, and its ray is drawn in orange.


### Qt window: live 2D views

In the Qt window the Ray Tracing and Delays tabs are pyqtgraph views:
- **Navigation:** scroll to zoom, drag to pan; right-click for the view menu. The law shown is shared: moving the slider, stepping or playing in any tab (or selecting a table row) moves every tab to that law.
- **Drag the focus:** drag the focal-point marker in the X-Z view to move the focus. The law for that point is solved as you drag and shown in every tab (rays, delays, 3D), with the readout "Dragged focus (not in the sweep)". The focus keeps the current law's Y. It isn't added to the sweep, the table or the CSV, and a slider, step or table selection returns to the sweep. A focus above the surface is refused.
- **Coverage (toolbar):** Off, Direct, Direct + 1st skip, or Direct + 2 skips.
  - Each law's central ray starts at the active aperture's centre, refracts at the surface, and reflects at the backwall and surface of a flat plate of the component **Thickness**, which must be set.
  - The sweep's central rays sweep out fans, drawn per leg (blue direct, purple 1st skip, pink 2nd skip), one fan per skew.
  - The current law's central ray is drawn dashed, and it follows a dragged focus.
  - Assumption: each reflection keeps the wave mode (no mode conversion), and only central rays are shown, not the beam's spread.
- **Weld (Setup panel):** None, Single-V, Double-V, Single-J or DXF file, placed at **Weld Centre X** (global X) through the component **Thickness**, which must be set.
  - Templates: bevel angle from the vertical, root gap and root face. Double-V also takes a lower bevel and the root depth (0 = mid-thickness). Single-J takes the J radius and the plate the J is cut in (near = −X, far = +X). Cap and root are flush.
  - DXF: the closed outline of the weld region, with x = 0 at the weld centreline and y up. **DXF y = 0 at** says whether y = 0 is the surface (part drawn below) or the backwall (part drawn above). **DXF Units** overrides the file's stated units. Name the **DXF Layer** when the file holds more than one closed outline, for example a plate as well as the weld.
  - The weld is read when the laws are calculated. It is drawn in X-Z and in 3D.
  - With Coverage on, each fusion face is green where a fan of the selected legs reaches it and red at gaps, and the toolbar gives the covered share and the gap length. "Covered" means a central-ray fan reaches the face; the incidence angle on the face is not judged.
- **Select an element:** click an element marker (X-Z or Y-Z), a delay bar, a delay-map cell or an element in the 3D view. It is selected in every tab: orange in the projections and the 3D view, outlined in the delay map, and reported in the 3D readout.

### Beam Field Tab (Qt window)

The beam of the law shown in the other tabs, in the component, as a map in dB re its maximum (turbo, 0 to −30 dB) with the −6 dB contour (white), the focus (+) and the fitted beam axis (dotted). Press **Compute field**: it takes a few seconds (2D) to about a minute (3D), with a progress bar.

- **Model:** **2D** treats each element as an infinitely long strip and maps the X-Z section; it needs a single linear array without a roof. **3D** splits each element into point sources over its width and **Elevation** and maps the X-Z section through the aperture centre and the Y-Z section through the focus.
- **Pulse:** a Hann-windowed burst of **Cycles** at the probe frequency (the map is the peak of the displacement envelope over time), or a **continuous wave** at the probe frequency (faster).
- **Inputs:** **Element width**, **Elevation**, the wedge's **S-wave** speed and **density** and the **component density**. They are filled from the catalogue when the probe or wedge comes from one, and saved in configurations.
- **Grid:** the map's spacing. It is coarsened automatically for large areas; the status line gives the spacing used.
- **Show in 3D view:** draws the computed sections in the 3D View as coloured planes.
- A field belongs to its law: when the law, the setup or an input changes, it is marked stale and taken out of the 3D view until it is computed again. After a setup edit (probe, wedge, component, scan or aperture), press **Calculate Laws** before computing the field again.
- **The model:** each element radiates into the wedge as a normal strip load (Miller–Pursey directivity); each ray refracts at the surface by Snell's law, with the plane-wave transmission coefficient of a bonded (welded) wedge and geometric beam spread; the elements' pulses are added with their delays. Not modelled: back-wall and surface reflections, mode conversion, attenuation, and a fluid couplant layer.
- **Validation:** the 2D pulsed mode was compared with buildFE's FE solve of the 2.25L64-A2 on the SA2-N55S wedge (64 elements, 45° shear), against acceptance tolerances fixed before the comparison: beam angle ±1°, exit point ±2 mm, −6 dB widths ±10 %, axis levels ±1.5 dB. Result: beam angle within 0.37°, exit point within 0.01 mm, −6 dB widths within 0.6 % and axis levels within 0.44 dB (`validation/beam_field/`). The 3D mode is not separately validated. How the field is computed, and where it can be trusted, is set out in [the beam field model note](docs/beam_field_model.html).

### Data Table Tab

| Column | Description |
|---|---|
| # | Law index |
| Angle (°) | Refracted beam angle in the component |
| Skew (°) | Skew angle (0° for linear probes) |
| Fx / Fy / Fz (mm) | Focal point coordinates |
| Min Delay (µs) | Smallest element delay in the law |
| Max Delay (µs) | Largest element delay in the law |

Refused laws are shown inline as rows numbered "-": critical angle exceeded (**Crit**), focus not below the surface (**Z<0**), beam parallel to the vertical line (**Parallel**: a 0° refracted angle or 90° skew in Vertical Line mode), and Y out of reach. Min/Max Delay are taken over the active elements.

### Delays Tab

- **Linear / Dual Linear probes:** bar chart of per-element delay for the selected law; inactive elements are marked with grey crosses, and a dotted line separates the two arrays of a dual probe.
- **Matrix / Dual Matrix probes:** a delay map over the element grid (X across, Y up), one per array, inactive elements grey, each cell labelled with its element number in the chosen numbering convention — a direct check of the sub-aperture and convention settings.

The colour or y scale is fixed to the largest delay in the sweep, so laws can be compared while stepping.

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

Stores all panel values — probe type, element counts, pitches, wedge geometry, material velocities, scan settings, and **sub-aperture settings** — as a structured JSON file for reproducible setups. When a probe or wedge came from a catalogue, a `catalog` block records, per asset, its id, manufacturer, model, the catalogue file and its SHA-256, the format, the buildFE content hash (`sha256`) with its stamp status, and `values_match` (false once a catalogue value has been edited in the panel).

---

## 6a. Probe and Wedge Catalogues

**File → Load Probe from Catalogue…** and **File → Load Wedge from Catalogue…** fill the Probe or Wedge panel from a catalogue entry, so the calculator uses the same probe and wedge values as buildFE. The file dialog opens in `$PAC_CATALOG_DIR`, or a sibling `buildFE/catalog` (then `nde-knowledge/exports/catalog`) checkout when one exists. A filterable list shows the entries; entries the calculator cannot use (single elements, curved arrays, …) are hidden unless *Usable only* is cleared, and the reason is shown.

| Format | Files | What is read |
|---|---|---|
| buildFE 0.1 | `buildFE/catalog/probes.json`, `wedges.json` | `{value, source}` values (an unsourced value is refused); the entry's content hash is recomputed exactly as `buildfe.asset.digest` does and compared with its stamp: **ok**, **changed** (a different asset to buildFE) or **unstamped** |
| nde-knowledge 1 | `nde-knowledge/exports/catalog/probes.json`, `wedges.json` | plain SI values; the file's SHA-256 identifies the copy read |

**Probes.** Linear, matrix, dual linear and dual matrix arrays map to the four probe types. A pitch the catalogue does not print is derived as active aperture ÷ elements (reported); a printed pitch that disagrees with the aperture, and the catalogue's own inconsistency notes, are reported, never corrected. Array separation is not in either catalogue and stays as entered.

**Wedges (buildFE).** buildFE's wedge frame has x along the contact face from the low end of the probe face, y up, elements ascending up the face, beam towards +x. It maps onto this calculator's frame with X = x and Z = −y, so element 1's catalogue centre (x₁, y₁) gives **Probe Offset X = x₁** and **Height @ El.1 = y₁** (the phased-array convention: height to element 1), the face angle gives the **Wedge Angle**, and the longitudinal speed the **Velocity**. `simple` and `polygon` outlines are read; a probe face that descends towards +x is refused. The outline is drawn in the X-Z and 3D views while the panel values still match it (and no roof angle is set).

**Wedges (nde-knowledge 1).** The export carries no element-1 seat or wave speed: only the wedge angle (where printed) is filled, and the message lists what to enter by hand. Curved wedges are flagged; the calculator models a flat interface.

The loaded values remain ordinary panel values: edit them freely; the configuration's `catalog` block then records `values_match: false`.

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

### `focal_targets` — `focal_rules.py`

```python
from focal_rules import focal_targets, Target
targets = focal_targets(solver, "constant-depth", 0.03,     # mode, value (m)
                        angles_deg=[40, 50, 60], skews_deg=[0, 10],
                        wave="shear", y_mode="from-skew")    # or "fixed" / "sweep" with y_values=[...]
for t in targets:
    if isinstance(t, Target):
        law = solver.calculate_law(t.x, t.y, t.z, wave_type="shear")
    else:
        print(t.angle_deg, t.skew_deg, t.reason)          # a Refused law and why
```

Modes: `constant-depth` (Z = value), `vertical-line` (X = value), `sound-path` (distance along the central ray). The central ray starts at the active sub-aperture's centre. Refusal reasons: `critical angle`, `focus not below surface`, `beam parallel to line`, `Y out of reach`. MATLAB: `FocalRules.targets(solver, mode, value, anglesDeg, skewsDeg, wave, yMode, yValues)` returns a struct array (`Angle, Skew, X, Y, Z, Reason`). The two are checked against shared cases (`tests/focal_rule_cases.json`).

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

> **Special case — equal velocities (`v₁ = v₂`):** Both quartic and cubic coefficients vanish, leaving a quadratic. The selected minimum is the straight segment through the interface.

### 9.3 3D Solver — Matrix & Dual Probes

For a planar interface and isotropic speeds, the minimum lies in the vertical incidence plane through the source and focus. Let `D` be their horizontal separation, `u` the distance from the source projection to the interface point, and `h₁`, `h₂` the two positive depths. Solve the dimensionless Snell residual on `0 ≤ u ≤ D`:

```
u / sqrt(u² + h₁²) − (v₁/v₂)(D−u) / sqrt((D−u)² + h₂²) = 0
```

For positive depths it is strictly increasing and has one root. Python uses bracketed Brent iteration; MATLAB uses bracketed `fzero`. Lengths are scaled before evaluation and the residual must be at most `1e-10`; failure raises an error. The horizontal root is rotated back to global X/Y. A vertical ray returns the shared horizontal position. A source on the interface uses the appropriate one-sided boundary minimum.

The solver requires finite endpoints, source Z ≤ 0, focus Z > 0 and finite positive wave speeds. Unknown wave modes and shear mode without a shear speed are refused. Strict convexity alone does not guarantee convergence of an unguarded Newton iteration; the former Newton/minimisation fallback has been removed.

Python caches transformed geometry and active indices using their actual probe/wedge parameters; changing those parameters invalidates the cache. Time of flight and target-dependent results are always recomputed.

Angle/skew targets use the refracted central ray from the geometric centre of the active sub-aperture (the whole array when no sub-aperture is set), so each sub-aperture of a sequence steers and focuses about its own centre: both the wedge entry displacement and the component displacement rotate with skew. This follows the geometry of Schmerr, *Fundamentals of Ultrasonic Phased Arrays* (2015), §§5.2 and 8.2, especially Eqs. 8.14–8.15. A fixed-Y override is an explicit target constraint and does not promise the displayed nominal skew. A sound-path Y sweep derives its effective skew from the complete central-ray horizontal displacement. This is numerical ray verification, not experimental validation or a model of finite-aperture beam maxima.

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
| **Serial 3D solver** | The bracketed Snell solver evaluates elements sequentially. Large arrays and long angle sweeps may take several seconds. Parallelisation is not yet implemented. |
| **Roof angle** | Applied to dual probes only. The Height @ El.1 is set before the roof tilt, so with a roof each array's element 1 sits slightly higher or lower than the value entered. |
| **Catalogue wedges** | Wedge width, roof geometry and curvature are not read from catalogues; nde-knowledge 1 wedges carry no element-1 seat. |
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
| `focal_rules.py` | `focal_targets`: focal points for angle/skew/Y sweeps in every focus mode, with refusal reasons |
| `scene_model.py` | `build_scene`: the geometry every view draws, as primitives in the global frame |
| `qt_app.py` | Qt GUI (qtpy/PySide6): main window, menus, table, dialogs |
| `qt_panels.py`, `qt_plotting.py`, `qt_catalog_dialog.py` | Qt input panels, plot tabs and catalogue picker |
| `session.py` | Solver from panel values, sweep into laws and table rows, focal-law CSV, catalogue links (behind the window) |
| `navigation.py` | Law navigation: angle/skew sliders, step buttons, table selection |
| `qt_view3d.py` | Qt 3D tab (pyvistaqt): picking, section, camera presets |
| `qt_views2d.py` | Qt Ray Tracing and Delays tabs (pyqtgraph): dragged focus, linked element selection |
| `scene_vtk.py` | PyVista renderer of the scene model; off-screen rendering for tests and exports |
| `scene.py` | Toolkit-independent scene drawing (2D projections, 3D scene, aperture delay maps) used by the scripts; its colours by the window |
| `catalog.py` | buildFE / nde-knowledge catalogue reader, buildFE content hash, frame mapping |
| `materials.json` | Built-in material velocity database |
| `verify_delays.py` | Standalone verification script |

### MATLAB (`matlab/`)

| File | Purpose |
|---|---|
| `DelayLaw.m` | Core solver class (mirrors Python `DelayLaw`) |
| `FocalRules.m` | Focal targets (mirrors Python `focal_rules.py`; shared case table) |
| `Probe.m` | `Probe` class |
| `DualProbe.m` | `DualProbe` subclass (extends `Probe`) |
| `Wedge.m` | `Wedge` class |
| `Material.m` | `Material` class |
| `PhasedArrayGUI.m` | App Designer GUI |
| `main.m` | Entry point / scripting demo |

---

*For bug reports or feature requests, open an issue on the project repository.*
