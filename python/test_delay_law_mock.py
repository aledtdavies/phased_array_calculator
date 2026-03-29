import sys
import unittest
from unittest.mock import MagicMock

# mock dependencies
np_mock = MagicMock()
sys.modules['numpy'] = np_mock
scipy_mock = MagicMock()
sys.modules['scipy'] = scipy_mock
sys.modules['scipy.optimize'] = MagicMock()

from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw

class TestDelayLawOptimization(unittest.TestCase):
    def test_init_caches_properties(self):
        probe = Probe(num_elements=16, pitch=0.6e-3, frequency=5e6)
        probe.get_active_element_indices = MagicMock(return_value=[0, 1, 2])

        steel = Material(velocity_longitudinal=5900.0, velocity_shear=3240.0)

        wedge = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0, probe_offset_x=0.0)
        mock_transformed = MagicMock()
        wedge.get_transformed_elements = MagicMock(return_value=mock_transformed)

        solver = DelayLaw(probe, wedge, steel)

        wedge.get_transformed_elements.assert_called_once_with(probe)
        probe.get_active_element_indices.assert_called_once()
        self.assertEqual(solver.transformed_elements, mock_transformed)

if __name__ == '__main__':
    unittest.main()
