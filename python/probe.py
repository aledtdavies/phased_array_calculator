import numpy as np

class Probe:
    """
    Represents a linear phased array probe.
    """
    def __init__(self, num_elements: int, pitch: float, frequency: float = 5e6, num_elements_y: int = 1, pitch_y: float = 0.0,
                 start_element: int = 1, num_active_elements: int = 0, element_order: str = 'column-first'):
        """
        Args:
            num_elements: Number of elements in the primary (X) axis.
            pitch: Center-to-center distance between elements in X axis (meters).
            frequency: Nominal frequency in Hz.
            num_elements_y: Number of elements in the passive (Y) axis.
            pitch_y: Center-to-center distance between elements in Y axis (meters).
            start_element: First active element (1-indexed).
            num_active_elements: Number of active elements (0 = all).
            element_order: 'column-first' or 'row-first' (matrix numbering convention).
        """
        if num_elements_y > 1 and pitch_y <= 0:
            raise ValueError("pitch_y must be > 0 when num_elements_y > 1")
            
        self.num_elements = num_elements
        self.pitch = pitch
        self.frequency = frequency
        self.num_elements_y = max(1, num_elements_y)
        self.pitch_y = pitch_y
        self.start_element = max(1, start_element)
        self.num_active_elements = max(0, num_active_elements)
        self.element_order = element_order

    @property
    def total_elements(self) -> int:
        return self.num_elements * self.num_elements_y

    def get_element_of_interest_indices(self):
        return self.get_active_element_indices()

    def get_active_element_indices(self):
        """
        Returns 0-based indices of active elements in the sub-aperture,
        mapped back to internal (column-first) storage order.
        """
        total = self.total_elements
        num_active = self.num_active_elements if self.num_active_elements > 0 else total
        start_0 = self.start_element - 1  # Convert to 0-based
        
        # Clip to valid range
        start_0 = max(0, min(start_0, total - 1))
        end_0 = min(start_0 + num_active, total)
        
        # Generate logical indices in the user's numbering convention
        user_indices = np.arange(start_0, end_0)
        
        if self.element_order == 'row-first' and self.num_elements_y > 1:
            # User numbering is row-first (Y varies fastest):
            # user_idx -> (row, col) where row = user_idx % num_elements_y,
            #                                col = user_idx // num_elements_y
            # Internal storage is column-first (X varies fastest via meshgrid 'ij'):
            # internal_idx = col * num_elements_y + row  (same as ix * Ny + iy)
            # But since internal is already col-first: internal_idx = ix * Ny + iy
            # From row-first user_idx: iy = user_idx % num_elements_y
            #                          ix = user_idx // num_elements_y
            # So internal_idx = ix * Ny + iy  (which equals user_idx) only if ordering matches.
            # Actually internal (meshgrid 'ij') order: ix varies first.
            # internal_idx for (ix, iy) = ix * Ny + iy    (X varies fastest)
            # row-first user_idx for (ix, iy) = iy * Nx + ix  (Y varies fastest)
            # So: given user_idx, iy = user_idx // Nx, ix = user_idx % Nx
            #     internal_idx = ix * Ny + iy
            Nx = self.num_elements
            Ny = self.num_elements_y
            iy = user_indices // Nx
            ix = user_indices % Nx
            internal_indices = ix * Ny + iy
            return np.sort(internal_indices)
        else:
            # column-first: user numbering matches internal storage order
            return user_indices

    def get_element_positions(self, center_at_origin: bool = True) -> np.ndarray:
        """
        Returns the (x, y, z) coordinates of the elements in the PROBE's local coordinate system.
        The array plane is the x-y plane, z is 0.

        Args:
            center_at_origin: If True, the array is centered at (x=0, y=0).
                              If False, the first element is at (x=0, y=0).
        
        Returns:
            np.ndarray: Shape (N_x * N_y, 3) containing (x, y, z) coordinates.
        """
        indices_x = np.arange(self.num_elements)
        indices_y = np.arange(self.num_elements_y)
        
        if center_at_origin:
            total_width_x = (self.num_elements - 1) * self.pitch
            x_positions = indices_x * self.pitch - (total_width_x / 2.0)
            
            total_width_y = (self.num_elements_y - 1) * self.pitch_y
            y_positions = indices_y * self.pitch_y - (total_width_y / 2.0)
        else:
            x_positions = indices_x * self.pitch
            y_positions = indices_y * self.pitch_y
            
        # Create a grid of x and y coordinates
        X, Y = np.meshgrid(x_positions, y_positions, indexing='ij')
        
        # Flatten the grids
        x_flat = X.flatten()
        y_flat = Y.flatten()
        z_flat = np.zeros_like(x_flat)
        
        return np.column_stack((x_flat, y_flat, z_flat))

    def __repr__(self):
        if self.num_elements_y > 1:
            return f"{self.__class__.__name__}({self.num_elements}x{self.num_elements_y} els, {self.pitch*1000}x{self.pitch_y*1000}mm pitch)"
        return f"{self.__class__.__name__}({self.num_elements} els, {self.pitch*1000}mm pitch)"

class DualProbe(Probe):
    """
    Represents a dual phased array probe (two identical sub-arrays).
    """
    def __init__(self, num_elements: int, pitch: float, frequency: float = 5e6, 
                 num_elements_y: int = 1, pitch_y: float = 0.0,
                 array_separation: float = 0.0,
                 start_element: int = 1, num_active_elements: int = 0, element_order: str = 'column-first'):
        super().__init__(num_elements, pitch, frequency, num_elements_y, pitch_y,
                         start_element, num_active_elements, element_order)
        self.array_separation = array_separation

    @property
    def total_elements(self) -> int:
        return 2 * super().total_elements

    def get_element_positions(self, center_at_origin: bool = True) -> np.ndarray:
        """
        Returns the (x, y, z) coordinates of both sub-arrays.
        Sub-array 1 is offset by -separation/2 in Y.
        Sub-array 2 is offset by +separation/2 in Y.
        """
        # Get coordinates for a single sub-array
        base_coords = super().get_element_positions(center_at_origin)
        
        # Sub-array 1
        coords1 = base_coords.copy()
        coords1[:, 1] -= self.array_separation / 2.0
        
        # Sub-array 2
        coords2 = base_coords.copy()
        coords2[:, 1] += self.array_separation / 2.0
        
        # Concatenate
        return np.vstack((coords1, coords2))

def create_probe_assembly(probe_type: str, num_elements: int, pitch: float, freq: float,
                          num_elements_y: int = 1, pitch_y: float = 0.0,
                          array_separation: float = 0.0,
                          start_element: int = 1, num_active_elements: int = 0,
                          element_order: str = 'column-first') -> Probe:
    """
    Factory function to create the appropriate Probe object.
    """
    if probe_type == "Linear":
        return Probe(num_elements, pitch, freq, 1, 0.0, start_element, num_active_elements, element_order)
    elif probe_type == "Matrix":
        return Probe(num_elements, pitch, freq, num_elements_y, pitch_y, start_element, num_active_elements, element_order)
    elif probe_type == "Dual Linear":
        return DualProbe(num_elements, pitch, freq, 1, 0.0, array_separation, start_element, num_active_elements, element_order)
    elif probe_type == "Dual Matrix":
        return DualProbe(num_elements, pitch, freq, num_elements_y, pitch_y, array_separation, start_element, num_active_elements, element_order)
    else:
        raise ValueError(f"Unknown probe type: {probe_type}")

