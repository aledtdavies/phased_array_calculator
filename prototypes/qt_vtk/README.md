# Qt / PyVista / pyqtgraph prototypes (throwaway)

Evidence for `docs/plans/PLAN-2026-11-qt-vtk-migration.md`. This is not production code: it is not imported by `python/` and has no tests. Steps 1–4 of the plan rewrite it properly.

| File | Shows |
|---|---|
| `scene_model.py` | Renderer-independent primitives built from the solver, a constant-depth focal rule, skip legs, a single-V weld, and an illustrative CW field |
| `render_static.py` | matplotlib renderer: coverage, skips and weld, plus the field (`images/proto_coverage_field.png`) |
| `render_pyvista.py` | PyVista 3D renderer, off-screen screenshots, `--show` for an interactive window |
| `qt_mock.py` | PySide6 shell with pyvistaqt and pyqtgraph, linked law slider, `--screenshot` |
| `check_mock.py` | Checks the linking: law actors replaced (none pile up), 3D central ray and focus match the scene model, table row follows the slider in any sort order |

```
python -m venv .venv-proto
.venv-proto\Scripts\pip install -r prototypes/qt_vtk/requirements.txt
cd prototypes/qt_vtk
..\..\.venv-proto\Scripts\python render_static.py  ..\..\..\buildFE\catalog
..\..\.venv-proto\Scripts\python render_pyvista.py ..\..\..\buildFE\catalog
..\..\.venv-proto\Scripts\python qt_mock.py        ..\..\..\buildFE\catalog
```

The catalogue folder is optional: without it, the same SA2-N55S and 2.25L64-A2 values are typed in.
Built and run with Python 3.14.2, PySide6 6.12.0, pyvista 0.49.2, pyvistaqt 0.14.0, vtk 9.7.2 and pyqtgraph 0.14.0 on Windows 11.
