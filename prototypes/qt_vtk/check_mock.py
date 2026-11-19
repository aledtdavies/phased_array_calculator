"""
Checks of the Qt mock's linking (review of PR #23):
- moving the law slider replaces the law's 3D actors (rays, focus, central ray); none pile up,
  and the 3D central ray matches the scene model for the selected law;
- the table's selected row follows the slider, whatever the sort order.

    python check_mock.py [buildFE/catalog folder]      exits non-zero on failure
"""
import os
import sys

os.environ.setdefault("QT_API", "pyside6")
import numpy as np
from qtpy import QtCore, QtWidgets

from qt_mock import Mock


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    app = QtWidgets.QApplication(sys.argv)
    w = Mock(args[0] if args else None)
    w.show()
    app.processEvents()
    n_actors = len(w.vtk.renderer.actors)
    laws = [0, 7, len(w.sweep) - 1, 3, 15]
    for sort_col, order in ((0, QtCore.Qt.AscendingOrder), (1, QtCore.Qt.DescendingOrder),
                            (3, QtCore.Qt.AscendingOrder)):
        w.table.sortItems(sort_col, order)
        for law in laws:
            w.slider.setValue(law)
            app.processEvents()
            actors = w.vtk.renderer.actors
            assert len(actors) == n_actors, f"actors {len(actors)} != {n_actors} after law {law}"
            names = [k for k in actors if k.startswith("law:")]
            assert sorted(names) == ["law:central-ray", "law:focus", "law:ray"], names
            pts = actors["law:central-ray"].mapper.dataset.points
            np.testing.assert_allclose(pts, w.current_prims["central-ray"].coords, atol=1e-9)
            fpts = actors["law:focus"].mapper.dataset.points
            np.testing.assert_allclose(fpts, w.current_prims["focus"].coords, atol=1e-9)
            row = w.table.currentRow()
            got = int(w.table.item(row, 0).data(QtCore.Qt.UserRole))
            assert got == law, f"table row holds law {got}, slider {law} (sort column {sort_col})"
        # and the other way: picking a row moves the slider
        w.table.selectRow(2)
        app.processEvents()
        assert w.slider.value() == int(w.table.item(2, 0).data(QtCore.Qt.UserRole))
    print(f"check_mock: OK ({len(laws)} laws x 3 sort orders, {n_actors} actors throughout)")
    w.close()
    app.quit()


if __name__ == "__main__":
    main()
