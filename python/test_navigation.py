"""Law navigation model (navigation.py): slider mapping, pinned laws, bounds."""
import unittest

from navigation import LawNavigation


def law(angle, skew, y=0.0):
    return {"angle": angle, "skew": skew, "fx": 0.01, "fy": y, "fz": 0.02}


class TestLawNavigation(unittest.TestCase):
    def test_sliders_pick_first_law_of_a_pair(self):
        n = LawNavigation()
        n.set_laws([law(40, 0, -1), law(40, 0, 1), law(50, 0), law(40, 10)])
        self.assertEqual((n.angle_values, n.skew_values), ([40, 50], [0, 10]))
        self.assertEqual(n.from_sliders(0, 0), 0)
        self.assertEqual(n.from_sliders(1, 0), 2)
        self.assertEqual(n.from_sliders(0, 1), 3)

    def test_law_sharing_a_pair_stays_selected(self):
        n = LawNavigation()
        n.set_laws([law(40, 0, -1), law(40, 0, 1), law(50, 0)])
        self.assertEqual(n.select(1), (0, 0))
        self.assertEqual(n.from_sliders(0, 0), 1)      # sliders agree: law 1 kept
        self.assertEqual(n.from_sliders(1, 0), 2)      # moved away: pin dropped
        self.assertEqual(n.from_sliders(0, 0), 0)

    def test_missing_pair_falls_back_to_the_angle(self):
        """Sound-path Y sweeps: skews depend on the angle, so pairs are sparse."""
        n = LawNavigation()
        n.set_laws([law(40, 20), law(50, 10)])
        self.assertEqual(n.from_sliders(0, 0), 0)      # (40, 10) absent: first law at 40
        self.assertEqual(n.from_sliders(1, 1), 1)      # (50, 20) absent: first law at 50

    def test_new_set_and_bounds(self):
        n = LawNavigation()
        n.set_laws([law(a, 0) for a in range(40, 71)])
        n.select(25)
        n.set_laws([law(40, 20), law(50, 10)])
        self.assertEqual(n.current, 0)
        self.assertEqual(n.from_sliders(99, 99), 1)    # clamped
        self.assertEqual(n.step(1), (0, 1))            # wraps 1 -> 0
        self.assertEqual(n.current, 0)

    def test_empty(self):
        n = LawNavigation()
        self.assertEqual(n.from_sliders(3, 2), 0)
        self.assertEqual(n.select(4), (0, 0))
        self.assertEqual(n.readout(), ("", "", ""))


if __name__ == "__main__":
    unittest.main()
