"""
Render the documentation screenshots of the Qt window (plan step 7): the setups of the step 5b
and step 6 images, grabbed from a shown window, to a folder.

    python tools/render_doc_images.py <out_dir>

Runs anywhere Qt and VTK can open a window: a desktop, or Xvfb in the headless image
(docker/Dockerfile). The probe and wedge are the 2.25L64-A2 on the SA2-N55S. With
$PAC_CATALOG_DIR (or a sibling buildFE checkout) they come from the catalogue, which also draws
the wedge's outline; without one the panels are filled with the same catalogue values
(buildFE catalog, 2026-11) and the wedge is drawn schematically. Writes index.txt with each
image's setup and status line.
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "python"))
os.environ.setdefault("QT_API", "pyside6")

from qtpy import QtWidgets          # noqa: E402

import qt_app                       # noqa: E402
from catalog import default_catalog_dir   # noqa: E402

PROBE = {"probe_type": "Linear", "num_elements": 64, "pitch_mm": 0.75, "freq_mhz": 2.25}
WEDGE = {"angle_deg": 36, "height_mm": 5, "velocity_ms": 2337, "offset_mm": 4}
FIELD = {"element_width_mm": 0.55, "elevation_mm": 12, "wedge_shear_ms": 1157, "wedge_density": 1049,
         "component_density": 7900}


class Shots:
    def __init__(self, out):
        self.out = out
        os.makedirs(out, exist_ok=True)
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        self.index = []
        self.catalog = default_catalog_dir()

    def window(self, thickness, scan, weld=None):
        w = qt_app.MainWindow()
        w.info = w.warn = lambda *a: None
        def fail(title, text):
            raise RuntimeError(f"{title}: {text}")      # a catalogue or calculation error stops the run
        w.error = fail
        if self.catalog:
            w.pick_catalog_entry = lambda c, k: "evident-2.25L64-A2" if k == "probe" else "evident-SA2-N55S"
            w.load_from_catalog("probe", path=os.path.join(self.catalog, "probes.json"))
            w.load_from_catalog("wedge", path=os.path.join(self.catalog, "wedges.json"))
            if sorted(w.catalog.assets) != ["probe", "wedge"]:
                raise RuntimeError(f"the catalogue in {self.catalog} did not give both the probe and the wedge")
        else:
            w.probe_panel.set_values(PROBE)
            w.wedge_panel.set_values(WEDGE)
        w.field_tab.set_values(FIELD)
        w.mat_panel.set_values({"thickness_mm": thickness, "vel_long_ms": 5900, "vel_shear_ms": 3230})
        w.sub_aperture_panel.set_values({"start_element": 1, "num_active_elements": 32})
        w.scan_panel.set_values(scan)
        if weld:
            w.weld_panel.set_values(weld)
        w.resize(1500, 950)
        w.show()
        w.run_calculation()
        self.app.processEvents()
        return w

    def save(self, w, tab, name, note=""):
        w.tabs.setCurrentWidget(tab)
        self.app.processEvents()
        time.sleep(0.2)
        self.app.processEvents()
        path = os.path.join(self.out, name)
        if not w.grab().save(path):
            raise RuntimeError(f"could not save {path}")
        self.index.append(f"{name}\t{note}")
        print(name, "|", note)

    def finish(self):
        src = f"catalogue {self.catalog}" if self.catalog else "panel values (no catalogue)"
        with open(os.path.join(self.out, "index.txt"), "w", encoding="utf-8") as f:
            f.write(f"probe and wedge from: {src}\n")
            f.write("\n".join(self.index) + "\n")


def compute(w, **values):
    """Compute the field and refuse to go on with a failed or stale one."""
    w.field_tab.set_values(values)
    w.field_tab.compute(sync=True)
    job = w.field_tab.job
    if job is None or not job.get("fresh"):
        raise RuntimeError(f"no field: {w.field_tab.status.text()}")


def main(out):
    s = Shots(out)
    # step 5b: single-V weld with coverage (direct + 1st skip)
    w = s.window(25, {"wave_type": "Shear", "focus_mode": "Constant Sound Path", "param_val": 60,
                      "start_angle": 40, "end_angle": 70, "step_angle": 1},
                 {"type": "Single-V", "centre_x_mm": 60, "bevel_deg": 30, "root_gap_mm": 2, "root_face_mm": 1.5})
    w.coverage_combo.setCurrentIndex(2)
    s.app.processEvents()
    s.save(w, w.plot_tab, "step5b_singlev_xz.png", w.weld_note.text())
    w.scene3d_tab.set_view("Iso")
    s.save(w, w.scene3d_tab, "step5b_singlev_3d.png")
    w.close()
    # step 6: beam field of the 55 degree shear law focused at 25 mm
    w = s.window(40, {"wave_type": "Shear", "focus_mode": "Constant Depth", "param_val": 25,
                      "start_angle": 40, "end_angle": 70, "step_angle": 5})
    idx = [i for i, r in enumerate(w.plot_tab.results) if abs(r["angle"] - 55) < 1e-6][0]
    w.plot_tab.show_law(idx)
    s.app.processEvents()
    compute(w, model="2D", pulsed=True, cycles=3, grid_mm=0.25)
    s.save(w, w.field_tab, "step6_field_2d.png", w.field_tab.status.text())
    compute(w, model="3D", pulsed=False, grid_mm=0.5)
    s.save(w, w.field_tab, "step6_field_3d_sections.png", w.field_tab.status.text())
    w.scene3d_tab.set_view("Iso")
    s.save(w, w.scene3d_tab, "step6_field_3d_view.png")
    w.close()
    s.finish()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "out", "images"))
