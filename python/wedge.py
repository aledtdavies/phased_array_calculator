import numpy as np
from probe import Probe, DualProbe

class Wedge:
    """
    Represents the wedge (prism) between the probe and the component.
    Handles the coordinate transformation from Probe Frame to Global Frame.
    
    Global Frame Convention:
    - Interface plane: Z = 0
    - Component: Z > 0
    - Wedge: Z < 0
    """
    def __init__(self, angle_degrees: float, height_at_element1: float, velocity: float, 
                 probe_offset_x: float = 0.0, roof_angle_degrees: float = 0.0):
        """
        Args:
            angle_degrees: Wedge angle.
            height_at_element1: Vertical distance from Element 1 center to the Interface (z=0).
                                (This means Element 1 Z = -height_at_element1).
            velocity: Longitudinal Velocity of sound in the wedge material (m/s).
                      (Note: Wedge is always treated as L-Wave).
            probe_offset_x: global X position of Element 1.
            roof_angle_degrees: Angle tilting the array in the Y-Z plane.
        """
        self.angle_degrees = angle_degrees
        self.angle_rad = np.radians(angle_degrees)
        self.height_at_element1 = height_at_element1
        self.velocity = velocity
        self.probe_offset_x = probe_offset_x
        self.roof_angle_degrees = roof_angle_degrees
        self.roof_angle_rad = np.radians(roof_angle_degrees)

    def get_transformed_elements(self, probe: Probe) -> np.ndarray:
        """
        Computes the GLOBAL (x, y, z) coordinates of the probe elements.
        
        Logic:
        1. Get Probe Elements relative to Element 1 (0,0,0).
        2. Rotate by Wedge Angle around the Y axis.
        3. Translate so Element 1 ends up at (probe_offset_x, 0, -height_at_element1).
        """
        # 1. Get local probe coordinates (First element at 0,0,0)
        local_coords = probe.get_element_positions(center_at_origin=False)
        local_x = local_coords[:, 0]
        local_y = local_coords[:, 1]
        local_z = local_coords[:, 2] # All zero
        
        # 2. Rotate (around Y axis - Squint/Pitch)
        # Rotated coordinates:
        c1 = np.cos(self.angle_rad)
        s1 = np.sin(self.angle_rad)
        
        # Rotation Matrix to tilt the array plane (pitch):
        rot_x1 = local_x * c1 - local_z * s1
        rot_y1 = local_y
        rot_z1 = -local_x * s1 - local_z * c1
        
        # 3. Rotate (around X axis - Roof/Roll)
        if isinstance(probe, DualProbe):
            # For dual probes, enforce symmetric roof: TX = -roof, RX = +roof.
            n_half = probe.total_elements // 2
            roof_angles = np.concatenate((
                np.full(n_half, -self.roof_angle_rad),
                np.full(n_half, self.roof_angle_rad)
            ))
            c2 = np.cos(roof_angles)
            s2 = np.sin(roof_angles)
        else:
            c2 = np.cos(self.roof_angle_rad)
            s2 = np.sin(self.roof_angle_rad)

        rot_x2 = rot_x1
        rot_y2 = rot_y1 * c2 - rot_z1 * s2
        rot_z2 = rot_y1 * s2 + rot_z1 * c2
        
        # 4. Translate
        global_x = rot_x2 + self.probe_offset_x
        global_y = rot_y2
        global_z = rot_z2 - self.height_at_element1
        
        return np.column_stack((global_x, global_y, global_z))
