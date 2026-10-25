import numpy as np
from scipy.optimize import brentq
from material import Material
from probe import Probe
from wedge import Wedge

class DelayLaw:
    """
    Calculates the focal laws (delays) for a given setup.
    """
    def __init__(self, probe: Probe, wedge: Wedge, material: Material):
        self.probe = probe
        self.wedge = wedge
        self.material = material
        self._geometry_cache = None

    def solve_fermat_point(self, p_start, p_end, v1, v2, C2=None):
        """
        Finds the point P(x, 0) on the interface that minimizes travel time 
        from p_start(x1, z1) to p_end(x2, z2).

        Args:
            p_start: (x, z) of element (z usually < 0)
            p_end: (x, z) of focus (z usually > 0)
            v1: velocity in wedge
            v2: velocity in component
            C2: optional pre-calculated squared velocity ratio (v2/v1)**2

        Returns:
            x_int: The x-coordinate of the interface point.
        """
        p_start, p_end = self._validate_ray(p_start, p_end, v1, v2)
        x1, z1 = p_start
        x2, z2 = p_end
        
        # We solve for u = x_int - x1. 
        # So x_int = u + x1.
        # Relative target X: H = x2 - x1.
        H = x2 - x1
        
        # Vertical distances (must be positive for the geometry triangles)
        h1 = abs(z1) # Depth in wedge
        h2 = abs(z2) # Depth in component
        
        # Ratio of velocities
        # Snell's Law: sin1/v1 = sin2/v2
        # Analytical Polynomial derivation:
        # Time T(u) = sqrt(u^2 + h1^2)/v1 + sqrt((H-u)^2 + h2^2)/v2
        # Setting dT/du = 0 and squaring to remove roots leads to a quartic.
        # Coeffs for u based on u = x - x1:
        
        if C2 is None:
            C = v2 / v1
            C2 = C ** 2
        
        # Polynomial: a*u^4 + b*u^3 + c*u^2 + d*u + e = 0
        
        # Derived coeffs:
        # u^4 terms: (1 - C^2)
        a = 1.0 - C2
        
        # u^3 terms: -2H(1 - C2)
        b = -2.0 * H * a
        
        # u^2 terms: (H^2 + h1^2) - C^2(H^2 + h2^2)
        c = (H**2 + h1**2) - C2 * (H**2 + h2**2)
        
        # u^1 terms: -2H * h1^2
        d = -2.0 * H * (h1**2)
        
        # u^0 terms: H^2 * h1^2
        e = (H**2) * (h1**2)
        
        # Solve roots
        roots = np.roots([a, b, c, d, e])
        
        # Filter valid roots
        # 1. Real roots only (allow tiny imaginary noise)
        real_roots = roots[np.isclose(roots.imag, 0)].real
        
        # 2. Check time for each real root to find the Minimum
        min_time = float('inf')
        best_u = None
        
        for u in real_roots:
            
            # Reconstruct global x for this u
            x_candidate = u + x1
            
            # Distances
            d_wedge = np.sqrt((x_candidate - x1)**2 + h1**2)
            d_mat   = np.sqrt((x2 - x_candidate)**2 + h2**2)
            
            t = d_wedge / v1 + d_mat / v2
            
            if t < min_time:
                min_time = t
                best_u = u

        if best_u is None:
            # Fallback (should not happen for physical setups)
            return x1 + H * (h1 / (h1 + h2))
            
        return best_u + x1

    @staticmethod
    def _validate_ray(start, end, v1, v2):
        start, end = np.asarray(start, dtype=float), np.asarray(end, dtype=float)
        if start.shape != end.shape or start.ndim != 1 or start.size not in (2, 3):
            raise ValueError("ray endpoints must both have two or three coordinates")
        if not np.isfinite(start).all() or not np.isfinite(end).all():
            raise ValueError("ray coordinates must be finite")
        if not np.isfinite([v1, v2]).all() or v1 <= 0 or v2 <= 0:
            raise ValueError("wave speeds must be finite and positive")
        if start[-1] > 0 or end[-1] <= 0:
            raise ValueError("source must have z <= 0 and transmitted focus z > 0")
        return start, end

    def _geometry(self):
        # Only values actually used by Probe/Wedge geometry and aperture selection.
        # Public configuration remains mutable; a changed state rebuilds the cache.
        p, w = self.probe, self.wedge
        key = (type(p), p.num_elements, p.num_elements_y, p.pitch, p.pitch_y,
               p.start_element, p.num_active_elements, p.element_order,
               getattr(p, 'array_separation', None), type(w), w.angle_rad,
               w.roof_angle_rad, w.height_at_element1, w.probe_offset_x)
        if self._geometry_cache is None or self._geometry_cache[0] != key:
            elements = w.get_transformed_elements(p)
            active = p.get_active_element_indices().copy()
            self._geometry_cache = (key, elements, p.total_elements, active)
        return self._geometry_cache[1:]

    def aperture_centre(self):
        """Centre of the active sub-aperture, global frame. Focal rules start the central ray here."""
        elements, _, active = self._geometry()
        return elements[active].mean(axis=0)

    def solve_fermat_point_3d(self, p_start, p_end, v1, v2):
        """Planar isotropic Snell ray, reduced to its vertical incidence plane.

        Coordinates are global metres: z<=0 incident medium, z>0 component;
        speeds are m/s. The dimensionless scalar residual is bracketed on [0,1].
        No unconstrained Newton step or unchecked optimiser result is used.
        """
        start, end = self._validate_ray(p_start, p_end, v1, v2)
        delta = end[:2] - start[:2]
        distance = np.linalg.norm(delta)
        if distance == 0:
            return float(start[0]), float(start[1])
        length = max(distance, -start[2], end[2])
        d, h1, h2 = distance/length, -start[2]/length, end[2]/length
        ratio = v1/v2

        def residual(fraction):
            u, remaining = d*fraction, d*(1-fraction)
            incident = 1.0 if h1 == 0 and fraction == 0 else u/np.hypot(u, h1)
            return incident - ratio*remaining/np.hypot(remaining, h2)

        if h1 == 0 and residual(0) >= 0:
            fraction = 0.0
        else:
            fraction = brentq(residual, 0.0, 1.0, xtol=np.nextafter(0., 1.),
                              rtol=8*np.finfo(float).eps)
            if abs(residual(fraction)) > 1e-10:
                raise ArithmeticError("Snell solve did not satisfy its residual")
        point = start[:2] + fraction*delta
        return float(point[0]), float(point[1])

    def calculate_law(self, focal_point_x: float, focal_point_y: float, focal_point_z: float, wave_type: str = 'longitudinal'):
        """
        Computes the delay law for a single focal point.
        
        Args:
            focal_point_x, focal_point_y, focal_point_z: Target coordinates.
            wave_type: 'longitudinal' or 'shear'.
        
        Returns dictionary with:
            'delays': np.ndarray (seconds)
            'tof': np.ndarray (seconds)
            'interface_points': np.ndarray (N, 3)
        """
        # 1. Get Element Positions in Global Frame
        target = np.array([focal_point_x, focal_point_y, focal_point_z], dtype=float)
        if not np.isfinite(target).all() or target[2] <= 0:
            raise ValueError("transmitted focus must be finite with z > 0")
        if not isinstance(wave_type, str) or wave_type.lower() not in ('longitudinal', 'shear'):
            raise ValueError("wave_type must be longitudinal or shear")
        elements, num_els, active_indices = self._geometry()
        
        tofs = np.full(num_els, np.nan)
        interface_points = np.zeros((num_els, 3))
        
        target = np.array([focal_point_x, focal_point_y, focal_point_z])
        
        # Velocities
        v_wedge = self.wedge.velocity
        
        if wave_type.lower() == 'shear':
            if self.material.velocity_shear is None:
                raise ValueError("shear mode requires a shear wave speed")
            v_mat = self.material.velocity_shear
        else:
            v_mat = self.material.velocity_longitudinal
        self._validate_ray(elements[0], target, v_wedge, v_mat)

        C2_precalc = (v_mat / v_wedge) ** 2
        
        # A pure 2D (X-Z plane) solve is only valid if every element AND the
        # focal point actually lie at y=0. num_elements_y==1 is not sufficient:
        # DualProbe sub-arrays are offset to y=+/-array_separation/2 even when
        # num_elements_y==1, so their elements are off the X-Z plane.
        has_y = np.any(np.abs(elements[:, 1]) > 1e-9) or abs(focal_point_y) > 1e-9
        is_2d = not has_y
        
        # 2. Iterate active elements only and solve path
        for i in active_indices:
            # Element pos
            p_el = elements[i]
            
            if is_2d:
                p_start_2d = np.array([p_el[0], p_el[2]])
                target_2d = np.array([target[0], target[2]])
                p_int_x = self.solve_fermat_point(p_start_2d, target_2d, v_wedge, v_mat, C2=C2_precalc)
                p_int = np.array([p_int_x, 0.0, 0.0])
            else:
                p_int_x, p_int_y = self.solve_fermat_point_3d(p_el, target, v_wedge, v_mat)
                p_int = np.array([p_int_x, p_int_y, 0.0]) # Interface is z=0
            
            interface_points[i] = p_int
            
            # Calculate Time
            dist_wedge = np.linalg.norm(p_el - p_int)
            dist_mat = np.linalg.norm(target - p_int)
            
            tofs[i] = dist_wedge / v_wedge + dist_mat / v_mat
            
            # Guard against NaN/Inf
            assert np.isfinite(tofs[i]), f"Calculated TOF is not finite for element {i}"
            
        # 3. Compute Delays (only over active elements)
        active_tofs = tofs[active_indices]
        max_tof = np.max(active_tofs)
        
        delays = np.full(num_els, np.nan)
        delays[active_indices] = max_tof - tofs[active_indices]
        
        return {
            'delays': delays,
            'tof': tofs,
            'interface_points': interface_points,
            'focal_point': target,
            'velocity_used': v_mat,
            'active_indices': active_indices.copy()
        }

    def export_element_positions(self, filename: str):
        """
        Exports the global (x, y, z) coordinates of the probe elements to a CSV or MAT file.
        """
        import os
        elements = self.wedge.get_transformed_elements(self.probe)
        print(f"Exporting element positions to {filename}...")
        
        coords_mm = elements * 1000.0
        
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        if ext == '.mat':
            import scipy.io
            data = {
                'ElementID': np.arange(1, len(coords_mm) + 1),
                'Global_X_mm': coords_mm[:, 0],
                'Global_Y_mm': coords_mm[:, 1],
                'Global_Z_mm': coords_mm[:, 2],
                'Coordinates_mm': coords_mm
            }
            scipy.io.savemat(filename, data)
        elif ext == '.m':
            with open(filename, 'w') as f:
                f.write("% Element Positions (mm)\n")
                f.write(f"ElementID = [ {', '.join(map(str, range(1, len(coords_mm)+1)))} ];\n")
                f.write(f"Global_X_mm = [ {', '.join(map(str, coords_mm[:, 0]))} ];\n")
                f.write(f"Global_Y_mm = [ {', '.join(map(str, coords_mm[:, 1]))} ];\n")
                f.write(f"Global_Z_mm = [ {', '.join(map(str, coords_mm[:, 2]))} ];\n")
                
                f.write("Coordinates_mm = [\n")
                for x, y, z in coords_mm:
                    f.write(f"    {x}, {y}, {z};\n")
                f.write("];\n")
        else:
            import csv
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['ElementID', 'Global_X_mm', 'Global_Y_mm', 'Global_Z_mm'])
                for i, (x, y, z) in enumerate(coords_mm):
                    writer.writerow([i + 1, x, y, z])
