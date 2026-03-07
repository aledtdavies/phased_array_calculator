# Implementation Plan — 3D Matrix Array Extension

## Goal Description
Extend the current 2D Phased Array Calculator to support **3D Geometry** and **2D Matrix Arrays**.
This will allow the user to:
1. Define a **Matrix Probe** (elements in X *and* Y).
2. Steer beams in both **Azimuth** (primary / scan axis) and **Skew** (secondary / passive axis).
3. Calculate delay laws and ray paths in a full 3D volume.

### Background — Current 2D State
All coordinates are currently `(x, z)`.  The quartic‑polynomial Fermat solver operates on a single interface variable `u`.  Extending to 3D means every coordinate becomes `(x, y, z)`, the interface point becomes `(x_i, y_i, 0)`, and the solver must minimise over **two** unknowns.

## User Review Required

> [!IMPORTANT]
> **Numerical Solver**: The 2D code uses a closed‑form quartic (`np.roots`).  In 3D the equivalent stationarity conditions are two coupled non‑linear equations — no clean closed‑form exists.  A **Newton‑Raphson** solver on the 2×2 gradient system is recommended; the Hessian is cheap to evaluate and the problem is strictly convex, so convergence is guaranteed in 2–4 iterations with a reasonable initial guess. A **fallback `scipy.optimize.minimize`** (L‑BFGS‑B, bounded to the interface) should be included for edge‑cases.

> [!WARNING]
> **Performance**: A matrix probe can have `N_x × N_y` elements (e.g. 32 × 32 = 1 024).  Combined with an angular sweep this means thousands of 3D Fermat solves per calculation run.  Vectorised initial‑guess computation and optional `joblib` parallelism should be planned from the start.

> [!IMPORTANT]
> **Backward Compatibility**: When `num_elements_y = 1` the code **must** reproduce the existing 2D results to within floating‑point tolerance.  This is the primary acceptance criterion before any new functionality is exercised.

---

## Proposed Changes

### 1. Core Data Model — Probe & Geometry

#### [MODIFY] [probe.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/probe.py)

| Current | Proposed |
|---|---|
| `__init__(num_elements, pitch, frequency)` | Add `num_elements_y: int = 1`, `pitch_y: float = 0.0` |
| `get_element_positions → (N, 2)` `[x, z]` | Return `(N_x × N_y, 3)` — `[x, y, z]` with `z = 0` |
| `num_elements` used everywhere | Add `total_elements` property (`N_x * N_y`) |

- Generate a 2D grid with `np.meshgrid` over X and Y pitches.
- When `num_elements_y == 1`, Y‑column is all‑zeros → identical geometry to today.
- `get_element_of_interest_indices` should return `np.arange(total_elements)`.

#### [MODIFY] [wedge.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/wedge.py)

| Current | Proposed |
|---|---|
| 2D rotation `[x, z]` by wedge angle | 3D rotation in the X‑Z plane; Y passes through unchanged |
| Returns `(N, 2)` | Returns `(N, 3)` |

- Build a 3×3 rotation matrix (rotation about the Y‑axis by `angle_rad`).
- Translation adds `(probe_offset_x, 0, −height_at_element1)`.
- Future: `probe_offset_y` parameter if lateral offset is needed.

#### [MODIFY] [material.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/material.py)
- No changes expected — velocities are scalar and dimension‑independent.

---

### 2. 3D Ray‑Tracing Solver

#### [MODIFY] [delay_law.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/delay_law.py)

##### New method: `solve_fermat_point_3d(p_start, p_end, v1, v2)`

**Inputs**: `p_start = (x₁, y₁, z₁)` (element in wedge), `p_end = (x₂, y₂, z₂)` (focal point in component).

**Objective**: Find `P_int = (x_i, y_i, 0)` on the interface that minimises total time:

$$ T(x_i, y_i) = \frac{\sqrt{(x_1-x_i)^2 + (y_1-y_i)^2 + z_1^2}}{v_1} + \frac{\sqrt{(x_2-x_i)^2 + (y_2-y_i)^2 + z_2^2}}{v_2} $$

**Algorithm**:
1. **Initial guess**: simple linear interpolation: `x_i₀ = x₁ + (x₂ − x₁) · |z₁| / (|z₁| + |z₂|)`, same for `y_i₀`.
2. **Newton‑Raphson** on the gradient `∇T = (∂T/∂x_i, ∂T/∂y_i) = 0`:
   - Analytical gradient and 2×2 Hessian (closed‑form, cheap).
   - Convergence tolerance: `‖∇T‖ < 1e-12`.
   - Max iterations: 20 (should converge in 2–5).
