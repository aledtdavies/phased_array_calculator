import unittest
from unittest.mock import patch
from material import Material
from probe import Probe
from wedge import Wedge
from delay_law import DelayLaw


class TestDelayLawCaching(unittest.TestCase):
    def test_calculate_law_reuses_cached_geometry(self):
        """
        DelayLaw computes element geometry and active indices once at
        construction; calculate_law() must not recompute them on every call
        in a sweep.
        """
        probe = Probe(num_elements=16, pitch=0.6e-3, frequency=5e6)
        wedge = Wedge(angle_degrees=36.0, height_at_element1=15e-3, velocity=2330.0)
        mat = Material(velocity_longitudinal=5920.0, velocity_shear=3240.0)

        with patch.object(wedge, 'get_transformed_elements', wraps=wedge.get_transformed_elements) as spy_elements, \
             patch.object(probe, 'get_active_element_indices', wraps=probe.get_active_element_indices) as spy_indices:
            solver = DelayLaw(probe, wedge, mat)
            for _ in range(5):
                solver.calculate_law(0.01, 0.0, 0.05)

            self.assertEqual(spy_elements.call_count, 1)
            self.assertEqual(spy_indices.call_count, 1)


if __name__ == '__main__':
    unittest.main()
