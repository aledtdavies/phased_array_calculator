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

    def test_show_all_overlays_are_reused_while_navigating(self):
        """Review of PR #27: Show All is built once per calculation, not per law."""
        w = self.calc(DUAL, {"array_sep_mm": 10})
        tab = w.plot_tab
        tab.chk_all.setChecked(True)
        kept = [list(p.all_items) for p in (tab.xz, tab.yz)]
        self.assertTrue(all(kept))
        for law in range(len(w.last_results)):
            tab.show_law(law)
            self.assertEqual([list(p.all_items) for p in (tab.xz, tab.yz)], kept)
        tab.chk_all.setChecked(False)
        self.assertEqual(tab.xz.all_items, [])
        tab.chk_all.setChecked(True)                    # rebuilt after leaving Show All
        self.assertEqual(len(tab.xz.all_items), len(kept[0]))
        self.calc(DUAL, {"array_sep_mm": 12})            # a new calculation rebuilds them
        self.assertTrue(tab.xz.all_items)
        self.assertNotEqual(tab.xz.all_items[0], kept[0][0])

    def test_auto_range_frames_the_geometry(self):
        """Review of PR #27: the component backdrop does not enter Auto Range."""
        for thickness in (0.0, 30.0):
            with self.subTest(thickness=thickness):
                w = self.win
                w.mat_panel.set_values({"thickness_mm": thickness})
                self.calc(LINEAR)
                for plot in (w.plot_tab.xz,):
                    plot.getPlotItem().vb.autoRange()
                    (x0, x1), (z0, z1) = plot.getPlotItem().vb.viewRange()
                    self.assertGreater(x0, -100)
                    self.assertLess(x1, 200)
                    self.assertLess(z1, max(thickness, 60) + 50)

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

    def test_ordinary_navigation_keeps_every_tab_on_one_law(self):
        """Review of PR #27: slider, step and Play in any tab move every tab, before and after a drag."""
        w = self.calc(LINEAR)
        n = len(w.last_results)

        def same(label):
            idx = {t.current_idx for t in w.law_tabs()}
            self.assertEqual(len(idx), 1, (label, [t.current_idx for t in w.law_tabs()]))
            k = idx.pop()
            for t in w.law_tabs():
                self.assertIsNone(t.custom, label)
                np.testing.assert_allclose(t.current_focal(), t.focal_points[k])
            return k

        for source in w.law_tabs():
            name = type(source).__name__
            source.step_law(1)
            same(f"{name} step")
            source.slider.setValue((source.slider.value() + 2) % n)
            same(f"{name} slider")
            if hasattr(source, "toggle_play"):              # Delays has no Play
                source.toggle_play()
                source.animate()
                source.toggle_play()
                same(f"{name} play")
            w.plot_tab.xz.focus.setPos(30.0, 15.0)
            source.step_law(1)
            k = same(f"{name} step after drag")
            source.step_law(1)
            self.assertEqual(same(f"{name} second step after drag"), (k + 1) % n)

    def test_hidden_tabs_open_on_the_shared_law(self):
        w = self.win
        w.resize(1000, 700)
        w.show()
        self.calc(LINEAR)
        w.tabs.setCurrentIndex(0)
        self.qapp.processEvents()
        for _ in range(4):
            w.plot_tab.step_law(1)
        self.assertTrue(w.hist_tab._stale and w.scene3d_tab._stale)
        w.tabs.setCurrentIndex(2)
        self.qapp.processEvents()
        self.assertIn(f"law {w.plot_tab.current_idx + 1}", w.hist_tab.items["plot"].titleLabel.text)
        w.tabs.setCurrentIndex(3)
        self.qapp.processEvents()
        self.assertEqual(w.scene3d_tab.scene.find("ray")[0].meta["law"], w.plot_tab.current_idx)

    def test_clicking_the_selected_row_leaves_a_dragged_focus(self):
        w = self.calc(LINEAR)
        w.tree.selectRow(2)
        w.plot_tab.xz.focus.setPos(30.0, 15.0)
        self.assertTrue(all(t.custom is not None for t in w.law_tabs()))
        w.tree.cellClicked.emit(2, 0)                       # the same row again
        for t in w.law_tabs():
            self.assertIsNone(t.custom)
            self.assertEqual(t.current_idx, 2)

    def test_deselection(self):
        for deferred in (False, True):
            with self.subTest(deferred=deferred):
                w = self.calc(DUAL, {"array_sep_mm": 10})
                w.select_element(5)
                self.assertIn("pick:element", w.scene3d_tab.plotter.renderer.actors)
                w.scene3d_tab._stale = deferred
                w.select_element(None)                      # no TypeError
                for t in w.law_tabs():
                    self.assertIsNone(t.selected_element)
                self.assertNotIn("pick:element", w.scene3d_tab.plotter.renderer.actors)
                self.assertEqual(w.scene3d_tab.lbl_pick.text(), "Click near an element to inspect it.")
                self.assertEqual(w.plot_tab.xz.pick.getData()[0].size, 0)
                w.scene3d_tab._stale = False

    def test_one_play_for_the_window(self):
        """Review of PR #27: one timer steps the shared law; Pause anywhere stops it."""
        w = self.calc(LINEAR)
        n = len(w.last_results)
        timers = lambda: [t.timer.isActive() for t in (w.plot_tab, w.scene3d_tab)] + [w.play.timer.isActive()]
        w.plot_tab.toggle_play()                                # Play in Ray Tracing
        self.assertTrue(w.play.playing)
        self.assertEqual(timers(), [False, False, True])        # the window's timer only
        self.assertEqual(w.scene3d_tab.play_btn.text(), "Pause")
        w.scene3d_tab.toggle_play()                             # the 3D button now pauses it
        self.assertFalse(w.play.playing)
        self.assertEqual(timers(), [False, False, False])
        self.assertEqual(w.plot_tab.play_btn.text(), "Play")
        start = w.plot_tab.current_idx
        w.scene3d_tab.toggle_play()
        for _ in range(3):
            w.play.tick()                                       # three timeouts: three laws, not six
        w.plot_tab.toggle_play()
        for t in w.law_tabs():
            self.assertEqual(t.current_idx, (start + 3) % n)
        w.play.tick()                                           # paused: nothing moves
        self.assertEqual(w.plot_tab.current_idx, (start + 3) % n)

    def test_scrubbing_during_play_redraws_the_source(self):
        w = self.calc(LINEAR)
        w.plot_tab.toggle_play()
        w.plot_tab.slider.setValue(w.plot_tab.slider.value() + 2)    # before any timeout
        f = w.plot_tab.current_focal() * 1e3
        self.assertAlmostEqual(w.plot_tab.xz.focus.pos().x(), f[0], places=9)
        self.assertAlmostEqual(w.plot_tab.xz.focus.pos().y(), f[2], places=9)
        for t in w.law_tabs():
            self.assertEqual(t.current_idx, w.plot_tab.current_idx)
        w.plot_tab.toggle_play()

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

    def test_delay_scale_covers_a_dragged_focus_and_returns(self):
        w = self.calc(dict(LINEAR, num_elements=64, pitch_mm=0.75))
        bars = w.hist_tab.items
        sweep_top = bars["plot"].vb.viewRange()[1][1]
        w.plot_tab.xz.focus.setPos(0.0, 1.0)                      # the reviewer's focus
        d = np.asarray(w.hist_tab.current_result()["delays_us"])
        self.assertGreater(np.nanmax(d), sweep_top)               # would clip on the sweep scale
        self.assertGreaterEqual(bars["plot"].vb.viewRange()[1][1], np.nanmax(d))
        w.plot_tab.step_law(1)                                    # back to the sweep: its scale
        self.assertAlmostEqual(bars["plot"].vb.viewRange()[1][1], sweep_top, places=9)
        # matrix: image levels and colour bar
        w = self.calc(DUAL, {"array_sep_mm": 10})
        items = w.hist_tab.items
        sweep_vmax = items["vmax"]
        w.plot_tab.xz.focus.setPos(-5.0, 0.5)
        d = np.asarray(w.hist_tab.current_result()["delays_us"])
        top = float(np.nanmax(d))
        self.assertGreater(top, sweep_vmax)
        for img in items["images"]:
            self.assertGreaterEqual(img.getLevels()[1], top)
        self.assertGreaterEqual(items["bar"].levels()[1], top)
        w.plot_tab.step_law(1)
        self.assertAlmostEqual(items["images"][0].getLevels()[1], sweep_vmax, places=12)

    def test_selected_bar_follows_the_law(self):
        w = self.calc(LINEAR)
        w.select_element(10)
        for step in ("law", "custom"):
            if step == "law":
                w.hist_tab.show_law(3)
            else:
                w.plot_tab.xz.focus.setPos(25.0, 12.0)
            y = w.hist_tab.items["pick"].getData()[1][0]
            self.assertAlmostEqual(y, w.hist_tab.current_result()["delays_us"][10], places=12, msg=step)

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
class Coverage(_WindowCase):
    """Plan step 5a: coverage fans and the central ray with skips in the 2D and 3D views."""

    def setUp(self):
        super().setUp()
        self.win.mat_panel.set_values({"thickness_mm": 25})

    def test_off_by_default_and_needs_a_thickness(self):
        w = self.calc(LINEAR)
        self.assertIsNone(w.plot_tab.coverage)
        w.mat_panel.set_values({"thickness_mm": 0})
        self.calc(LINEAR)                                   # a calculation without a thickness
        w.coverage_combo.setCurrentIndex(2)
        self.assertIsNone(w.plot_tab.coverage)
        self.assertIn("Thickness", w.coverage_note.text())

    def test_fans_and_central_ray_follow_the_law_and_a_dragged_focus(self):
        import pyqtgraph as pg
        w = self.calc(LINEAR, scan={"wave_type": "Shear", "start_angle": 40, "end_angle": 70, "step_angle": 5})
        w.coverage_combo.setCurrentIndex(2)                 # direct + 1st skip
        tab = w.plot_tab
        cov = tab.coverage
        self.assertEqual(cov.legs, 2)
        self.assertIn("no mode conversion", w.coverage_note.text())
        polys = [it for it in tab.xz.setup_items if isinstance(it, QtWidgets.QGraphicsPolygonItem)]
        n_quads = sum(len(q) for q in cov.fans.values())
        self.assertGreaterEqual(len(polys), n_quads)
        centre = tab.solver.aperture_centre() * 1e3
        for law in (0, 3, len(w.last_results) - 1):
            tab.show_law(law)
            x, z = tab.xz.central.getData()
            want = np.vstack([centre[None, :], cov.paths[law] * 1e3])
            np.testing.assert_allclose(x, want[:, 0])
            np.testing.assert_allclose(z, want[:, 2])
            np.testing.assert_allclose(z[1:], [0.0, 25.0, 0.0], atol=1e-9)    # surface, backwall, surface
        tab.xz.focus.setPos(40.0, 12.0)                      # dragged: the central ray follows
        x, z = tab.xz.central.getData()
        self.assertAlmostEqual(float(np.interp(12.0, z[1:3], x[1:3])), 40.0, places=6)
        # the 3D view carries the same
        w.scene3d_tab.refresh_plot()
        actors = w.scene3d_tab.plotter.renderer.actors
        self.assertIn("setup:coverage-1", actors)
        self.assertIn("setup:coverage-2", actors)
        self.assertIn("law:central-ray", actors)
        w.coverage_combo.setCurrentIndex(0)                 # off again
        self.assertIsNone(tab.coverage)
        x, _ = tab.xz.central.getData()
        self.assertTrue(x is None or len(x) == 0)

    def test_coverage_uses_the_calculations_thickness(self):
        """Review of PR #28: an edit after the calculation does not move the skips off the drawn backwall."""
        w = self.calc(LINEAR)                                   # 25 mm plate
        w.mat_panel.set_values({"thickness_mm": 50})            # edited, not recalculated
        w.coverage_combo.setCurrentIndex(2)
        self.assertEqual(w.plot_tab.coverage.thickness, 0.025)
        self.assertEqual(w.plot_tab.component_thickness_mm, 25)
        self.assertEqual(w.scene3d_tab.component_thickness_mm, 25)
        np.testing.assert_allclose(w.plot_tab.coverage.paths[0][1, 2], 0.025)

    def test_single_law_skips_are_framed(self):
        """Review of PR #28: a single law (no fans) still frames its whole skip path."""
        w = self.calc(LINEAR, scan={"start_angle": 60, "end_angle": 60, "step_angle": 1, "param_val": 5})
        w.coverage_combo.setCurrentIndex(3)
        self.assertEqual(len(w.last_results), 1)
        x, z = w.plot_tab.xz.central.getData()
        (x0, x1), (z0, z1) = w.plot_tab.xz.getPlotItem().vb.viewRange()
        self.assertTrue(np.all((x >= x0) & (x <= x1)), (x, x0, x1))
        self.assertTrue(np.all((z >= min(z0, z1)) & (z <= max(z0, z1))))
        names = [label.text for _, label in w.plot_tab.xz.legend.items]
        self.assertIn("Central ray (skips)", names)

    def test_3d_frames_every_skip_path(self):
        """Review of PR #28: a single-angle, multi-Y sweep (no fans) frames all skips in 3D."""
        from scene_vtk import scene_bounds
        w = self.calc(dict(DUAL, probe_type="Matrix"),
                      scan={"start_angle": 40, "end_angle": 40, "step_angle": 1, "param_val": 5,
                            "y_focus_mode": "Y Sweep", "y_start_mm": -5, "y_end_mm": 5, "y_step_mm": 5})
        w.coverage_combo.setCurrentIndex(3)
        tab = w.scene3d_tab
        tab.chk_locus.setChecked(False)
        self.assertEqual(sum(len(q) for q in tab.coverage.fans.values()), 0)
        for law in range(len(w.last_results)):
            tab.show_law(law)
            lo, hi = tab.bounds
            pts = np.vstack(tab.coverage.paths) * 1e3
            self.assertTrue(np.all((pts >= lo - 1e-9) & (pts <= hi + 1e-9)), law)

    def test_matrix_skew_sweep_one_fan_per_skew(self):
        w = self.calc(dict(DUAL, probe_type="Matrix"), scan={"start_skew": -10, "end_skew": 10, "step_skew": 20,
                                                             "start_angle": 40, "end_angle": 60, "step_angle": 10})
        w.coverage_combo.setCurrentIndex(1)
        cov = w.plot_tab.coverage
        self.assertEqual(len(cov.fans[1]), 2 * 2)          # 2 skews x (3 angles - 1)


