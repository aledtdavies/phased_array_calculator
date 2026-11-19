# Changelog

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