3. **Fallback**: If Newton fails to converge (e.g. singular Hessian near degenerate geometry), fall back to `scipy.optimize.minimize(method='L-BFGS-B')`.
4. **Return**: `(x_i, y_i)` interface coordinates and the minimum time‑of‑flight.

##### Retain: `solve_fermat_point` (original 2D)
Keep the existing quartic solver as the **fast path** for linear arrays (`num_elements_y == 1`) — this avoids any performance regression or numerical risk for the most common use‑case.

##### Modified: `calculate_law`

| Current | Proposed |
|---|---|
| `calculate_law(focal_point_x, focal_point_z, wave_type)` | `calculate_law(focal_point_x, focal_point_y, focal_point_z, wave_type)` |
| Iterates `num_elements` | Iterates `total_elements` |
| Interface points `(N, 2)` | Interface points `(N, 3)` |
| Uses `solve_fermat_point` | Dispatches to `solve_fermat_point` (2D) or `solve_fermat_point_3d` (3D) based on probe type |

##### Modified: `export_element_positions`
- Add `Global_Y_mm` column to CSV, `.mat`, and `.m` exports.

---

### 3. Focal‑Point Geometry (Steering)

#### [MODIFY] [app.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/app.py)

`run_calculation` currently computes the focal point in 2D:

```python
fx = x_int + fz * np.tan(beta_rad)
```

For 3D with an additional **skew angle** `φ`:

```python
# Spherical-to-Cartesian conversion from beam entry point
fx = x_int + fz * np.tan(beta_rad) * np.cos(skew_rad)
fy = y_int + fz * np.tan(beta_rad) * np.sin(skew_rad)
```

When `skew = 0`, `fy = 0` and `fx` is unchanged → backward compatible.

**Other changes in `app.py`:**
- Update `get_solver` to pass new probe parameters.
- Pass `fy` to `solver.calculate_law(fx, fy, fz, wave_type)`.
- Results table: add `FY (mm)` column.
- Export CSV: include Y coordinate.
- Config save/load: include new probe/scan parameters.

---

### 4. GUI Panels

#### [MODIFY] [panels.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/panels.py)

**`ProbePanel`** — add:
- `num_elements_y` (default 1) — labelled "Passive Axis Elements".
- `pitch_y_mm` (default 0.0) — labelled "Passive Pitch (mm)".
- Conditionally show/hide these fields, or always show with sensible defaults.

**`ScanPanel`** — add:
- `skew_angle` (default 0.0°) — labelled "Skew Angle (deg)".
- Place below the existing angle fields.
- `get_values` / `set_values` updated to include it.

---

### 5. Visualisation

#### [MODIFY] [plotting.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/plotting.py)

**When `num_elements_y == 1`** (linear probe):
- No change to existing 2D X‑Z ray plot — fully backward compatible.

**When `num_elements_y > 1`** (matrix probe):
- **Primary view**: Two side‑by‑side 2D projections (X‑Z and Y‑Z) showing element positions, interface points, and focal point. These are more useful for engineering than a 3D scatter plot.
- **Secondary view (optional tab)**: 3D scatter/line plot using `mpl_toolkits.mplot3d`. Elements as markers, ray paths as lines, focal point as a star.
- Delay histogram: unchanged (element index vs delay) — naturally extends to more elements.

---

### 6. Verification Script

#### [MODIFY] [verify_delays.py](file:///c:/Users/aledd/Documents/Projects/phased_array_calculator/python/verify_delays.py)

Extend or create a companion `verify_delays_3d.py` that exercises the new solver with known reference cases.

---

## Robustness & Edge‑Case Handling

### Input Validation
| Parameter | Constraint | Error Handling |
|---|---|---|
| `num_elements_y` | ≥ 1, integer | Clamp / warning in `ProbePanel` |
| `pitch_y` | ≥ 0 when `N_y > 1` | Raise `ValueError` in `Probe.__init__` |
| Skew angle | −90° < φ < +90° | GUI clamp + tooltip |
| Critical angle | `sin(α) ≤ 1` | Already handled in `run_calculation`; extend to 3D Snell check |

### Solver Robustness
1. **Degenerate geometry** (element directly above focal point → `H = 0`):
   - Newton‑Raphson initial guess handles this (interpolation gives `x_i = x₁`, `y_i = y₁`).
   - Add explicit guard: if `‖p_start[:2] − p_end[:2]‖ < ε`, skip solver, compute direct TOF.
2. **Equal velocities** (`v₁ = v₂`):
   - Quartic coefficient `a = 1 − C² = 0` in 2D (polynomial degenerates to cubic).
   - In 3D Newton solver this is naturally handled — no special case needed, but add a unit test.
