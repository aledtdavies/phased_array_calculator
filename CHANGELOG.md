# Changelog
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
