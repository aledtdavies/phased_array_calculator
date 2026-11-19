"""
Focal-target rules: where each law of an angle (and skew) sweep is focused.

Frame and conventions (SI, the calculator's global frame):
- X along the wedge (the beam's facing direction at zero skew), Y across, Z down into the
  component; Z = 0 is the wedge-component interface.
- Refracted angle beta: from the inward normal (+Z) towards the facing direction, positive
  towards +X at zero skew.
- Skew: rotation about +Z (Z down) of the beam's horizontal direction, from +X towards +Y.
  The beam direction is (sin b cos s, sin b sin s, cos b).
- The central ray starts at the centre of the active sub-aperture (DelayLaw.aperture_centre),
  crosses the wedge at the incident angle alpha given by Snell's law
  (sin alpha = v_wedge / v_component * sin beta), and enters the component a horizontal
  distance h * tan(alpha) from the aperture centre along the skew direction, h being the
  centre's height above the interface. Both legs are rotated by the skew.

Focus modes (value in metres):
- constant-depth:  focus at depth Z = value on the central ray.
- vertical-line:   focus where the central ray meets the vertical line X = value.
- sound-path:      focus at a distance `value` along the central ray from its entry point.

Y modes (matrix probes):
- from-skew:  Y follows the central ray (the default).
- fixed:      Y = the given value for every law (constant-depth and vertical-line only;
              it over-constrains sound-path, so it is refused there).
- sweep:      one law per Y value. In sound-path mode the skew is not taken from the skew
              list: it is solved for each Y value so that the focus lies on the central ray
              at that Y (the effective skew is reported); the skew list is used once.

Each requested law gives a Target, or a Refused with a reason; nothing is silently replaced or
dropped (in a Y sweep, one result per skew and Y; in a sound-path Y sweep, one per Y):
- 'critical angle':          sin(alpha) > 1;
- 'focus not below surface': the focus would have Z <= 0;
- 'beam parallel to line':   vertical-line mode with the central ray parallel to the line
                             (beta = 0, or skew 90 degrees);
- 'Y out of reach':          sound-path Y sweep with |Y offset| greater than the path's
                             horizontal reach (with no reach, any offset from the
                             aperture centre's Y).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Union

import numpy as np

FOCUS_MODES = ("constant-depth", "vertical-line", "sound-path")
Y_MODES = ("from-skew", "fixed", "sweep")
_PARALLEL_TOL = 1e-9
_ZERO_REACH = 1e-12     # m: horizontal reach treated as none (sound-path Y sweep)


@dataclass(frozen=True)
class Target:
    """A focal law's target. Angles in degrees, coordinates in metres (global frame)."""
    angle_deg: float
    skew_deg: float
    x: float
    y: float
    z: float

    @property
    def point(self):
        return (self.x, self.y, self.z)


@dataclass(frozen=True)
class Refused:
    """A law that cannot be formed: angle (and skew, None when not applicable) and why."""
    angle_deg: float
    skew_deg: Optional[float]
    reason: str


def swept_values(start: float, end: float, step: float, single: float) -> np.ndarray:
    """inclusive_range(start, end, step), or [single] when step <= 0 (no sweep)."""
    if step > 0:
        vals = np.arange(start, end + step, step)
        if vals[-1] < end:
            vals = np.append(vals, end)
        return vals
    return np.array([single])


def angle_sweep(start: float, end: float, step: float) -> np.ndarray:
    """Angles from start to end inclusive (the GUI's angle sweep)."""
    angles = np.arange(start, end + step, step)
    if step > 0 and angles[-1] < end:
        angles = np.append(angles, end)
    return angles


def component_speed(material, wave: str) -> float:
    """The component wave speed for 'longitudinal' or 'shear'; refuses a missing shear speed."""
    w = wave.lower() if isinstance(wave, str) else wave
    if w == "longitudinal":
        return material.velocity_longitudinal
    if w == "shear":
        if not material.velocity_shear:
            raise ValueError("shear mode requires a shear wave speed")
        return material.velocity_shear
    raise ValueError("wave must be 'longitudinal' or 'shear'")


def base_focal(mode: str, value: float, beta_rad: float, x_int: float):
    """
    Un-skewed focal primitives for one angle: (fz, f_primary, fx). f_primary is the
    horizontal distance from the entry point along the beam's plan direction; fx is the
    vertical line's X (vertical-line mode only, else None). fz is None when the beam is
    parallel to the vertical line.
    """
    if mode == "constant-depth":
        return value, value * np.tan(beta_rad), None
    if mode == "vertical-line":
        if abs(np.tan(beta_rad)) < _PARALLEL_TOL:
            return None, 0.0, value
        f_primary = value - x_int
        return f_primary / np.tan(beta_rad), f_primary, value
    if mode == "sound-path":
        return value * np.cos(beta_rad), value * np.sin(beta_rad), None
    raise ValueError(f"unknown focus mode {mode!r}")


