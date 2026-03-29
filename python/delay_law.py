import numpy as np
from scipy.optimize import minimize
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

        # Cache properties to avoid repeated coordinate calculations and index fetching during the calculate_law loop
        self.transformed_elements = self.wedge.get_transformed_elements(self.probe)
        self.num_els = self.probe.total_elements
        self.active_indices = self.probe.get_active_element_indices()

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

    def solve_fermat_point_3d(self, p_start, p_end, v1, v2):
        """
        Finds the point P(x_i, y_i, 0) on the interface that minimizes travel time 
        from p_start(x1, y1, z1) to p_end(x2, y2, z2).

        Args:
            p_start: (x, y, z) of element (z usually < 0)
            p_end: (x, y, z) of focus (z usually > 0)
            v1: velocity in wedge
            v2: velocity in component

        Returns:
            (x_i, y_i): The interface coordinates.
        """
        x1, y1, z1 = p_start
        x2, y2, z2 = p_end
        
        # Guard for degenerate geometry (element directly above/below focus)
        if np.linalg.norm(p_start[:2] - p_end[:2]) < 1e-9:
            return x1, y1

        # Initial guess via linear interpolation
        h1 = abs(z1)
        h2 = abs(z2)
        ratio = h1 / (h1 + h2) if (h1 + h2) > 0 else 0.5
        x0 = x1 + (x2 - x1) * ratio
        y0 = y1 + (y2 - y1) * ratio
        u0 = np.array([x0, y0])

        def time_func(u):
            dx1, dy1 = u[0] - x1, u[1] - y1
            dx2, dy2 = x2 - u[0], y2 - u[1]
            d1 = np.sqrt(dx1**2 + dy1**2 + z1**2)
            d2 = np.sqrt(dx2**2 + dy2**2 + z2**2)
            return d1 / v1 + d2 / v2

        def grad_func(u):
            dx1, dy1 = u[0] - x1, u[1] - y1
            dx2, dy2 = x2 - u[0], y2 - u[1]
            d1 = np.sqrt(dx1**2 + dy1**2 + z1**2)
            d2 = np.sqrt(dx2**2 + dy2**2 + z2**2)
            
            gx = dx1 / (v1 * d1) - dx2 / (v2 * d2)
            gy = dy1 / (v1 * d1) - dy2 / (v2 * d2)
            return np.array([gx, gy])
            
        def hessian_func(u):
            dx1, dy1 = u[0] - x1, u[1] - y1
            dx2, dy2 = x2 - u[0], y2 - u[1]
            
            d1_2 = dx1**2 + dy1**2 + z1**2 + 1e-12
            d2_2 = dx2**2 + dy2**2 + z2**2 + 1e-12
            d1_3 = d1_2 * np.sqrt(d1_2)
            d2_3 = d2_2 * np.sqrt(d2_2)
            
            hxx = (d1_2 - dx1**2) / (v1 * d1_3) + (d2_2 - dx2**2) / (v2 * d2_3)
            hyy = (d1_2 - dy1**2) / (v1 * d1_3) + (d2_2 - dy2**2) / (v2 * d2_3)
            hxy = -dx1 * dy1 / (v1 * d1_3) - dx2 * dy2 / (v2 * d2_3)
            
            return np.array([[hxx, hxy], [hxy, hyy]])

        # Newton-Raphson
        u = u0
        max_iter = 20
        tol = 1e-12
        for _ in range(max_iter):
            g = grad_func(u)
            if np.linalg.norm(g) < tol:
                return float(u[0]), float(u[1])
            H = hessian_func(u)
            try:
                du = np.linalg.solve(H, -g)
                u = u + du
            except np.linalg.LinAlgError:
                break
                
        # Fallback to scipy if NR fails to converge
        res = minimize(time_func, u0, method='L-BFGS-B', jac=grad_func)
        return float(res.x[0]), float(res.x[1])

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
        elements = self.transformed_elements
        
        num_els = self.num_els
        active_indices = self.active_indices
        
        tofs = np.full(num_els, np.nan)
        interface_points = np.zeros((num_els, 3))
        
        target = np.array([focal_point_x, focal_point_y, focal_point_z])
        
        # Velocities
        v_wedge = self.wedge.velocity
        
        if wave_type.lower() == 'shear' and self.material.velocity_shear:
            v_mat = self.material.velocity_shear
        else:
            v_mat = self.material.velocity_longitudinal
        
        is_2d = (self.probe.num_elements_y == 1 and abs(focal_point_y) < 1e-9)
        
        # 2. Iterate active elements only and solve path
        for i in active_indices:
            # Element pos
            p_el = elements[i]
            
            if is_2d:
                p_start_2d = np.array([p_el[0], p_el[2]])
                target_2d = np.array([target[0], target[2]])
                p_int_x = self.solve_fermat_point(p_start_2d, target_2d, v_wedge, v_mat)
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
            'active_indices': active_indices
        }

    def export_element_positions(self, filename: str):
        """
        Exports the global (x, y, z) coordinates of the probe elements to a CSV or MAT file.
        """
        import os
        elements = self.transformed_elements
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
