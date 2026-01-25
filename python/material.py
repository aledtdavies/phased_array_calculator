class Material:
    """
    Represents an ultrasonic material with defined velocities.
    """
    def __init__(self, velocity_longitudinal: float, velocity_shear: float = None):
        """
        Args:
            velocity_longitudinal: L-wave velocity in m/s.
            velocity_shear: S-wave velocity in m/s (optional).
        """
        self.velocity_longitudinal = velocity_longitudinal
        self.velocity_shear = velocity_shear

    def __repr__(self):
        return f"Material(vL={self.velocity_longitudinal}, vS={self.velocity_shear})"
