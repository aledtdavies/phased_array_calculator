# Visualisation Review & Improvement Plan

**Scope:** High-level review of the Phased Array Focal Law Calculator's visualisation
(functionality and visuals, particularly 3D), a comparison against `pogopy`'s geometry
visualisation, and a phased improvement plan. Covers both the Python and MATLAB editions.

---

## 1. Current State

### 1.1 Python edition

| Surface | Location | What it shows |
|---|---|---|
| Ray Tracing tab | `python/plotting.py` → `PlottingPanel` | 2D X-Z projection (plus Y-Z projection for matrix/dual probes). Interface as a bold black line, elements as red squares (blue/red split for dual probes), outer-envelope rays only (first/last element → interface → focal point), focal point marker. Angle + skew sliders, Play animation (~10 fps), Show All overlay coloured by `jet` colormap. |
| Delays tab | `python/plotting.py` → `DelayHistogramPanel` | Bar chart of delay (µs) vs element ID for the selected law, with global-max y-scaling across the sweep. |
| Data Table tab | `python/app.py` | Treeview of law ID, angle, skew, focal coordinates, min/max delay. Row selection drives both plot tabs. |
| Standalone script | `python/visualisation.py` | Single-law 2D plot to PNG with all rays, crude wedge/component `fill_between` shading, legend. Not used by the GUI. |

### 1.2 MATLAB edition

`matlab/PhasedArrayGUI.m` renders the same X-Z / Y-Z envelope-ray projections with
angle/skew sliders (`refreshPlot`, lines ~243–335). It has **no** delay histogram, **no**
data table, and **no** Show All / Play animation — a parity gap with Python beyond just
visuals.

### 1.3 The 3D gap

The solver is genuinely 3D (matrix arrays, azimuth + skew steering, roof angle, 3D
Fermat interface search), and the README advertises "full 3D geometry" — but the
visualisation is only ever two orthogonal 2D projections. Consequences:

- A skewed beam from a matrix array is split across two projections that the user must
  mentally fuse; the actual beam direction and the interface crossing point are never
  shown as one picture.
- The outer-envelope choice (`elements[0]` / `elements[-1]`) is a *geometric* extreme of
  the array, not the extreme of the projected beam. Under skew, the true widest rays in
  the X-Z projection can come from interior elements, so the drawn envelope can
  under-represent the beam footprint.
- Matrix-array delay profiles are shown as a 1D bar chart indexed by flattened element
  ID, which hides the 2D delay surface across the aperture (and makes the
  column-first/row-first convention setting hard to sanity-check visually).

---

## 2. Findings

### 2.1 Defects (both editions unless noted)

- **F1 — Sub-aperture envelope rays are wrong.** `interface_points` is zero-filled for
  inactive elements (`python/delay_law.py:204`, `matlab/DelayLaw.m:176`), but the ray
  drawing always pairs `elements[0]`/`elements[-1]` with `int_pts[0]`/`int_pts[-1]`
  (`python/plotting.py:260-264`, `matlab/PhasedArrayGUI.m:275-290`). With
  `start_element > 1` or a restricted active count, the plot draws rays from a real
  element position to the origin `(0, 0)`. Envelope rays should be drawn from the
  *first/last active* elements (`active_indices` is already in the law result).
- **F2 — Labels but no legend (Python).** `PlottingPanel.refresh_plot` sets
  `label=` on elements/rays but never calls `ax.legend()`, so the Tx/Rx colour coding
  for dual probes is never explained on screen.
- **F3 — Active vs inactive elements indistinguishable.** All elements render as
  identical red squares regardless of sub-aperture state, in both editions.

### 2.2 Quality / maintainability

- **Full-figure redraw per slider tick.** `refresh_plot` calls `figure.clear()` and
  rebuilds every artist on every slider event and every animation frame. Fine at 16
  elements, sluggish with Show All over large sweeps. (pogopy inherited the same
  pattern — not a regression, but the natural place to fix it is here first.)
- **~120 lines duplicated** between `PlottingPanel` and `DelayHistogramPanel`
  (slider/index-map/skew-visibility logic is copy-pasted). A shared law-navigation
  mixin/controller would halve the file and keep the two tabs in sync by construction.
- **`jet` colormap for law index.** Perceptually non-uniform and misleading at the
  cyan/yellow bands; `viridis` is the better default for an ordered quantity like law
  index. (Keep jet-like maps only where NDT display convention expects them, e.g. any
  future S-scan-style amplitude image.)
- **`matplotlib.pyplot.Figure` inside an embedded GUI.** `plotting.py` imports pyplot
  purely to construct figures; embedded canvases should use
  `matplotlib.figure.Figure` directly to avoid pyplot global state (pogopy does this).
- **No scene context.** The GUI plot draws no wedge body, no probe body, no component
  extent — just a line at z = 0. The standalone `visualisation.py` gestures at this
  with hard-coded `fill_between` patches but is disconnected from the GUI.

---

## 3. What pogopy does, and what is portable

`pogopy/gui/canvas/geometry_canvas.py` is explicitly *a port of this repo's*
`plotting.py` (its docstring says so) that was then substantially extended. That has two
consequences: (a) its improvements drop back into this codebase almost verbatim at the
matplotlib level, and (b) anything improved here can flow forward to pogopy again.

### 3.1 Worth porting back (all matplotlib-level, toolkit-independent)

1. **Wedge body overlay** (`_draw_wedge_overlay`): a proper wedge polygon derived from
   angle / element-1 height / offset, with front/back face heights, an optional flat
   height cap, contact-mode detection (elements on the surface → "Contact" annotation
   instead of a degenerate polygon), a probe-body polygon above the wedge, and on-plot
   dimension annotations (`h1`, angle, offset, length). Mirrored Tx/Rx wedges for
   dual-probe setups map directly onto Dual Linear / Dual Matrix here.
