import numpy as np

class Probe:
    """
    Represents a linear phased array probe.
    """
    def __init__(self, num_elements: int, pitch: float, frequency: float = 5e6, num_elements_y: int = 1, pitch_y: float = 0.0):
        """
        Args:
            num_elements: Number of elements in the primary (X) axis.
            pitch: Center-to-center distance between elements in X axis (meters).
            frequency: Nominal frequency in Hz.
            num_elements_y: Number of elements in the passive (Y) axis.
            pitch_y: Center-to-center distance between elements in Y axis (meters).
        """
        if num_elements_y > 1 and pitch_y <= 0:
            raise ValueError("pitch_y must be > 0 when num_elements_y > 1")
            
        self.num_elements = num_elements
        self.pitch = pitch
        self.frequency = frequency
        self.num_elements_y = max(1, num_elements_y)
        self.pitch_y = pitch_y

    @property
    def total_elements(self) -> int:
        return self.num_elements * self.num_elements_y

    def get_element_of_interest_indices(self):
        return np.arange(self.total_elements)

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
                 array_separation: float = 0.0):
        super().__init__(num_elements, pitch, frequency, num_elements_y, pitch_y)
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
                          array_separation: float = 0.0) -> Probe:
    """
    Factory function to create the appropriate Probe object.
    """
    if probe_type == "Linear":
        return Probe(num_elements, pitch, freq, 1, 0.0)
    elif probe_type == "Matrix":
        return Probe(num_elements, pitch, freq, num_elements_y, pitch_y)
    elif probe_type == "Dual Linear":
        return DualProbe(num_elements, pitch, freq, 1, 0.0, array_separation)
    elif probe_type == "Dual Matrix":
        return DualProbe(num_elements, pitch, freq, num_elements_y, pitch_y, array_separation)
    else:
        raise ValueError(f"Unknown probe type: {probe_type}")

