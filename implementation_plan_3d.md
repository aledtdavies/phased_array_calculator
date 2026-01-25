# Implementation Plan - 3D Matrix Array Extension

# Goal Description
Extend the current 2D Phased Array Calculator to support **3D Geometry** and **2D Matrix Arrays**.
This will allow the user to:
1.  Define a Matrix Probe (Elements in X and Y).
2.  Steer beams in both **Azimuth** (Primary Axis) and **Elevation/Skew** (Secondary Axis).
3.  Calculate delay laws and ray paths in a full 3D volume.

## User Review Required
> [!IMPORTANT]
> **Performance Consideration**: The 3D ray tracing (Fermat's Principle on a surface) is computationally more expensive than the 2D case. We will need to implement an efficient iterative solver (Newton-Raphson or similar) using `numpy` since an analytical quartic solution does not easily exist for the general 3D case with arbitrary element positions.

## Proposed Changes

### 1. Probe & Geometry (`probe.py`, `wedge.py`)
Extend the coordinate system to include the Y-axis (Passive/Elevation axis).

#### [MODIFY] [probe.py](file:///c:/Users/IVC Analysis/ProjectsAG/phased_array_calculator/python/probe.py)
- **Class**: `Probe`
  - Add `num_elements_y` and `pitch_y` arguments.
  - Defaults for Linear Array: `num_elements_y = 1`, `pitch_y = 0`.
- **Method**: `get_element_positions`
  - Generate a 2D grid of coordinates $(x, y, 0)$.
  - Return shape: `(N_x * N_y, 3)`.

#### [MODIFY] [wedge.py](file:///c:/Users/IVC Analysis/ProjectsAG/phased_array_calculator/python/wedge.py)
- **Method**: `get_transformed_elements`
  - Update rotation logic to handle the 3rd dimension.
  - For a simple wedge (squint=0), the Y-coordinates pass through untransformed, but the rotation must effectively handle `(x, y, z)` vectors.

### 2. 3D Ray Tracing Solver (`delay_law.py`)
Replace the 2D polynomial solver with a generalized 3D solver.

#### [MODIFY] [delay_law.py](file:///c:/Users/IVC Analysis/ProjectsAG/phased_array_calculator/python/delay_law.py)
- **Method**: `solve_fermat_point_3d(p_start, p_end, v1, v2)`
  - **Inputs**: `p_start=(x,y,z)`, `p_end=(x,y,z)`.
  - **Logic**: Find the point $P(x_i, y_i, 0)$ on the interface that minimizes total time.
  - **Algorithm**:
    - Since $z_{interface}=0$, the problem reduces to finding $(x_i, y_i)$.
    - Use a **Newton-Raphson** optimizer or a bounded scalar minimizer if reduced to a single parameter (not easy in 3D).
    - A simple Gradient Descent with momentum or Newton step is usually sufficient and fast for this convex problem.
- **Method**: `calculate_law`
  - Accept `target=(x, y, z)`.
  - Loop over all elements (N_total) and solve 3D path.

### 3. Application & GUI (`app.py`, `panels.py`)
Add controls for the new dimensions.

#### [MODIFY] [panels.py](file:///c:/Users/IVC Analysis/ProjectsAG/phased_array_calculator/python/panels.py)
- **ProbePanel**: Add inputs for "Analysis Axis Elements" vs "Passive Axis Elements" (or X/Y).
- **ScanPanel**: Add input for **Skew Angle** (Elevation steering).

#### [MODIFY] [app.py](file:///c:/Users/IVC Analysis/ProjectsAG/phased_array_calculator/python/app.py)
- Update `run_calculation` to:
  - Generate 3D target coordinates based on Azimuth And Skew angles.
  - `fx = R * sin(Az) * cos(El)` ... (Standard Spherical to Cartesian conversion).
  - Pass 3D target to solver.

#### [MODIFY] [plotting.py](file:///c:/Users/IVC Analysis/ProjectsAG/phased_array_calculator/python/plotting.py)
- Update `PlottingPanel` to support 3D visualization.
- Option 1: **3D Scatter/Line Plot** (using `mpl_toolkits.mplot3d`).
- Option 2: **Projections** (Side View X-Z, Top View X-Y).
  - *Recommendation*: Projections are often more useful for engineering. A 3D view can be added as a tab.

## Verification Plan

### Automated Tests
1. **Regression Test**: Ensure 1D Linear Array (Elements_Y=1) produces identical results to the current 2D code (within float tolerance).
2. **Symmetry Test**: For a Matrix Array, focusing at $(0, 0, Z)$ should produce symmetric delays in both X and Y directions.

### Manual Verification
1. **Linear Probe Check**: Run the existing `verify_delays.py` script logic (checking the new 3D solver with Y=0) to confirm it matches exact analytical 2D results.
2. **Skew Steering**: Visualize a beam steered at 45° Skew. Verify that the delays shift across the Y-axis.
