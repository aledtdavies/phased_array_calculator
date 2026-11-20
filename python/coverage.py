"""
Beam coverage of a sweep: each law's central ray, carried through the component with skips
(reflections at the backwall and the scanning surface), and the fans the sweep's central rays
sweep out leg by leg.

Frame and units: the calculator's global frame, metres; X along the wedge, Y across, Z down
into the component (Z = 0 the scanning surface, Z = T the backwall of a flat plate).

The central ray of a law runs from the active aperture's centre to its focus, refracted at the
interface: its entry point is the Fermat (Snell) point of that path, and inside the component
it continues along entry -> focus. This holds for any focus (a sweep law, a Y-sweep target or
a dragged focus), so coverage never depends on how the focus was chosen.

Skips are specular reflections in a flat plate of thickness T: at each wall the Z component of
the direction reverses. ASSUMPTION (shown with the views): the wave keeps its mode at every
reflection. Mode conversion (L <-> T at a wall) and beam spread are not modelled; coverage
shows where the central rays go, not the extent of the beam.
"""
from __future__ import annotations

import numpy as np

from focal_rules import component_speed

MODE_ASSUMPTION = "Skips: specular reflection, same mode at each wall (no mode conversion); central rays only"


def central_ray(solver, focus, wave="longitudinal"):
    """
    (entry point, unit direction) of the central ray to focus (m) from the active aperture's
    centre: entry on Z = 0 by Snell's law between the wedge and component speeds.
    """
    focus = np.asarray(focus, dtype=float)
    if not focus[2] > 0:
        raise ValueError("the focus must be below the surface (Z > 0)")
    centre = solver.aperture_centre()
    ex, ey = solver.solve_fermat_point_3d(centre, focus, solver.wedge.velocity,
                                          component_speed(solver.material, wave.lower()))
    entry = np.array([ex, ey, 0.0])
    d = focus - entry
    return entry, d / np.linalg.norm(d)


def skip_path(entry, direction, thickness, legs):
    """
    The central ray's path through a flat plate: [entry, backwall hit, surface hit, ...], legs
    + 1 points. Leg 1 runs to the backwall, leg 2 back to the surface, and so on. Refuses a ray
    that does not go down into the plate or runs parallel to the walls.
    """
    if not thickness > 0:
        raise ValueError("skips need the component thickness (> 0)")
    if legs < 1:
        raise ValueError("at least one leg")
    p = np.asarray(entry, dtype=float)
    d = np.asarray(direction, dtype=float)
    if not d[2] > 1e-12:
        raise ValueError("the central ray must travel down into the component")
    pts = [p]
    for _ in range(legs):
        wall = thickness if d[2] > 0 else 0.0
        t = (wall - p[2]) / d[2]
        p = p + t * d
        pts.append(p)
        d = d * np.array([1.0, 1.0, -1.0])
    return np.array(pts)


def sweep_paths(solver, foci, thickness, legs, wave="longitudinal"):
    """Each focus's central-ray path (see skip_path), in order: a list of (legs + 1, 3) arrays."""
    out = []
    for f in foci:
        entry, d = central_ray(solver, f, wave)
        out.append(skip_path(entry, d, thickness, legs))
    return out


def fans(results, paths):
    """
    Coverage fans: for each leg, the quads between neighbouring laws' central rays. Laws are
    grouped into fans that share a skew (rounded to 1e-6 degrees) and ordered by refracted angle,
    so a skew sweep gives one fan per skew, never quads across skews. Returns
    {leg: [(4, 3) quad, ...]} with legs numbered from 1.
    """
    groups = {}
    for i, r in enumerate(results):
        groups.setdefault(round(float(r.get("skew") or 0.0), 6), []).append(i)
    legs = len(paths[0]) - 1 if paths else 0
    out = {leg: [] for leg in range(1, legs + 1)}
    for members in groups.values():
        members = sorted(members, key=lambda i: (results[i]["angle"], results[i].get("fy", 0.0)))
        for a, b in zip(members[:-1], members[1:]):
            if results[a]["angle"] == results[b]["angle"]:
                continue        # Y-sweep targets at one angle: no fan between them
            pa, pb = paths[a], paths[b]
            for leg in range(1, legs + 1):
                out[leg].append(np.array([pa[leg - 1], pa[leg], pb[leg], pb[leg - 1]]))
    return out


class SweepCoverage:
    """
    A calculation's coverage: every law's central-ray path (legs from the entry point) and the
    fans between them, computed once; path_for() solves a dragged focus on demand.
    """

    def __init__(self, solver, results, foci, thickness, legs, wave="longitudinal"):
        self.solver, self.thickness, self.legs, self.wave = solver, float(thickness), int(legs), wave
        self.paths = sweep_paths(solver, foci, self.thickness, self.legs, wave)
        self.fans = fans(results, self.paths)

    def path_for(self, focus):
        entry, d = central_ray(self.solver, focus, self.wave)
        return skip_path(entry, d, self.thickness, self.legs)
