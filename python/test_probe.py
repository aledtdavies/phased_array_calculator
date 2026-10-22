import unittest
import numpy as np
from probe import DualProbe

class TestDualProbe(unittest.TestCase):
    def test_dual_probe_array_separation_center_origin(self):
        """Test array separation in Y when center_at_origin is True."""
        num_elements = 16
        pitch = 0.5e-3
        array_separation = 5.0e-3

        probe = DualProbe(num_elements=num_elements, pitch=pitch, array_separation=array_separation)

        # Default center_at_origin=True
        coords = probe.get_element_positions(center_at_origin=True)

        # Total elements should be 2 * num_elements
        self.assertEqual(len(coords), 2 * num_elements)

        # Split into sub-arrays
        coords1 = coords[:num_elements]
        coords2 = coords[num_elements:]

        # The separation in Y between corresponding elements should be exactly array_separation
        y_diff = coords2[:, 1] - coords1[:, 1]

        np.testing.assert_allclose(y_diff, array_separation, err_msg="Y offset does not match array_separation")

        # Check symmetric around 0 for Y when center_at_origin=True
        np.testing.assert_allclose(coords1[:, 1], -array_separation / 2.0)
        np.testing.assert_allclose(coords2[:, 1], array_separation / 2.0)

    def test_dual_probe_array_separation_not_center_origin(self):
        """Test array separation in Y when center_at_origin is False."""
        num_elements = 16
        pitch = 0.5e-3
        array_separation = 5.0e-3

        probe = DualProbe(num_elements=num_elements, pitch=pitch, array_separation=array_separation)

        # Test with center_at_origin=False
        coords = probe.get_element_positions(center_at_origin=False)

        # Split into sub-arrays
        coords1 = coords[:num_elements]
        coords2 = coords[num_elements:]

        # The separation in Y between corresponding elements should be exactly array_separation
        y_diff = coords2[:, 1] - coords1[:, 1]

        np.testing.assert_allclose(y_diff, array_separation, err_msg="Y offset does not match array_separation when center_at_origin=False")

        # Check symmetric around 0 for Y when center_at_origin=False
        # For a 1D base array, base_coords[:, 1] is 0, so even after subtracting mean, it's 0.
        np.testing.assert_allclose(coords1[:, 1], -array_separation / 2.0)
        np.testing.assert_allclose(coords2[:, 1], array_separation / 2.0)

    def test_dual_matrix_probe_array_separation(self):
        """Test array separation for a Dual Matrix probe."""
        num_elements = 8
        num_elements_y = 4
        pitch = 0.5e-3
        pitch_y = 0.6e-3
        array_separation = 10.0e-3

        probe = DualProbe(
            num_elements=num_elements,
            pitch=pitch,
            num_elements_y=num_elements_y,
            pitch_y=pitch_y,
            array_separation=array_separation
        )

        coords = probe.get_element_positions()

        elements_per_subarray = num_elements * num_elements_y

        coords1 = coords[:elements_per_subarray]
        coords2 = coords[elements_per_subarray:]

        # The separation in Y between corresponding elements should be exactly array_separation
        y_diff = coords2[:, 1] - coords1[:, 1]

        np.testing.assert_allclose(y_diff, array_separation, err_msg="Y offset does not match array_separation for dual matrix probe")

if __name__ == '__main__':
    unittest.main()
