"""
The pyqtgraph 2D views (plan step 4): item reuse per law, geometry from the scene model,
element selection linked across tabs, delay-map cells, and the dragged focus.
"""
import os
import sys
import unittest

import numpy as np

HEADLESS = sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
os.environ.setdefault("QT_API", "pyside6")
try:
    if HEADLESS:
        raise ImportError("no display")
    from qtpy import QtWidgets
    import pyqtgraph
    import pyvistaqt  # noqa: F401
    HAVE_QT = True
except Exception:
    HAVE_QT = False

DUAL = {"probe_type": "Dual Matrix", "num_elements": 4, "num_elements_y": 3, "pitch_mm": 1.0, "pitch_y_mm": 1.5}
LINEAR = {"probe_type": "Linear", "num_elements": 16, "pitch_mm": 0.6}


class _WindowCase(unittest.TestCase):
    """A Qt main window per test (hidden), and a helper to run a calculation."""
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        import qt_app
        self.win = qt_app.MainWindow()
        self.win.info = self.win.warn = lambda *a: None
        self.errors = []
        self.win.error = lambda *a: self.errors.append(a)

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        self.qapp.processEvents()

    def calc(self, probe, wedge=None, sub=None, scan=None):
        w = self.win
        w.probe_panel.set_values(probe)
        if wedge:
            w.wedge_panel.set_values(wedge)
        if sub:
            w.sub_aperture_panel.set_values(sub)
        w.scan_panel.set_values(dict({"focus_mode": "Constant Depth", "param_val": 20, "start_angle": 40,
                                      "end_angle": 60, "step_angle": 5}, **(scan or {})))
        w.run_calculation()
        self.assertEqual(self.errors, [])
        return w


@unittest.skipUnless(HAVE_QT, "PySide6/pyqtgraph/pyvistaqt not installed, or no display")
class Views2D(_WindowCase):
    def test_items_reused_per_law_and_match_the_scene(self):
        from scene_model import build_scene
        w = self.calc(DUAL, {"array_sep_mm": 10, "roof_angle_deg": 3},
                      {"start_element": 3, "num_active_elements": 18, "element_order": "row-first"})
        tab = w.plot_tab
        counts = [len(p.items()) for p in (tab.xz, tab.yz)]
        for law in range(len(w.last_results)):
            tab.show_law(law)
            self.assertEqual([len(p.items()) for p in (tab.xz, tab.yz)], counts)   # data updated, nothing added
            scene = build_scene(tab.solver, tab._get_law_data, [law])
            for plot in (tab.xz, tab.yz):
                d = plot.dim
                for a, item in plot.env_items.items():
                    segs = scene.find("envelope-ray", law=law, array=a)
                    x, y = item.getData()
                    if segs:
                        c = np.vstack([p.coords for p in segs])
                        np.testing.assert_allclose(x, c[:, d])
                        np.testing.assert_allclose(y, c[:, 2])
                    else:
                        self.assertEqual(len(x or []), 0)
                f = np.asarray(w.last_results[law]["fx"]), np.asarray(w.last_results[law]["fz"])
                if d == 0:
                    self.assertAlmostEqual(plot.focus.pos().x(), float(f[0]) * 1e3, places=9)
                self.assertAlmostEqual(plot.focus.pos().y(), float(f[1]) * 1e3, places=9)
        tab.chk_all.setChecked(True)
        self.assertGreater(len(tab.xz.all_items), 0)
        tab.chk_all.setChecked(False)
        self.assertEqual(tab.xz.all_items, [])

    def test_linear_hides_the_yz_view(self):
        w = self.calc(LINEAR)
        self.assertFalse(w.plot_tab.yz.isVisibleTo(w.plot_tab))
        w = self.calc(DUAL)
        self.assertTrue(w.plot_tab.yz.isVisibleTo(w.plot_tab))

    def test_element_selection_is_linked_across_tabs(self):
        w = self.calc(DUAL, {"array_sep_mm": 10}, {"element_order": "column-first", "start_element": 1,
                                                   "num_active_elements": 0})
        # a click on an X-Z element marker
        import pyqtgraph as pg
        scatter = [it for it in w.plot_tab.xz.setup_items if isinstance(it, pg.ScatterPlotItem)][0]
        pts = scatter.points()
        scatter.sigClicked.emit(scatter, [pts[2]], None)
        idx = int(pts[2].data())
        for tab in w.law_tabs():
            self.assertEqual(tab.selected_element, idx, type(tab).__name__)
        self.assertEqual(w.scene3d_tab.picked, idx)
        el = w.plot_tab.solver.wedge.get_transformed_elements(w.plot_tab.solver.probe)[idx] * 1e3
        np.testing.assert_allclose(w.plot_tab.xz.pick.getData()[0], [el[0]])
        # a 3D pick selects it in the 2D views
        w.scene3d_tab.pick_element(5)
        w.scene3d_tab.element_selected.emit(5)
        self.assertEqual(w.plot_tab.selected_element, 5)
        self.assertEqual(w.hist_tab.selected_element, 5)

    def test_delay_map_cells_map_to_elements(self):
        from scene_model import user_element_numbers
        for order in ("column-first", "row-first"):
            with self.subTest(order):
                w = self.calc(DUAL, {"array_sep_mm": 10}, {"element_order": order, "start_element": 3,
                                                           "num_active_elements": 18})
                tab = w.hist_tab
                nx, ny, per = tab.items["shape"]
                numbers = user_element_numbers(tab.solver.probe)
                delays = np.asarray(tab.current_result()["delays_us"])
                for b, img in enumerate(tab.items["images"]):
                    grid = img.image
                    for ix in range(nx):
                        for iy in range(ny):
                            idx = b * per + ix * ny + iy
                            v = grid[ix, iy]
                            self.assertTrue((np.isnan(v) and np.isnan(delays[idx])) or v == delays[idx])
                            self.assertEqual(tab.items["texts"][b][ix * ny + iy].toPlainText(), str(numbers[idx]))
                for img in tab.items["images"]:                   # cell (ix, iy) spans ix+0.5..ix+1.5
                    r = img.mapRectToParent(img.boundingRect())
                    self.assertEqual((r.x(), r.y(), r.width(), r.height()), (0.5, 0.5, nx, ny))
                tab.highlight_element(per + 2 * ny + 1)          # Rx array, X index 3, Y index 2
                r = tab.items["picks"][1]
                self.assertTrue(r.isVisible())
                self.assertEqual((r.rect().x(), r.rect().y()), (2.5, 1.5))

    def test_dragged_focus_solves_live_in_every_tab(self):
        w = self.calc(LINEAR, sub={"start_element": 5, "num_active_elements": 8})
        tab = w.plot_tab
        tab.show_law(2)
        y = float(tab.current_focal()[1])
        tab.xz.focus.setPos(30.0, 15.0)           # as a drag does: sigPositionChanged from the item
        self.qapp.processEvents()
        want = w.plot_tab.solver.calculate_law(0.030, y, 0.015)
        for t in w.law_tabs():
            self.assertIsNotNone(t.custom, type(t).__name__)
            np.testing.assert_allclose(t.current_result()["delays_us"], want["delays"] * 1e6)
            np.testing.assert_allclose(t.current_focal(), (0.030, y, 0.015))
        self.assertIn("Dragged focus", tab.lbl_law.text())
        bars = w.hist_tab.items["bars"]
        np.testing.assert_allclose(bars.opts["height"], want["delays"][5 - 1:5 - 1 + 8] * 1e6)
        self.assertEqual(len(w.table_rows()), len(w.last_results))       # the sweep is unchanged
        tab.xz.focus.setPos(30.0, -2.0)           # above the surface: refused, the custom law stays
        self.assertIn("below the surface", w.statusBar().currentMessage())
        np.testing.assert_allclose(tab.current_focal(), (0.030, y, 0.015))
        tab.step_law(1)                           # back to the sweep
        self.assertIsNone(tab.custom)
        self.assertEqual(tab.current_idx, 3)


