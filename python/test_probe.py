import unittest
import numpy as np
from probe import DualProbe, Probe

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


class TestProbeValidation(unittest.TestCase):
    def test_invalid_pitch_y_zero_raises(self):
        """num_elements_y > 1 with pitch_y == 0 should raise ValueError."""
        with self.assertRaisesRegex(ValueError, "pitch_y must be > 0 when num_elements_y > 1"):
            Probe(num_elements=10, pitch=0.1, num_elements_y=2, pitch_y=0.0)

    def test_invalid_pitch_y_negative_raises(self):
        """num_elements_y > 1 with pitch_y < 0 should raise ValueError."""
        with self.assertRaisesRegex(ValueError, "pitch_y must be > 0 when num_elements_y > 1"):
            Probe(num_elements=10, pitch=0.1, num_elements_y=2, pitch_y=-0.5)

    def test_valid_pitch_y_succeeds(self):
        """num_elements_y > 1 with pitch_y > 0 should succeed."""
        probe = Probe(num_elements=10, pitch=0.1, num_elements_y=2, pitch_y=0.1)
        self.assertEqual(probe.num_elements_y, 2)
        self.assertEqual(probe.pitch_y, 0.1)

    def test_num_elements_y_one_allows_zero_pitch_y(self):
        """num_elements_y == 1 should not require a positive pitch_y."""
        probe = Probe(num_elements=10, pitch=0.1, num_elements_y=1, pitch_y=0.0)
        self.assertEqual(probe.num_elements_y, 1)
        self.assertEqual(probe.pitch_y, 0.0)


if __name__ == '__main__':
    unittest.main()
