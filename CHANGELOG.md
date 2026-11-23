# Changelog

## Beam field: progress and Cancel in both versions — 2026-11-22

- **Browser:**
  - the beam field is computed in steps of about 0.4 s, so a bar shows its progress;
  - **Cancel** stops it between steps and leaves the field shown as it was;
  - the result equals the one-call field exactly, because steps are whole blocks of points.
- **Desktop:** the Beam Field tab gains a **Cancel** button beside its progress bar, which before only stopped when the window closed.
- **Shared code:** both versions step through the same field job in `field_job.py` (`start_job`, `step_job`, `finish_job`; `run_job` runs them in one go). `beam_field.point_block` gives the block size.
- **Tests:**
  - stepped equals one-call, exactly, in 2D pulsed and 3D continuous wave (`test_field_tab.TestSteps`, `test_web`);
  - the desktop Cancel keeps the field shown;
  - the browser check starts a long 3D field, sees progress, cancels and checks that the field shown is kept.
## Desktop 3D view: solids from the shared scene model — 2026-11-22

- The desktop 3D view draws the component, wedge and weld from `scene_model.solid_prims`, as the browser does: the same cross-sections, triangles and extents. Before, it extruded the outlines itself.
- `scene_vtk.solid_mesh` builds each closed body with outward faces.
- Test (`test_view3d.SharedSolids`): each body is closed, and its volume and Y extent match the shared solid (component, wedge, and a pinched double-V weld drawn lobe by lobe).
- The parity plan's gap for this is closed.

## Browser version: the 3D view, and keeping it in step with the desktop — 2026-11-22

- **3D view in the browser** (tab "3D"), as the desktop's 3D tab:
  - wedge, component, weld, element footprints, coverage fans and fusion faces, drawn as solids;
  - the law's rays, interface points and focus, the sweep's foci, and the beam field sections (while current);
  - camera presets Iso, X-Z, Y-Z and Top, the Section cut and element picking.
  - Plotly WebGL (`web/view3d.js`), already shipped: nothing more to download. Rotate by dragging; pinch or scroll to zoom.
- **Shared 3D geometry:** the framing, section plane and solids moved from the VTK renderer into `scene_model.py` (`scene_bounds`, `section_y`, `solid_prims`, `triangulate_polygon`), so both 3D views use them.
- **Parity plan** (`docs/plans/PLAN-2026-11-web-desktop-parity.md`), with checks on every pull request:
  - `docs/web_parity.json` lists every desktop control and its browser counterpart;
  - `python/test_parity.py` fails on an unlisted control, a missing shipped module, panels whose fields or defaults differ, or different 3D presets or styles;
  - `tools/web_smoke.py` runs the page in headless Chromium and checks every tab at desktop and phone width, uploading the screenshots as the `web-screenshots` artefact.
- The page shows the commit it was built from (*Build …* under the status line).

## Browser version: full functionality, phones, new look — 2026-11-22