class _Click:
    """A scene click event as pyqtgraph's scene delivers it (only scenePos is read)."""

    def __init__(self, pos):
        self._pos = pos

    def scenePos(self):
        return self._pos


@unittest.skipUnless(HAVE_QT, "PySide6/pyqtgraph/pyvistaqt not installed, or no display")
class ReviewFixes(_WindowCase):
    """Review of PR #27."""

    def test_leaving_a_dragged_focus_returns_every_tab_to_the_sweep(self):
        for how in ("slider", "step", "play"):
            with self.subTest(how):
                w = self.calc(LINEAR)
                tab = w.plot_tab
                tab.show_law(2)
                tab.xz.focus.setPos(30.0, 15.0)
                self.assertTrue(all(t.custom is not None for t in w.law_tabs()))
                if how == "slider":
                    tab.slider.setValue(tab.slider.value() + 1)
                elif how == "step":
                    tab.step_law(1)
                else:
                    tab.toggle_play()
                    tab.animate()
                    tab.toggle_play()
                idx = tab.current_idx
                for t in w.law_tabs():
                    self.assertIsNone(t.custom, (how, type(t).__name__))
                    self.assertEqual(t.current_idx, idx, (how, type(t).__name__))
                    np.testing.assert_allclose(t.current_focal(), t.focal_points[idx])

    def test_one_delay_click_handler_through_rebuilds(self):
        w = self.calc(LINEAR)
        selected = []
        w.hist_tab.element_selected.connect(selected.append)
        for probe in (dict(LINEAR, num_elements=16), DUAL, dict(LINEAR, num_elements=4), DUAL,
                      dict(DUAL, num_elements=2, num_elements_y=2)):
            self.calc(probe, {"array_sep_mm": 10})
            tab = w.hist_tab
            tab.refresh_plot()
            n = tab.solver.probe.total_elements
            if "bars" in tab.items:
                plot = tab.items["plot"]
                target = plot.vb.mapViewToScene(pyqtgraph.QtCore.QPointF(n, 0.01))
                want = n - 1
            else:
                nx, ny, per = tab.items["shape"]
                plot = tab.items["plots"][-1]
                target = plot.vb.mapViewToScene(pyqtgraph.QtCore.QPointF(nx, ny))
                want = (len(tab.items["plots"]) - 1) * per + (nx - 1) * ny + (ny - 1)
            before = len(selected)
            tab.view.scene().sigMouseClicked.emit(_Click(target))
            self.assertEqual(selected[before:], [want], probe)        # exactly one, valid, current
            self.assertLess(want, n)

    def test_selection_while_the_delay_layout_is_stale(self):
        """Delays shown for a small dual matrix, then hidden while a larger one is calculated."""
        w = self.win
        w.resize(1000, 700)
        w.show()
        self.calc(DUAL, {"array_sep_mm": 10})
        w.tabs.setCurrentIndex(2)                               # Delays built for 4 x 3 x 2
        self.qapp.processEvents()
        w.tabs.setCurrentIndex(0)                               # Ray Tracing in front
        self.qapp.processEvents()
        self.calc(dict(DUAL, num_elements=16, num_elements_y=4), {"array_sep_mm": 10})
        self.assertEqual(w.hist_tab.items["shape"], (4, 3, 12))  # still the old layout (deferred)
        w.select_element(100)                                   # a new element: no IndexError
        self.assertEqual(w.hist_tab.selected_element, 100)
        w.tabs.setCurrentIndex(2)                               # shown: rebuilt, selection applied
        self.qapp.processEvents()
        nx, ny, per = w.hist_tab.items["shape"]
        self.assertEqual((nx, ny), (16, 4))
        block, local = divmod(100, per)
        ix, iy = divmod(local, ny)
        r = w.hist_tab.items["picks"][block]
        self.assertTrue(r.isVisible())
        self.assertEqual((r.rect().x(), r.rect().y()), (ix + 0.5, iy + 0.5))
        w.tabs.setCurrentIndex(3)
        self.qapp.processEvents()
        self.assertEqual(w.scene3d_tab.picked, 100)
        self.assertIn("Element", w.scene3d_tab.lbl_pick.text())

    def test_refused_drag_puts_the_marker_back(self):
        w = self.calc(LINEAR)
        tab = w.plot_tab
        tab.xz.focus.setPos(30.0, 15.0)
        tab.xz.focus.setPos(32.0, -3.0)                         # above the surface: refused
        f = tab.current_focal() * 1e3
        self.assertAlmostEqual(tab.xz.focus.pos().x(), f[0], places=9)
        self.assertAlmostEqual(tab.xz.focus.pos().y(), f[2], places=9)
        self.assertEqual((round(f[0], 9), round(f[2], 9)), (30.0, 15.0))
        for t in w.law_tabs():
            np.testing.assert_allclose(t.current_focal() * 1e3, f)