3. **Very large focal distances** (plane‑wave limit):
   - Solver must still converge. Test with focal depth = 10 m.
4. **Negative / zero heights**:
   - Guard `height_at_element1 > 0` in `Wedge.__init__`.
5. **Newton convergence failure**:
   - After `max_iter`, fall back to `scipy.optimize.minimize` and log a warning.
   - If fallback also fails, raise a descriptive `RuntimeError` with the element index.
6. **NaN / Inf propagation**:
   - After each solver call, `assert np.isfinite(tof)` before accumulating.

---

## Verification Plan

### Automated Tests

All tests should be runnable via:
```
cd c:\Users\aledd\Documents\Projects\phased_array_calculator\python
python -m pytest tests/ -v
```

*(A `tests/` directory will be created alongside the source.)*

#### 1. Backward‑Compatibility Regression (`test_regression_2d.py`)
Ensures the 3D code path produces **identical** results to the current 2D code for a linear probe.

| Test Case | Setup | Assertion |
|---|---|---|
| `test_delays_match_2d` | 16‑element linear probe, 36° wedge, steel, 45° at 20 mm depth | `np.allclose(delays_3d, delays_2d, atol=1e-12)` |
| `test_interface_points_match_2d` | Same setup | X‑coords match; Y = 0 |
| `test_tof_match_2d` | Same setup | All TOF values identical |

**Method**: Run both `solve_fermat_point` (quartic) and `solve_fermat_point_3d` (Newton) for every element; compare outputs.

#### 2. 3D Symmetry Tests (`test_3d_symmetry.py`)
Validates physical correctness of the new solver.

| Test Case | Setup | Assertion |
|---|---|---|
| `test_on_axis_symmetric_delays` | 4×4 matrix, target at `(0, 0, 30mm)` | Delays symmetric in X *and* Y (mirror symmetry about both axes) |
| `test_skew_shifts_y` | 4×4 matrix, 0° azimuth, 30° skew | Delays **not** symmetric in Y; monotonically shift across passive axis |
| `test_zero_skew_equals_2d` | 4×1 matrix, various angles, skew = 0° | Results identical to pure‑2D (`num_elements_y = 1`) |

#### 3. Solver Convergence Tests (`test_solver_robustness.py`)
Stress‑tests the Newton solver under difficult conditions.

| Test Case | Setup | Assertion |
|---|---|---|
| `test_equal_velocity` | `v1 == v2 = 5900 m/s` | Solver converges; interface point lies on straight‑line path |
| `test_extreme_angle` | 85° beam angle | Solver converges without NaN |
| `test_element_above_focus` | Element at `(0, 0, −10mm)`, focus at `(0, 0, 20mm)` | TOF = `10mm/v1 + 20mm/v2` (direct, no lateral offset) |
| `test_large_focal_distance` | Focus at 10 m depth | Delay profile is near‑linear (plane wave limit) |
| `test_fallback_triggered` | Mock Newton failure (max_iter = 0) | Falls back to `scipy` without error |
| `test_nan_guard` | Inject NaN coordinate | `ValueError` raised cleanly |

#### 4. Export Tests (`test_export_3d.py`)
| Test Case | Assertion |
|---|---|
| `test_csv_has_y_column` | CSV header includes `Global_Y_mm`; values correct |
| `test_mat_has_y_field` | `.mat` dict includes `Global_Y_mm` key |
| `test_m_script_has_y` | `.m` file contains `Global_Y_mm` variable |

### Manual Verification

1. **Linear Probe Smoke Test**
   - Launch the GUI (`python main.py`).
   - Set 16 elements, 0.6 mm pitch, 36° wedge, steel, 45° beam at 50 mm depth.
   - Press *Calculate* → verify ray diagram and delay histogram match existing v0.1.0 output exactly (visually identical plots).

2. **Matrix Probe Smoke Test**
   - Set 8×8 matrix probe, 0.5 mm pitch in both axes.
   - Set 45° azimuth, 0° skew, 30 mm depth.
   - Press *Calculate* → verify:
     - 64 elements shown in results table.
     - Ray projection plots show beams in both X‑Z and Y‑Z views.
     - Delay histogram shows 64 bars.

3. **Skew Steering Visualisation**
   - Same 8×8 setup, change skew to 30°.
   - Verify ray paths visibly shift off‑axis in the Y‑Z projection.
   - Verify delays are **not** symmetric across the passive axis.

4. **Edge‑Case GUI Behaviour**
   - Set `num_elements_y = 1`, verify passive pitch field is greyed out or ignored.
   - Enter a beam angle beyond critical angle → confirm error row appears in table.
   - Enter `num_elements_y = 0` → confirm validation prevents crash.
