# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