2. **Component/domain rendering:** grey material fill + outline rectangle + backwall,
   instead of a bare interface line. Needs one new display-only input (component
   thickness) — worth adding since it also frames "focal point beyond backwall"
   situations that are currently invisible.
3. **Deliberate framing:** accumulate `bounds_x`/`bounds_y` from every drawn artefact
   and set explicit limits with padding (`geometry_canvas.py:456-463`), rather than
   relying on `axis('equal')` autoscale, which currently lets a distant focal point
   crush the wedge region.
4. **Visual polish:** consistent zorder discipline, a restrained hex palette
   (slate/green/orange) instead of matplotlib single-letter colours, legend in the
   corner, `draw_idle()` instead of `draw()`.
5. **Annotated shot label** ("Shot 3/12 — 45.0°") rather than bare slider values.

### 3.2 Not applicable / nothing to take

- **3D:** pogopy's 3D is a stub — `core/geometry_3d.py` raises `NotImplementedError`
  and the GUI warns "3D mode is experimental" and resets state. **This calculator is
  ahead of pogopy on 3D physics; the 3D visualisation has to be designed here**, and
  once built in matplotlib it becomes the thing pogopy can port *from* later.
- **Qt:** pogopy uses qtpy/PyQt6 + `FigureCanvasQTAgg`. Everything listed in §3.1 lives
  in matplotlib Axes/Artist calls, so there is no reason to leave Tkinter to adopt it.
- **Scan-position slider, TFM ROI, flaw markers, absorbing layers, source/receiver
  overlays:** simulation-domain concepts with no counterpart in a focal-law calculator.

---

## 4. Library choice for 3D

Constraint: the MATLAB edition must not diverge from Python without good reason.

| Option | Python | MATLAB counterpart | Verdict |
|---|---|---|---|
| **matplotlib `mplot3d` (recommended)** | Already a dependency; embeds in the existing Tk canvas; line/scatter 3D scenes of this size (≤ ~2k artists) are well within its comfort zone | Native `plot3`/`surf`/`patch`/`view(3)`/`rotate3d` — first-party, zero toolboxes, near 1:1 scene composition | Keeps the two editions structurally identical; no new dependencies |
| pyvista / VTK | True 3D with depth sorting and fast interaction | None — a MATLAB equivalent would be a separate, different implementation | Heavy dependency, awkward Tk embedding, forces divergence. Not justified for ray/point scenes |
| plotly (browser) | Nice interaction, but lives outside the Tk GUI; adds dependency and an export/embed workflow | None comparable | Breaks the single-window GUI model and diverges from MATLAB |

`mplot3d`'s known weaknesses (painter's-algorithm depth sorting, slow dense meshes)
don't bite for this content: rays, element grids, a wedge wireframe, and focal-point
markers. Recommendation: **mplot3d + native MATLAB 3D axes**, revisit only if a future
feature needs rendered beam fields rather than rays.

---

## 5. Plan

### Phase 1 — 2D scene quality & correctness (port from pogopy)

- Fix **F1**: draw envelope rays from the first/last *active* elements using
  `active_indices`; grey-out inactive elements (fixes **F3**); add `ax.legend()`
  (fixes **F2**). Same fixes in `PhasedArrayGUI.m` `refreshPlot`.
- Port the wedge polygon + probe body + dimension annotations, mirrored dual-probe
  wedges, material fill + outline (new optional component-thickness display input),
  and bounds-accumulation framing from `geometry_canvas.py`. MATLAB: `patch()` +
  `text()` equivalents.
- Refactor: shared law-navigation controller for the two Python panels; replace
  `plt.Figure` with `matplotlib.figure.Figure`; switch law-index colouring to
  `viridis`; retire or rewrite `visualisation.py` on top of the shared scene code.
- MATLAB parity beyond visuals: add the missing Delays bar chart (`bar`) and, if
  desired, a results table (`uitable`) to match the Python tabs.

### Phase 2 — 3D view tab (new; this is the part pogopy can't provide)

- New "3D View" tab (Python `mplot3d`, MATLAB 3D axes) showing, in mm:
  element grid as 3D scatter (active/inactive distinguished), wedge as translucent
  patch/wireframe, interface plane, per-element interface points, rays
  element → interface → focal point for the selected law (decimate to every nth
  element beyond ~64 to keep it readable), and the focal-point locus across the whole
  sweep coloured by law index.
- Reuse the existing angle/skew sliders + Show All; add camera presets
  (isometric / top / side buttons — `view(az, el)` in both editions) so the 2D
  projections remain reachable from within the 3D tab.
- Keep the X-Z / Y-Z tabs; the 3D view complements rather than replaces them.

### Phase 3 — Aperture delay map (matrix probes)

- For matrix/dual-matrix probes, replace (or accompany) the 1D delay bar chart with a
  2D aperture heatmap: element grid coloured by delay (µs), inactive elements grey
  (NaN-masked). Python `pcolormesh`/`imshow`, MATLAB `imagesc` with `AlphaData` for
  NaN. This also gives users a direct visual check of the column-first/row-first
  numbering convention.

### Phase 4 — Performance & polish (optional, after the above)

- Replace clear-and-rebuild redraws with artist reuse (`set_data`/`set_offsets`) for
  slider scrubbing and animation; consider blitting for Play mode.
- Unify styling constants (palette, marker sizes, fonts) in one module shared by all
  panels, mirroring pogopy's hex palette so future cross-porting stays mechanical.

### Suggested sequencing

Phase 1 is low-risk and mostly transcription from pogopy — do it first and in both
editions in the same change set. Phase 2 is the substantive new work and the main
answer to the "particularly 3D" brief. Phases 3–4 are independent and can trail.