@unittest.skipUnless(HAVE_QT, "PySide6/pyqtgraph/pyvistaqt not installed, or no display")
class Weld(_WindowCase):
    """Plan step 5b: the weld drawn in X-Z and 3D, fusion faces split into covered runs and gaps."""
    SCAN = {"wave_type": "Shear", "focus_mode": "Constant Sound Path", "param_val": 40,
            "start_angle": 40, "end_angle": 70, "step_angle": 2}
    WELD = {"type": "Single-V", "centre_x_mm": 45, "bevel_deg": 30, "root_gap_mm": 2, "root_face_mm": 1.5}

    def setUp(self):
        super().setUp()
        self.warnings = []
        self.win.warn = lambda *a: self.warnings.append(a)
        self.win.mat_panel.set_values({"thickness_mm": 25})

    def roles(self, plot):
        """The legend names the 2D plot shows."""
        return [label.text for _, label in plot.legend.items]

    def test_no_weld_by_default(self):
        w = self.calc(LINEAR, scan=self.SCAN)
        self.assertEqual(w.plot_tab.weld_prims, [])
        self.assertNotIn("Weld", self.roles(w.plot_tab.xz))
        self.assertEqual(w.weld_note.text(), "")
        self.assertNotIn("weld", w.config_dict())

    def test_template_weld_faces_and_gaps(self):
        from weld import template_profile
        w = self.win
        w.weld_panel.set_values(self.WELD)
        self.calc(LINEAR, scan=self.SCAN)
        tab = w.plot_tab
        roles = [p.role for p in tab.weld_prims]
        self.assertEqual(roles.count("weld"), 1)
        self.assertEqual(roles.count("fusion-face"), 2)          # no coverage yet: plain faces
        self.assertIn("Weld", self.roles(tab.xz))
        self.assertNotIn("Weld", self.roles(tab.yz))            # the weld runs along Y: X-Z only
        self.assertIn("turn Coverage on", w.weld_note.text())
        want = template_profile("single-V", 25, 45, bevel_deg=30, root_gap_mm=2, root_face_mm=1.5)
        np.testing.assert_allclose(w.calc_weld.polygon, want.polygon)
        w.coverage_combo.setCurrentIndex(1)                     # direct only
        direct = w.fusion.covered_mm()
        roles = {p.role for p in tab.weld_prims}
        self.assertTrue({"fusion-covered", "fusion-gap"} <= roles, roles)
        self.assertIn("% covered", w.weld_note.text())
        self.assertIn("Fusion face, gap", self.roles(tab.xz))
        w.coverage_combo.setCurrentIndex(2)                     # + 1st skip reaches more
        self.assertGreater(w.fusion.covered_mm(), direct)
        # the runs drawn are the coverage's runs, end to end along each face
        for f in w.fusion.faces:
            runs = [p for p in tab.weld_prims if p.role.startswith("fusion-") and p.meta["name"] == f.name]
            self.assertEqual(len(runs), len(f.runs()))
        w.scene3d_tab.refresh_plot()
        actors = w.scene3d_tab.plotter.renderer.actors
        for name in ("setup:weld", "setup:fusion-covered", "setup:fusion-gap"):
            self.assertIn(name, actors)

    def test_the_drawn_weld_is_the_calculations(self):
        w = self.win
        w.weld_panel.set_values(self.WELD)
        self.calc(LINEAR, scan=self.SCAN)
        before = w.calc_weld.polygon.copy()
        w.weld_panel.set_values({"bevel_deg": 45})              # edited, not recalculated
        w.coverage_combo.setCurrentIndex(2)
        np.testing.assert_allclose(w.calc_weld.polygon, before)
        self.calc(LINEAR, scan=self.SCAN)
        self.assertGreater(np.ptp(w.calc_weld.polygon[:, 0]), np.ptp(before[:, 0]))

    def test_refused_weld_warns_and_draws_nothing(self):
        w = self.win
        w.weld_panel.set_values(dict(self.WELD, root_face_mm=30))
        self.calc(LINEAR, scan=self.SCAN)
        self.assertIsNone(w.calc_weld)
        self.assertEqual(w.plot_tab.weld_prims, [])
        self.assertIn("Weld not drawn", w.weld_note.text())
        self.assertEqual(len(self.warnings), 1)
        w.mat_panel.set_values({"thickness_mm": 0})
        w.weld_panel.set_values(self.WELD)
        self.calc(LINEAR, scan=self.SCAN)
        self.assertIn("Thickness", w.weld_note.text())

    def test_dxf_weld_matches_the_template(self):
        import tempfile
        import ezdxf
        from weld import template_outline
        w = self.win
        w.weld_panel.set_values(self.WELD)
        self.calc(LINEAR, scan=self.SCAN)
        w.coverage_combo.setCurrentIndex(2)
        template = w.fusion.covered_mm()
        pts = template_outline("single-V", 25, bevel_deg=30, root_gap_mm=2, root_face_mm=1.5)
        doc = ezdxf.new()
        doc.modelspace().add_lwpolyline([(x, -z) for x, z in pts], close=True)
        path = os.path.join(tempfile.mkdtemp(), "weld.dxf")
        doc.saveas(path)
        w.weld_panel.set_values({"type": "DXF file", "dxf_path": path, "dxf_datum": "surface"})
        self.calc(LINEAR, scan=self.SCAN)
        # ezdxf stamps a new file as metres: read so, the outline is 1000x too deep and refused
        self.assertIsNone(w.calc_weld)
        self.assertIn("set them if the file's are wrong", w.weld_note.text())
        w.weld_panel.set_values({"dxf_units": "mm"})
        self.calc(LINEAR, scan=self.SCAN)
        self.assertTrue(w.calc_weld.source.startswith("DXF weld.dxf"))
        self.assertAlmostEqual(w.fusion.covered_mm(), template, delta=0.1)

    def test_configuration_round_trip(self):
        w = self.win
        w.weld_panel.set_values(dict(self.WELD, type="Single-J", j_side="far", root_radius_mm=5))
        config = w.config_dict()
        self.assertEqual(config["weld"]["type"], "Single-J")
        import qt_app
        w2 = qt_app.MainWindow()
        try:
            w2.apply_config(config)
            self.assertEqual(w2.weld_panel.get_values(), config["weld"])
        finally:
            w2.close()
            w2.deleteLater()


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
