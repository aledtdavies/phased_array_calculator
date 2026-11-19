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
        # Local probe coordinates (first element at 0,0,0)
        local_coords = probe.get_element_positions(center_at_origin=False)
        return self.transform_points(local_coords, self.roof_signs(probe))

    def roof_signs(self, probe: Probe) -> np.ndarray:
        """
        Per element (internal order), the sign applied to the roof angle: +1 for a single
        array; for dual probes the symmetric roof, -1 for the Tx array and +1 for Rx.
        """
        if isinstance(probe, DualProbe):
            n_half = probe.total_elements // 2
            return np.concatenate((np.full(n_half, -1.0), np.full(n_half, 1.0)))
        return np.ones(probe.total_elements)

    def transform_points(self, local_coords: np.ndarray, roof_sign) -> np.ndarray:
        """
        Probe frame -> global frame for any points (e.g. element corners): local (x, y, z)
        with element 1's centre at the origin and the array plane z = 0; roof_sign per point
        (see roof_signs) or a scalar. Rotation by the wedge angle about Y, then the roof
        about X, then the translation of element 1 to (probe_offset_x, 0, -height_at_element1).
        Metres.
        """
        local_x = local_coords[:, 0]
        local_y = local_coords[:, 1]
        local_z = local_coords[:, 2]

        # 1. Rotate (around Y axis - Squint/Pitch): tilt the array plane
        c1 = np.cos(self.angle_rad)
        s1 = np.sin(self.angle_rad)
        rot_x1 = local_x * c1 - local_z * s1
        rot_y1 = local_y
        rot_z1 = -local_x * s1 - local_z * c1

        # 2. Rotate (around X axis - Roof/Roll); dual probes: TX = -roof, RX = +roof
        roof_angles = np.asarray(roof_sign, dtype=float) * self.roof_angle_rad
        c2 = np.cos(roof_angles)
        s2 = np.sin(roof_angles)
        rot_x2 = rot_x1
        rot_y2 = rot_y1 * c2 - rot_z1 * s2
        rot_z2 = rot_y1 * s2 + rot_z1 * c2

        # 3. Translate
        global_x = rot_x2 + self.probe_offset_x
        global_y = rot_y2
        global_z = rot_z2 - self.height_at_element1

        return np.column_stack((global_x, global_y, global_z))
