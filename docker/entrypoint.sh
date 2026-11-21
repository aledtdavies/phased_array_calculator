#!/bin/bash
# Entry point of the headless image (docker/Dockerfile). Commands:
#   test     the full test suite under Xvfb; junit report and skip list to /out
#   images   documentation screenshots to /out/images
#   info     versions and the OpenGL renderer seen by VTK
#   <other>  run as given (e.g. bash)
set -eo pipefail
OUT=${OUT:-/out}
mkdir -p "$OUT"

case "${1:-test}" in
  test)
    cd /app/python
    # The GUI tests skip themselves when Qt or VTK cannot start; in this image that would be a
    # fault, so check first that both open a window (a missing library fails here, loudly).
    xvfb-run -a -s "-screen 0 1920x1200x24" python - <<'EOF'
import os
os.environ.setdefault("QT_API", "pyside6")
from qtpy import QtWidgets
import pyvista, pyvistaqt, pyqtgraph  # noqa: F401
app = QtWidgets.QApplication([])
w = QtWidgets.QWidget(); w.show(); app.processEvents()
pl = pyvista.Plotter(off_screen=True); pl.add_mesh(pyvista.Sphere()); pl.screenshot("/tmp/check.png")
print("GUI check: Qt", app.platformName(), "| VTK renders")
EOF
    # -rs lists every skip with its reason (finish criterion of plan step 7)
    xvfb-run -a -s "-screen 0 1920x1200x24" \
      python -m pytest -q -rs -p no:cacheprovider --junitxml="$OUT/junit.xml" 2>&1 | tee "$OUT/pytest.txt"
    ;;
  images)
    xvfb-run -a -s "-screen 0 1920x1200x24" python /app/tools/render_doc_images.py "$OUT/images"
    ;;
  info)
    python --version
    xvfb-run -a -s "-screen 0 1920x1200x24" python - <<'EOF'
import PySide6, pyvista, vtk, pyqtgraph, numpy
print("PySide6", PySide6.__version__, "| pyvista", pyvista.__version__, "| vtk", vtk.vtkVersion.GetVTKVersion(),
      "| pyqtgraph", pyqtgraph.__version__, "| numpy", numpy.__version__)
pl = pyvista.Plotter(off_screen=True)
pl.add_mesh(pyvista.Sphere())
pl.screenshot("/tmp/x.png")
print(pl.render_window.ReportCapabilities().splitlines()[:4])
EOF
    ;;
  *)
    exec "$@"
    ;;
esac
