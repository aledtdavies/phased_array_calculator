# Focal Point Logic Validation Report

## Executive Summary
The logic in the Phased Array Calculator has been thoroughly reviewed and tested. **The system correctly implements focused beam steering**, ensuring that wavefronts converge at the specified focal point. This results in the expected **curved delay laws**, not linear plane wave delays.

## 1. Theoretical Verification
The core logic resides in `DelayLaw.solve_fermat_point`, which calculates the ray path for **each individual element** to the target point.

### Fermat's Principle
The code solves for the path of minimum time:
$T(u) = \frac{\sqrt{u^2 + h_1^2}}{v_1} + \frac{\sqrt{(H-u)^2 + h_2^2}}{v_2}$

It finds the exact intersection point $u$ on the interface by solving the derivative $dT/du = 0$, which results in a quartic polynomial (4th degree).
The coefficients used in the code match the analytical derivation for this optimization problem.

**Conclusion**: The math is physically correct for focusing energy from multiple sources (elements) to a single point through a refracting interface (wedge/material).

## 2. Implementation Logic
- **Targeting**: The function `calculate_law` accepts a single coordinate `(focal_point_x, focal_point_z)`.
- **Iterative Solution**: It iterates through every element of the probe.
- **Independence**: For each element, it calculates the unique time-of-flight (TOF) to that specific target point.
- **Delay Calculation**: $Delay_i = T_{max} - T_i$.
  - This ensures that pulses from all elements arrive at the target point simultaneously (constructive interference at the focus).

This approach inherently produces a spherical/cylindrical wavefront converging on the target, which requires non-linear (curved) delays. Linear delays (plane waves) would only occur if the target point were set to infinity.

## 3. Empirical Verification
A test script was executed to verify the output delays for a standard configuration:
- **Probe**: 16 elements, 0.5mm pitch.
- **Wedge**: 36° angle, Steel Component.
- **Target**: 45° beam, 20mm focal depth.

### Results
| Check | Outcome |
| :--- | :--- |
| **Delay Profile** | Quadratic Curve (Parabola-like) |
| **Linear Fit Residual** | `6.16e-4` (Poor fit) |
| **Quadratic Fit Residual** | `1.00e-6` (Excellent fit) |

The significant curvature confirms that the calculator is producing **Focused Beams** (converging waves), not Steering-Only (plane waves).

## Recommendation
The logic is correct as implemented. The user can be confident that setting a focal depth in the GUI produces a true focal point with converging wavefronts.
