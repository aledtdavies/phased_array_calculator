"""
Redraw time per law in the Qt window (plan step 4 finish criterion: under 50 ms on the dev
laptop for a 64-element linear probe and a 16 x 4 dual matrix).

    python tests/benchmarks/redraw_timing.py

Steps through every law of a sweep, as Play does, and times each tab's redraw (the window
shown, so the time includes painting), then times a dragged focus (solve + every tab).
Prints medians and maxima in milliseconds. A measurement, not a test.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "python")))
os.environ.setdefault("QT_API", "pyside6")

import numpy as np                      # noqa: E402
from qtpy import QtWidgets              # noqa: E402

CASES = {
    "64-element linear": ({"probe_type": "Linear", "num_elements": 64, "pitch_mm": 0.75, "freq_mhz": 2.25},
                          {"angle_deg": 36, "height_mm": 5, "velocity_ms": 2337, "offset_mm": 4},
                          {"start_element": 1, "num_active_elements": 0},
                          {"wave_type": "Shear", "start_angle": 40, "end_angle": 70, "step_angle": 1}),
    "16 x 4 dual matrix": ({"probe_type": "Dual Matrix", "num_elements": 16, "num_elements_y": 4,
                            "pitch_mm": 1.0, "pitch_y_mm": 1.5, "freq_mhz": 2.25},
                           {"angle_deg": 18, "height_mm": 8, "velocity_ms": 2330, "offset_mm": 0,
                            "array_sep_mm": 14, "roof_angle_deg": 3},
                           {"start_element": 1, "num_active_elements": 0},
                           {"wave_type": "Longitudinal", "start_angle": 35, "end_angle": 70, "step_angle": 1,
                            "start_skew": 0, "end_skew": 0, "step_skew": 1}),
}


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    import qt_app
    w = qt_app.MainWindow()
    w.info = w.warn = w.error = lambda *a: print("dialog:", a)
    w.resize(1500, 900)
    w.show()
    rows = []
    for name, (pv, wv, sav, sv) in CASES.items():
        w.probe_panel.set_values(pv)
        w.wedge_panel.set_values(wv)
        w.sub_aperture_panel.set_values(sav)
        w.mat_panel.set_values({"thickness_mm": 30})
        w.scan_panel.set_values(dict({"focus_mode": "Constant Depth", "param_val": 20}, **sv))
        w.run_calculation()
        n = len(w.last_results)
        for t, tab in enumerate((w.plot_tab, w.hist_tab, w.scene3d_tab)):
            w.tabs.setCurrentIndex({0: 0, 1: 2, 2: 3}[t])
            app.processEvents()
            tab.show_law(0)
            app.processEvents()
            times = []
            for k in range(1, n):
                t0 = time.perf_counter()
                tab.show_law(k)
                if hasattr(tab, "plotter"):
                    tab.plotter.render()
                app.processEvents()
                times.append((time.perf_counter() - t0) * 1e3)
            rows.append((name, type(tab).__name__, n, np.median(times), np.max(times)))
        # dragged focus: solve and redraw every tab
        w.tabs.setCurrentIndex(0)
        app.processEvents()
        y = float(w.plot_tab.current_focal()[1])
        times = []
        for k in range(20):
            t0 = time.perf_counter()
            w.on_focus_dragged(0.03 + 0.0005 * k, 0.018)
            app.processEvents()
            times.append((time.perf_counter() - t0) * 1e3)
        rows.append((name, "dragged focus (all tabs)", 20, np.median(times), np.max(times)))
    w.close()
    print(f"{'setup':22s} {'view':26s} {'laws':>5s} {'median ms':>10s} {'max ms':>8s}")
    for name, view, n, med, mx in rows:
        print(f"{name:22s} {view:26s} {n:5d} {med:10.1f} {mx:8.1f}")


if __name__ == "__main__":
    main()
