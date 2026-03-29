import sys
from unittest.mock import MagicMock

# mock dependencies
np_mock = MagicMock()
sys.modules['numpy'] = np_mock
scipy_mock = MagicMock()
sys.modules['scipy'] = scipy_mock
sys.modules['scipy.optimize'] = MagicMock()

# Now we can import our modules
from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw

def benchmark():
    probe = Probe(num_elements=64, pitch=0.6e-3, frequency=5e6)
    probe.get_active_element_indices = MagicMock(return_value=list(range(64)))

    steel = Material(velocity_longitudinal=5900.0, velocity_shear=3240.0)

    wedge = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0, probe_offset_x=0.0)
    wedge.get_transformed_elements = MagicMock()

    solver = DelayLaw(probe, wedge, steel)

    # Mocking internal methods used during calculate_law to avoid actual computations
    solver.solve_fermat_point = MagicMock(return_value=0.0)
    solver.solve_fermat_point_3d = MagicMock(return_value=(0.0, 0.0))

    # Simulate a sector scan calculation loop
    for angle in range(30, 71, 1):
        try:
            solver.calculate_law(0.05, 0.0, 0.05)
        except Exception as e:
            pass

    print(f"Total calls to get_transformed_elements: {wedge.get_transformed_elements.call_count}")
    print(f"Total calls to get_active_element_indices: {probe.get_active_element_indices.call_count}")

if __name__ == "__main__":
    benchmark()
