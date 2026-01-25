import numpy as np

class Probe:
    """
    Represents a linear phased array probe.
    """
    def __init__(self, num_elements: int, pitch: float, frequency: float = 5e6):
        """
        Args:
            num_elements: Number of elements.
            pitch: Center-to-center distance between elements in meters.
            frequency: Nominal frequency in Hz.
        """
        self.num_elements = num_elements
        self.pitch = pitch
        self.frequency = frequency

    def get_element_of_interest_indices(self):
        return np.arange(self.num_elements)

    def get_element_positions(self, center_at_origin: bool = True) -> np.ndarray:
        """
        Returns the (x, z) coordinates of the elements in the PROBE's local coordinate system.
        The array line is along the x-axis, z is 0.

        Args:
            center_at_origin: If True, the array is centered at x=0. 
                              If False, the first element is at x=0.
        
        Returns:
            np.ndarray: Shape (N, 2) containing (x, z) coordinates.
        """
        # Element indices 0 to N-1
        indices = np.arange(self.num_elements)
        
        # Calculate x positions
        if center_at_origin:
            total_width = (self.num_elements - 1) * self.pitch
            x_positions = indices * self.pitch - (total_width / 2.0)
        else:
            x_positions = indices * self.pitch
            
        z_positions = np.zeros_like(x_positions)
        
        return np.column_stack((x_positions, z_positions))

    def __repr__(self):
        return f"Probe({self.num_elements} els, {self.pitch*1000}mm pitch)"