@unittest.skipUnless(HAVE_QT, "PySide6/pyqtgraph/pyvistaqt not installed, or no display")
class ShownWindow(unittest.TestCase):
    """The window shown and painted: what a hidden window cannot catch (paint-time errors)."""

    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_every_tab_paints_and_hidden_tabs_wait(self):
        import qt_app
        from qtpy import QtCore
        w = qt_app.MainWindow()
        w.info = w.warn = lambda *a: None
        errors = []
        w.error = lambda *a: errors.append(a)
        handler_errors = []
        old = sys.excepthook
        sys.excepthook = lambda *a: handler_errors.append(a)    # Qt paint overrides report here
        try:
            w.resize(1200, 800)
            w.show()
            for probe in (LINEAR, DUAL):
                w.probe_panel.set_values(probe)
                w.wedge_panel.set_values({"array_sep_mm": 10})
                w.run_calculation()
                for i in range(w.tabs.count()):
                    w.tabs.setCurrentIndex(i)
                    self.qapp.processEvents()
                    w.tabs.currentWidget().repaint()
                    self.qapp.processEvents()
                w.plot_tab.chk_all.setChecked(True)
                w.tabs.setCurrentIndex(0)
                self.qapp.processEvents()
                w.plot_tab.chk_all.setChecked(False)
            # hidden tabs defer: step in the Ray tab, the 3D tab catches up when shown
            w.tabs.setCurrentIndex(0)
            self.qapp.processEvents()
            w.plot_tab.show_law(3)
            w.scene3d_tab.show_law(3)
            self.assertTrue(w.scene3d_tab._stale)
            w.tabs.setCurrentIndex(3)
            self.qapp.processEvents()
            self.assertFalse(w.scene3d_tab._stale)
            self.assertEqual(w.scene3d_tab.scene.find("ray")[0].meta["law"], 3)
        finally:
            sys.excepthook = old
            w.close()
            w.deleteLater()
            self.qapp.processEvents()
        self.assertEqual(errors, [])
        self.assertEqual(handler_errors, [], [str(e[1]) for e in handler_errors][:3])


if __name__ == "__main__":
    unittest.main()