- **Every desktop feature except the 3D view:**
  - linear, matrix, dual linear and dual matrix probes, with skew, Y focus modes, roof and element order;
  - coverage fans and skips, and welds (templates and DXF, with fusion-face gaps);
  - Show all laws, Play, the dragged focus (drag, or tap with "Place focus"), and element picking in rays and delays;
  - delay bars and per-array delay maps, and the beam field in 2D or 3D sections;
  - configurations (the desktop's file format, both ways), probe and wedge catalogues, laws CSV and element coordinates (CSV, .m, .mat).
- **One source of truth:** the views draw the desktop's own scene primitives (`scene_model.py`). The panels (`web/panels.json`) carry the desktop's fields, defaults and rules, and `test_web.py` checks the defaults. The beam field runs the desktop's job, now in a Qt-free `python/field_job.py` that `qt_field.py` also uses.
- **Layout:** responsive. On a phone the setup slides in and the views fill the screen; on wider screens the setup is a side panel. The charts are Plotly (`vendor/plotly.min.js`, MIT), which pan and zoom by touch.
- **DXF in the browser:** the site ships the ezdxf wheel (SHA-256 checked at build) and Pyodide's micropip, pyparsing, typing-extensions and fonttools.
- **Tests:** `test_web.py` gives the desktop's tables and delays on every shared scan case, the desktop's CSV, and the desktop's beam field.
- **Notices:** `THIRD_PARTY_NOTICES.md` lists the browser version's third-party files and licences.

## Browser version published on GitHub Pages — 2026-11-22

- Published at <https://aledtdavies.github.io/phased_array_calculator/>; the `pages` workflow publishes every merge to `main` (owner, 2026-11-22).
- `web/help.html`: help for users, linked from the page. `docs/WEB_APP.md`: publishing, rolling back, and hosting on a work server (site zip or Docker), with the content types a server needs.
- The site now ships a `web.config`, so IIS serves `.mjs`, `.wasm`, `.py` and `.whl` without configuration.

## Browser prototype — 2026-11-22

- `web/`: the calculator in a browser, through Pyodide (Python 3.14 in WebAssembly) running the same `session.py` and `beam_field.py` as the desktop window, in a Web Worker. It covers linear probes on a wedge: laws and table, X-Z rays, delays, and the 2D beam field. Measured on the dev laptop: ready in 18–19 s on a first visit; the beam field 1.2–1.4× the desktop's time.
- `tools/build_web.py` (`--offline` copies Pyodide in), `python/test_web.py`, `docker/web.Dockerfile` (nginx, for a work-network server), `netlify.toml`, `.github/workflows/pages.yml` (manual), and the `web` job in `headless.yml` (builds and checks the image, uploads the site zip).
- Plan and hosting options: `docs/plans/PLAN-2026-11-web-app.md`.

## The Tk window is retired — 2026-11-21

- Removed: `python/app.py`, `panels.py`, `plotting.py`, `catalog_dialog.py` and `test_gui.py`, and `tests/refactor_check` (the step 1 reference-image check rendered with the Tk window; it is in the history up to 5b43988). The Qt window (`python/qt_app.py`) is the calculator's window; the PyInstaller build already used it.
- Kept: `scene.py` (the matplotlib drawing used by `visualisation.py`, and colours used by the Qt views), `session.py`, `navigation.py` and the library.
- Configuration files saved by the Tk window load unchanged: a Tk-saved default and dual-matrix setup are kept as `tests/fixtures/tk_saved_configs.json` and tested. The Tk-vs-Qt table test becomes "the Data Table is `session.calculate`'s rows".
- The headless image no longer installs Tk.

## Dragged focus: the view reframes on release — 2026-11-21

- Releasing a dragged focus widens the Ray Tracing views (X-Z, and Y-Z where shown) when the law's rays, central ray or focus lie within 10 % of the view's edge or outside it; a view that already shows them is left as the user set it. The view never narrows. Images: `docs/plans/images/drag_reframe_before.png`, `drag_reframe_after.png`.

## DXF weld outlines must be flat — 2026-11-21

- `weld.dxf_profile` refuses an outline whose points do not share one Z (a 3D drawing, a tilted arc or a 3D polyline) instead of reading it flattened onto X-Y. An outline drawn flat at any constant elevation is read as before. (Codex MINOR on PR #29.)

## Step 7: headless Docker image — 2026-11-21

Plan step 7 (approved by the owner on 2026-11-20); finish criteria committed first (cadc1e3).

- **`docker/Dockerfile`:** Python 3.12 on Debian bookworm with Xvfb, Mesa software OpenGL, the xcb libraries Qt loads, Tk and fonts; the repository's requirements and pytest. Qt runs on its native `xcb` platform and VTK on GLX (Mesa llvmpipe), as on a desktop.
- **`docker/entrypoint.sh`:** `test` (first checks that Qt and VTK open a window, so the GUI tests cannot skip silently; then the suite with every skip listed), `images`, `info`.
- **`tools/render_doc_images.py`:** the step 5b and step 6 screenshots from a shown window; fails if a field is not computed or an image is not saved.
- **`.github/workflows/headless.yml`:** builds the image and runs `info`, `test` and `images` on pull requests and pushes to `main`; uploads the results.
- **Finish criteria met** (run 2026-11-21): the image builds in Actions from this repository alone; 191 tests pass, 2 skip (both "no sibling buildFE checkout"); the five documentation images render, with the same coverage and beam-axis figures as on the laptop. Renderer: llvmpipe (LLVM 15), OpenGL 4.5, Mesa 22.3.6.

## Step 6: beam field view — 2026-11-20

Plan step 6 (approved by the owner on 2026-11-20).

- **Survey first:** no suite component holds an analytic beam model (buildFE solves FE fields; imageFE builds travel-time tables; nde-knowledge none), so the calculator has its own.
- **`beam_field.py`:** ray model of a law's beam in the component.
  - Element directivity: Miller–Pursey normal strip load on the wedge (copied from arim, MIT, with attribution).
  - Fermat entry point for every element–point pair at once (bisection, then Newton).
  - Plane-wave displacement coefficients of a welded solid–solid interface (4 × 4 boundary conditions), tabulated against slowness.
  - Geometric spreading through the interface, 2D (line sources) and 3D (point sources).
  - Pulsed (Hann burst, broadband sum, envelope peak) or continuous wave; displacement summed as a vector.
- **`beam_metrics.py`:** buildFE's beam-axis and width rule, ported so both maps are measured alike. On the FE frames it reproduces buildFE's own measurement (angle 45.27°, widths to 0.01 mm).
- **Finish criterion met:** against a full-wave FE solve (2.25L64-A2 on SA2-N55S, 64 elements, 45° shear steer, 2D, bonded), with tolerances committed before the comparison ran (bb9a730): axis angle −0.37° (≤ 1°), exit point +0.01 mm (≤ 2 mm), −6 dB widths within 0.6 % (≤ 10 %), axis levels within 0.44 dB (≤ 1.5 dB). `validation/beam_field/compare_buildfe.py`.
- **Qt window:** a **Beam Field** tab (2D or 3D model, pulsed or CW, inputs filled from the catalogue, computed in a worker thread) and the sections in the 3D view.
- **Not modelled (stated in the tab):** reflections, mode conversion, attenuation, fluid couplant. The 3D mode is not separately validated.
- **Catalogue:** the wedge's material density is now read (`WedgeAsset.density`).

## Step 5b: weld geometry and fusion-face gaps — 2026-11-20

Plan step 5b (approved by the owner on 2026-11-20).

- **`weld.py`:**
  - Preparation templates: single-V, double-V (separate upper and lower bevels, root face at any depth) and single-J (ISO 9692-1 shape, J on either plate). Cap and root are flush.
  - DXF cross-sections read with ezdxf: LINE, ARC, LWPOLYLINE (with bulges), POLYLINE, SPLINE, ELLIPSE and CIRCLE, joined into one closed outline. Its datum is the surface or the backwall, and x = 0 is the weld centreline. Units follow `$INSUNITS` or are set by hand. A file with several outlines must name its weld layer. Open, ambiguous or out-of-part outlines are refused with the reason.
  - Fusion faces are taken from the outline the same way for templates and DXF. They are split into covered runs and gaps by the coverage fans, leg by leg.
- **Qt window:**
  - A **Weld** panel (type, centre X, preparation, or DXF file, datum, units and layer), read when the laws are calculated and saved in configurations.
  - The weld is drawn in X-Z and as a prism in 3D. Fusion faces are green where covered and red at gaps.
  - The toolbar gives the covered share and the gap length.
- **Finish criterion met:** template and DXF of one weld agree to 0.01 mm (stated before the test was written).
- **New dependency:** `ezdxf` (MIT).

## Step 5a: coverage fans and skips — 2026-11-20

Plan step 5a (approved by the owner on 2026-11-20).

- **`coverage.py`:**
  - Each law's central ray runs from the active aperture's centre to its focus, refracted at the entry by Snell's law. This holds for any focus: a sweep law, a Y-sweep target or a dragged focus.
  - The ray is carried through a flat plate of the component Thickness with skips: specular reflections at the backwall and the surface.
  - Coverage fans join neighbouring laws leg by leg, one fan per skew.
- **ASSUMPTION, shown in the window:** each reflection keeps the wave mode (no mode conversion), and only central rays are drawn, not the beam's spread.
- **Qt window:** a Coverage selector (Off, Direct, + 1st skip, + 2 skips) in a new toolbar. Fans are drawn as translucent polygons in X-Z and Y-Z and as sheets in 3D. The current law's central ray is drawn from the aperture centre with its skips (dashed in 2D) and follows a dragged focus. Coverage needs a Thickness; without one the toolbar says so.
- **Tests:**
  - Snell's law holds at every entry point, and the central ray's direction is the focal rule's (sin β cos φ, sin β sin φ, cos β).
  - Skip points lie on the walls, with the angle to the normal and the horizontal direction preserved; ± skew move ± Y.
  - Fans group by skew; the views draw them, and the central ray follows the law and a dragged focus.

## Migration step 4: live 2D views on pyqtgraph — 2026-11-20

Plan step 4 (`docs/plans/PLAN-2026-11-qt-vtk-migration.md`).

- **The Qt window's Ray Tracing and Delays tabs on pyqtgraph** (`qt_views2d.py`), drawn from the scene model:
  - items are built once per calculation, and only the current law's are updated per tick;
  - X-Z, plus Y-Z for matrix and dual probes, with the wedge, probe body, dimensions, elements, envelope rays, focus and component;
  - Delays shows a bar chart (linear) or per-array delay maps with element numbers and a colour bar (matrix).
- **Drag the focus in X-Z.** The law for the dragged focus is solved live and shown in every tab, marked "dragged focus (not in the sweep)". The table and CSV are unchanged; any slider, step or table selection returns to the sweep. A focus dragged above the surface is refused.
- **One current law for every tab.** A slider, step, Play or table selection in any tab moves them all; hidden tabs draw it when shown.
- **Linked element selection.** Clicking an element marker, a delay bar, a map cell or an element in the 3D view selects it in every tab.
- **Hidden tabs redraw only when shown,** and the 3D tab updates the law's meshes in place: a 3D redraw per law went from about 125–156 ms to 28–30 ms.
- **Redraw per law** (dev laptop, `tests/benchmarks/redraw_timing.py`, medians):

  | | Ray Tracing | Delays | 3D View | Dragged focus (solve + visible tab) |
  |---|---|---|---|---|
  | 64-element linear | 19 ms | 17 ms | 25 ms | 35 ms |
  | 16 × 4 dual matrix | 33 ms | 29 ms | 30 ms | 66 ms |

  Steady-state maxima are at most 50 ms. The first redraw after a tab is first shown (a one-off cache warm-up) reached 67 ms for the dual-matrix Delays maps. The dual-matrix drag includes solving 128 elements with the 3D solver. Hidden tabs redraw when shown: a drag followed by showing every tab in turn takes 126 and 160 ms, tab switching included.
- **One Play for the window:** a single timer steps the shared law, and every Play button shows the same state.
- `scene_model.wedge_yz_rect` (the Y-Z wedge silhouette) is shared by both renderers; the Tk images are unchanged. `session.law_result` holds one law's fields.
- `requirements.txt` adds pyqtgraph. The Qt window no longer uses matplotlib; the Tk window and static exports still do.

## Migration step 3: the 3D view on PyVista — 2026-11-20

Plan step 3 (`docs/plans/PLAN-2026-11-qt-vtk-migration.md`).

- **The Qt window's 3D View** (`qt_view3d.py`, pyvistaqt) draws the scene model with a new VTK renderer (`scene_vtk.py`):
  - the wedge (catalogue outline or schematic) and the component as translucent solids;
  - element footprints at their catalogue width and elevation, or a labelled schematic size;
  - the selected law's rays, interface points and focus, and the sweep's foci.

  Camera presets keep depth downward; the axis views use parallel projection. A Section option cuts the solids at the active aperture's centre. Clicking near an element picks it, showing its number in the chosen numbering convention, its array, grid position, delay and time of flight, and drawing its ray bold.
- **`wedge.transform_points`:** the element transform is applied to any points (element corners). `get_transformed_elements` uses it with unchanged arithmetic.
- **Fix: roof angle and array separation now apply to dual probes only.** The panels hide them for single arrays, but a value left over from a dual setup was still applied, tilting a linear probe out of the X-Z plane unseen and switching off the catalogue wedge outline. This matches the MATLAB GUI, which only reads them for dual probes.
- `session.py` results carry each element's time of flight (`tof_us`).
- `requirements.txt` adds pyvista and pyvistaqt. The Qt tests now run on the native Qt platform with hidden windows, because VTK needs a real render window.

## Migration step 2: the Qt window — 2026-11-19

Plan step 2 (`docs/plans/PLAN-2026-11-qt-vtk-migration.md`).

- **Qt window** (`python/qt_app.py`; qtpy with PySide6), with every feature of the Tk window:
  - the same panels, with the same keys, defaults and visibility rules;
  - menus: configurations, element coordinates, catalogue loading with a filterable picker;
  - Calculate and Export CSV, and a Data Table whose rows select their law;
  - Ray Tracing (toolbar, Show All, Play), Delays (bar chart or per-array delay maps) and 3D View (presets, sweep foci).

  Numbers are read exactly as typed, and a field that isn't a number is refused by name.
- **Shared core:** `session.py` holds the calculation, table rows, CSV and catalogue links, and both windows call it. Identical output is tested: the Tk and Qt tables match for six scan cases, and configurations load both ways. The Tk window's images are unchanged (61/61). `navigation.py` holds the law navigation for the Qt tabs.
- **Refusals in Y sweeps** (review of PR #24): one per requested law, so per skew × Y, and per Y in a sound-path sweep. Python and MATLAB, with three shared cases.
- `build_executable.py` builds the Qt window and bundles `UserManual.md` and `materials.json`. It was still referring to the removed `UserManual.html` and CSVs.
- `requirements.txt` adds PySide6 and qtpy.

## Migration step 1: focal rules and scene model in the library — 2026-11-19

Plan step 1 (`docs/plans/PLAN-2026-11-qt-vtk-migration.md`).

- **Focal rules move out of the GUIs.** `python/focal_rules.py` (`focal_targets`) and its MATLAB twin `matlab/FocalRules.m` (`FocalRules.targets`) cover constant depth, vertical line and sound path, with skew and the three Y modes. Both GUIs call them. `tests/focal_rule_cases.json` (from `python/make_focal_rule_cases.py`) holds 12 shared cases: Python checks that the file is current, and MATLAB's `testFocalRules` gives the same targets and refusals.
- **Refusals instead of silent outcomes.** A vertical-line law parallel to its line (0° refracted angle, or 90° skew) is refused. The Python GUI used to aim it 1000 km down; MATLAB skipped it. A skew that puts a vertical-line focus above the surface is refused per law; Python used to abort the whole calculation. Refused rows in the Data Table show "-" instead of repeating the next law's number. The MATLAB GUI reports how many laws were refused.
- **Scene model.** `python/scene_model.py` builds every view's geometry as primitives in the global frame (mm), each with a role: elements, wedge, probe body, dimensions, envelope rays, rays, interface points, foci. `scene.py` only draws them. All 61 reference images (seven setups in both projections, 3D and delay maps, plus eight GUI scan cases) are pixel-identical before and after, apart from the refused vertical-line law above (`tests/refactor_check/`).

## Review, catalogues and visualisation — 2026-11-19

Catalogues (Python):
- Load probes and wedges from buildFE catalogues (`catalog/probes.json`, `wedges.json`, format 0.1) or the nde-knowledge export (`exports/catalog`, version 1): File → Load Probe / Wedge from Catalogue. buildFE entries are checked against their stamped content hash, recomputed exactly as `buildfe.asset.digest` (verified against every stamp in buildFE's catalogue). buildFE's wedge frame maps onto this calculator's with X = x, Z = −y: element 1's seat gives the offset and the height at element 1. Saved configurations record each asset's id, file hash, content hash, stamp status and whether the panel still matches it.

Visualisation (Python):
- New 3D View tab (mplot3d): wedge body, interface and backwall planes, active/inactive elements, rays from every active element (at most 48, ends kept), interface points, the sweep's focal points, camera presets.
- Delays tab: per-array delay map for matrix probes, labelled with element numbers in the chosen numbering convention; inactive elements marked on the linear bar chart.
- Catalogue wedges are drawn from their true outline in the X-Z and 3D views.
- Step buttons and a law readout reach every law, including Y-sweep laws that share an angle and skew; table rows select their exact law in every tab; zoom/pan toolbar on the ray-tracing tab.

Fixes:
- Dual matrix probes in row-first order selected first-array elements for second-array numbers (Python and MATLAB).
- Sub-aperture laws gave NaN Min/Max Delay in the table and a NaN Delays-tab scale.
- Play on matrix sweeps mixed the flat law index with the angle slider.
- Loading a configuration did not restore the Y focus mode.
- `main.py`, `verify_delays.py` and `main.m` took the central ray's height from Y instead of Z; `main.m` failed outright on its `calculateLaw(fx, fz, mode)` call, which MATLAB `calculateLaw` now accepts.
- Critical-angle error rows read "Brit".
- The manual and README described column-first / row-first the wrong way round (column-first numbers up each column: Y fastest).
- Generated CSVs and `__pycache__` files are no longer tracked.

## Sub-aperture central ray — 2026-10-25

- Angle/skew focal targets (constant depth, vertical line, constant sound path) start the refracted central ray at the centre of the active sub-aperture, not the whole array, in both GUIs (`DelayLaw.aperture_centre` / `apertureCentre`). Full-aperture laws are unchanged; 16-element sub-aperture laws on a 32-element array move by up to about 10 mm. Matches buildFE and imageFE.

## Review corrections — 2026-10-22

- Replace the 3D Newton/fallback solver with a scaled, bracketed planar Snell solve in Python and MATLAB; refuse invalid geometry and wave modes.
- Invalidate Python geometry caching when the mutable probe, wedge or active aperture changes, and return independent active-index arrays.
- Preserve X in MATLAB's legacy two-coordinate call. Rotate both legs of GUI central-ray targets with skew; correct the manual's solver and equal-speed descriptions.
- Add analytic Snell, grazing-ray, 2D/3D, cache mutation, input refusal, GUI angle and MATLAB legacy-call regression checks. The 2D quartic and max-TOF delay definition are retained.
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Ray-tracing scene context: wedge body with dimension annotations, schematic probe housing, component fill and optional backwall (new display-only Thickness field in Component Settings), and an on-plot legend.
- Inactive sub-aperture elements are now drawn as grey open squares, distinct from active elements.
- `python/scene.py`: toolkit-independent scene drawing shared by the GUI panels and the standalone visualisation script.
- MATLAB GUI: delay-profile bar chart matching the Python Delays tab.

### Changed
- Show All law overlay now uses the perceptually uniform `viridis` colormap instead of `jet`.
- Plot framing is now computed explicitly from the drawn geometry with padding, instead of relying on axis autoscaling.
- The ray-tracing and delay-histogram panels share a common law-navigation base class (removes duplicated slider/index logic).

### Fixed
- Envelope rays were drawn to the origin when the first or last probe element was outside the active sub-aperture; rays now bound the first/last *active* element of each array (Python and MATLAB).

## [0.2.0] - 2026-03-08
### Added
- Sub-aperture selection (start element and active elements subset) to restrict pulsing elements.
- Element numbering convention settings for matrix probes (Column-first and Row-first).
- Full MATLAB implementation parity, including `DelayLaw`, `Probe`, `Wedge`, `Material`, and `DualProbe` classdef files.
- MATLAB legacy GUI (`PhasedArrayGUI.m`) supporting 3D ray tracing, skew angles, and dual matrix arrays.
- Export options for focal laws (.csv, .mat) and element coordinates (.mat, .m).
- Markdown-based comprehensive User Manual (`UserManual.md`) replacing the HTML version.

### Changed
- `calculate_law` functions (Python and MATLAB) output `NaN` for inactive elements to preserve shape indexing.
- Fixed MATLAB GUI rendering and layout clipping issues using a compact direct-on-figure layout.
- Recreated README.md with detailed feature lists and Python/MATLAB quickstart API sections.

## [0.1.0] - 2026-03-06
