import numpy as np
from probe import Probe

class Wedge:
    """
    Represents the wedge (prism) between the probe and the component.
    Handles the coordinate transformation from Probe Frame to Global Frame.
    
    Global Frame Convention:
    - Interface plane: Z = 0
    - Component: Z > 0
    - Wedge: Z < 0
    """
    def __init__(self, angle_degrees: float, height_at_element1: float, velocity: float, probe_offset_x: float = 0.0):
        """
        Args:
            angle_degrees: Wedge angle.
            height_at_element1: Vertical distance from Element 1 center to the Interface (z=0).
                                (This means Element 1 Z = -height_at_element1).
            velocity: Longitudinal Velocity of sound in the wedge material (m/s).
                      (Note: Wedge is always treated as L-Wave).
            probe_offset_x: global X position of Element 1.
        """
        self.angle_degrees = angle_degrees
        self.angle_rad = np.radians(angle_degrees)
        self.height_at_element1 = height_at_element1
        self.velocity = velocity
        self.probe_offset_x = probe_offset_x

    def get_transformed_elements(self, probe: Probe) -> np.ndarray:
        """
        Computes the GLOBAL (x, z) coordinates of the probe elements.
        
        Logic:
        1. Get Probe Elements relative to Element 1 (0,0).
        2. Rotate by Wedge Angle.
        3. Translate so Element 1 ends up at (probe_offset_x, -height_at_element1).
        """
        # 1. Get local probe coordinates (First element at 0,0)
        local_coords = probe.get_element_positions(center_at_origin=False)
        local_x = local_coords[:, 0]
        local_z = local_coords[:, 1] # All zero
        
        # 2. Rotate
        # Rotated coordinates:
        c = np.cos(self.angle_rad)
        s = np.sin(self.angle_rad)
        
        # Rotation Matrix to tilt the array line:
        rot_x = local_x * c - local_z * s
        rot_z = -local_x * s - local_z * c
        
        # 3. Translate
        global_x = rot_x + self.probe_offset_x
        global_z = rot_z - self.height_at_element1
        
        return np.column_stack((global_x, global_z))
