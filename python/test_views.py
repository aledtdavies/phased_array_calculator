"""Element numbering, sub-aperture mapping and headless rendering of the views."""
import unittest

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
import numpy as np

from delay_law import DelayLaw
from material import Material
from probe import create_probe_assembly
from scene import (decimate_rays, draw_aperture_maps, draw_projection, draw_scene_3d,
                   user_element_numbers)
from wedge import Wedge


def dual_matrix(order, start=1, active=0):
    return create_probe_assembly("Dual Matrix", 4, 1e-3, 5e6, num_elements_y=2, pitch_y=1e-3,
                                 array_separation=10e-3, start_element=start,
                                 num_active_elements=active, element_order=order)


class TestNumbering(unittest.TestCase):
    def test_row_first_second_array_stays_in_second_array(self):
        p = dual_matrix("row-first", start=9, active=8)
        np.testing.assert_array_equal(p.get_active_element_indices(), np.arange(8, 16))
        p = dual_matrix("row-first", start=7, active=4)   # spans both arrays
        el = p.get_element_positions()
        idx = p.get_active_element_indices()
        self.assertEqual(sorted(el[idx, 1] > 0), [False, False, True, True])

    def test_row_first_runs_along_x(self):
        p = create_probe_assembly("Matrix", 4, 1e-3, 5e6, num_elements_y=3, pitch_y=1e-3,
                                  start_element=1, num_active_elements=4, element_order="row-first")
        el = p.get_element_positions()[p.get_active_element_indices()]
        self.assertEqual(len(set(el[:, 1])), 1)          # one row: Y fixed
        self.assertEqual(len(set(el[:, 0])), 4)          # X varies
        p.element_order = "column-first"
        p.num_active_elements = 3
        el = p.get_element_positions()[p.get_active_element_indices()]
        self.assertEqual(len(set(el[:, 0])), 1)          # one column: X fixed

    def test_user_numbers_agree_with_active_selection(self):
        for order in ("column-first", "row-first"):
            for start in range(1, 17):
                p = dual_matrix(order, start=start, active=3)
                nums = user_element_numbers(p)
                act = p.get_active_element_indices()
                want = np.arange(start, min(start + 3, 17))
                np.testing.assert_array_equal(np.sort(nums[act]), want, err_msg=f"{order} {start}")
                self.assertEqual(sorted(nums), list(range(1, 17)))


class TestDecimation(unittest.TestCase):
    def test_keeps_ends_and_limit(self):
        act = np.arange(5, 205)
        d = decimate_rays(act, 48)
        self.assertLessEqual(d.size, 48)
        self.assertEqual((d[0], d[-1]), (5, 204))
        np.testing.assert_array_equal(decimate_rays(act[:10], 48), act[:10])


class TestRendering(unittest.TestCase):
    """Every view draws without error for each probe type with a sub-aperture."""

    def setups(self):
        steel = Material(5920, 3240)
        yield create_probe_assembly("Linear", 32, 0.6e-3, 5e6, start_element=9,
                                    num_active_elements=16), Wedge(36, 0.01, 2330)
        yield create_probe_assembly("Matrix", 8, 1e-3, 5e6, num_elements_y=4, pitch_y=1e-3,
                                    start_element=3, num_active_elements=20,
                                    element_order="row-first"), Wedge(20, 0.008, 2330)
        yield create_probe_assembly("Dual Linear", 16, 0.5e-3, 5e6, array_separation=8e-3,
                                    start_element=5, num_active_elements=20), \
            Wedge(15, 0.006, 2330, roof_angle_degrees=3)
        yield dual_matrix("column-first", start=2, active=12), Wedge(0, 0.0, 2330)   # contact

    def test_views(self):
        for probe, wedge in self.setups():
            s = DelayLaw(probe, wedge, Material(5920, 3240))
            cx, cy, _ = s.aperture_centre()
            fps = [(cx + 0.02, cy + 0.002, 0.03), (cx + 0.03, cy, 0.03)]
            laws = [s.calculate_law(*fp) for fp in fps]
            get = lambda i: (laws[i]["interface_points"] * 1e3, np.array(fps[i]) * 1e3)
            with self.subTest(probe=repr(probe)):
                fig = Figure()
                draw_projection(fig.add_subplot(121), s, get, [0, 1], 0, "longitudinal", True, 40)
                draw_projection(fig.add_subplot(122), s, get, [0], 1, "longitudinal", False)
                fig.canvas.draw()
                fig = Figure()
                draw_scene_3d(fig.add_subplot(111, projection="3d"), s, get(0),
                              np.array(fps) * 1e3, 0, "longitudinal", component_thickness_mm=40)
                fig.canvas.draw()
                if probe.num_elements_y > 1:
                    fig = Figure()
                    axes = draw_aperture_maps(fig, probe, laws[0]["delays"] * 1e6)
                    self.assertEqual(len(axes), probe.total_elements // (probe.num_elements * probe.num_elements_y))
                    fig.canvas.draw()


if __name__ == "__main__":
    unittest.main()