def skewed_focal(mode, skew_rad, x_int, fx, beta_rad, fz, f_primary, center_y, y_values,
                 y_mode, entry_offset=0.0):
    """
    (x, [y, ...], z) for one skew, from base_focal's primitives. Both legs of the central
    ray are rotated about the aperture centre: the entry point moves to
    (centre_x + e cos s, centre_y + e sin s), e = entry_offset. z is None when the
    vertical line is parallel to the skewed beam.
    """
    x_int += entry_offset * (np.cos(skew_rad) - 1)
    center_y += entry_offset * np.sin(skew_rad)
    if mode == "constant-depth":
        x = x_int + f_primary * np.cos(skew_rad)
        ys = list(y_values) if y_values is not None else [center_y + f_primary * np.sin(skew_rad)]
        return x, ys, fz
    if mode == "vertical-line":
        cos_s = np.cos(skew_rad)
        if abs(cos_s) < _PARALLEL_TOL or abs(np.tan(beta_rad)) < _PARALLEL_TOL:
            return fx, [], None
        f3 = (fx - x_int) / cos_s
        z = f3 / np.tan(beta_rad)
        ys = list(y_values) if y_values is not None else [center_y + f3 * np.sin(skew_rad)]
        return fx, ys, z
    # sound-path (a Y sweep there is handled by focal_targets)
    x = x_int + f_primary * np.cos(skew_rad)
    return x, [center_y + f_primary * np.sin(skew_rad)], fz


def focal_targets(solver, mode: str, value: float, angles_deg: Sequence[float],
                  skews_deg: Sequence[float] = (0.0,), wave: str = "longitudinal",
                  y_mode: str = "from-skew",
                  y_values: Optional[Sequence[float]] = None) -> list[Union[Target, Refused]]:
    """
    Targets for every angle x skew (x Y value) of a sweep, in sweep order: for each angle,
    each skew, each Y. See the module docstring for modes and refusals. Lengths in metres,
    angles in degrees.
    """
    if mode not in FOCUS_MODES:
        raise ValueError(f"focus mode must be one of {FOCUS_MODES}")
    if y_mode not in Y_MODES:
        raise ValueError(f"Y mode must be one of {Y_MODES}")
    if y_mode == "fixed" and mode == "sound-path":
        raise ValueError("a fixed Y over-constrains the sound-path focus")
    if y_mode in ("fixed", "sweep") and (y_values is None or len(y_values) == 0):
        raise ValueError(f"Y mode {y_mode!r} needs Y values")
    if y_mode == "fixed" and len(y_values) != 1:
        raise ValueError("a fixed Y takes one value")
    y_list = None if y_mode == "from-skew" else [float(y) for y in y_values]

    v_wedge = solver.wedge.velocity
    v_mat = component_speed(solver.material, wave)
    cx, cy, cz = solver.aperture_centre()
    h = abs(cz)
    path_y_sweep = mode == "sound-path" and y_mode == "sweep"
    # Each refusal stands for one requested law: per skew, times each Y in a Y sweep; in a
    # sound-path Y sweep, per Y with no skew (the skew list is not used there).
    per_skew = len(y_list) if y_mode == "sweep" else 1

    def refuse_all(ang, reason):
        if path_y_sweep:
            return [Refused(float(ang), None, reason) for _ in y_list]
        return [Refused(float(ang), float(s), reason) for s in skews_deg for _ in range(per_skew)]

    out: list[Union[Target, Refused]] = []

    for ang in angles_deg:
        beta = np.radians(ang)
        sin_alpha = v_wedge / v_mat * np.sin(beta)
        if abs(sin_alpha) > 1.0:
            out += refuse_all(ang, "critical angle")
            continue
        alpha = np.arcsin(sin_alpha)
        entry = h * np.tan(alpha)
        x_int = cx + entry
        fz, f_primary, fx = base_focal(mode, value, beta, x_int)
        # Depth and path foci do not depend on skew, so a negative depth refuses every skew
        # here. A vertical-line focus does (the entry point rotates with skew): it is
        # checked per skew below.
        if mode != "vertical-line" and fz < 0:
            out += refuse_all(ang, "focus not below surface")
            continue

        for s in skews_deg:
            if path_y_sweep:
                # Skew solved per Y: the focus lies on the central ray at that Y.
                reach = entry + f_primary
                if not fz > 0:
                    out += [Refused(float(ang), None, "focus not below surface") for _ in y_list]
                    break
                for y in y_list:
                    if abs(reach) <= _ZERO_REACH:
                        # No horizontal reach (a 0 degree beam from the centre): only the
                        # aperture centre's Y lies on the central ray.
                        val = 0.0 if abs(y - cy) <= _ZERO_REACH else np.inf
                    else:
                        val = (y - cy) / reach
                    if abs(val) > 1.0:
                        out.append(Refused(float(ang), None, "Y out of reach"))
                        continue
                    eff = np.arcsin(val)
                    out.append(Target(float(ang), float(np.degrees(eff)),
                                      float(cx + reach * np.cos(eff)), float(y), float(fz)))
                break   # the skew list is not used in this mode
            x, ys, z = skewed_focal(mode, np.radians(s), x_int, fx, beta, fz, f_primary, cy,
                                    y_list, y_mode, entry_offset=entry)
            if z is None:
                out += [Refused(float(ang), float(s), "beam parallel to line")] * per_skew
                continue
            if not z > 0:
                out += [Refused(float(ang), float(s), "focus not below surface")] * per_skew
                continue
            out += [Target(float(ang), float(s), float(x), float(y), float(z)) for y in ys]
    return out
