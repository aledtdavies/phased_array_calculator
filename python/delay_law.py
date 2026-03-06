import numpy as np
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

    def solve_fermat_point(self, p_start, p_end, v1, v2):
        """
        Finds the point P(x, 0) on the interface that minimizes travel time 
        from p_start(x1, z1) to p_end(x2, z2).

        Args:
            p_start: (x, z) of element (z usually < 0)
            p_end: (x, z) of focus (z usually > 0)
            v1: velocity in wedge
            v2: velocity in component

        Returns:
            x_int: The x-coordinate of the interface point.
        """
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

    def calculate_law(self, focal_point_x: float, focal_point_z: float, wave_type: str = 'longitudinal'):
        """
        Computes the delay law for a single focal point.
        
        Args:
            focal_point_x, focal_point_z: Target coordinates.
            wave_type: 'longitudinal' or 'shear'.
        
        Returns dictionary with:
            'delays': np.ndarray (seconds)
            'tof': np.ndarray (seconds)
            'interface_points': np.ndarray (N, 2)
        """
        # 1. Get Element Positions in Global Frame
        elements = self.wedge.get_transformed_elements(self.probe)
        
        num_els = self.probe.num_elements
        tofs = np.zeros(num_els)
        interface_points = np.zeros((num_els, 2))
        
        target = np.array([focal_point_x, focal_point_z])
        
        # Velocities
        v_wedge = self.wedge.velocity
        
        if wave_type.lower() == 'shear' and self.material.velocity_shear:
            v_mat = self.material.velocity_shear
        else:
            v_mat = self.material.velocity_longitudinal
        
        # 2. Iterate elements and solve path
        for i in range(num_els):
            # Element pos
            p_el = elements[i]
            
            p_int_x = self.solve_fermat_point(p_el, target, v_wedge, v_mat)
            p_int = np.array([p_int_x, 0.0]) # Interface is z=0
            
            interface_points[i] = p_int
            
            # Calculate Time
            dist_wedge = np.linalg.norm(p_el - p_int)
            dist_mat = np.linalg.norm(target - p_int)
            
            tofs[i] = dist_wedge / v_wedge + dist_mat / v_mat
            
        # 3. Compute Delays
        max_tof = np.max(tofs)
        delays = max_tof - tofs
        
        return {
            'delays': delays,
            'tof': tofs,
            'interface_points': interface_points,
            'focal_point': target,
            'velocity_used': v_mat
        }

    def export_element_positions(self, filename: str):
        """
        Exports the global (x, z) coordinates of the probe elements to a CSV file.
        """
        import csv
        elements = self.wedge.get_transformed_elements(self.probe)
        
        print(f"Exporting element positions to {filename}...")
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ElementID', 'Global_X_mm', 'Global_Z_mm'])
            for i, (x, z) in enumerate(elements):
                writer.writerow([i + 1, x * 1000, z * 1000])
