# Plan: keeping the browser and desktop versions the same

Status: IN PLACE from 2026-11-22 (this plan's checks run on every pull request). The owner asked
for "a plan for maintaining parity between web and desktop".

## The aim

The browser version (GitHub Pages) and the desktop window (Qt) should give **the same results,
show the same things and offer the same controls**. A change made to one should reach the other
in the same pull request, or be recorded as a known gap. Nothing should drift unnoticed.

## How the code keeps them together

1. **One calculation library.** The physics, the geometry, the file formats and the catalogue
   reading all live in `python/`. The browser runs **the same `.py` files** in Pyodide; the worker
   loads them by name (`web/worker.js`, `PY_FILES`). No calculation is written twice, and none is
   written in JavaScript.
2. **Geometry is decided once.** `scene_model.py` turns a calculation into drawing primitives
   (elements, wedge, rays, foci, coverage fans, weld faces). The renderers only draw them:
   - desktop: `qt_views2d.py`, `scene_vtk.py`;
   - browser: `web/views.js`, `web/view3d.js`.

   This pull request moved the 3D view's framing and section plane into `scene_model`
   (`scene_bounds`, `section_y`), and both 3D views use them. The solids are shared only in part:
   - the browser fills them from `solid_prims` and `triangulate_polygon`;
   - the desktop still extrudes the same outlines itself, with PyVista;
   - `test_parity.py` checks that the colours and opacities match.

   Moving the desktop onto `solid_prims` is a small follow-on, listed under known differences.
3. **Thin front ends.** Desktop and browser code (`qt_*.py`, `web/app.js`) handles only inputs,
   layout and events. When both need the same logic, it moves down into `python/`, as was done for:
   - the scan and the law table: `session.py`;
   - the beam-field job: `field_job.py`.

   `web/pac_web.py` is a thin adapter: JSON in, JSON out.
4. **One file format.** Configurations saved in either version open in the other, catalogue
   references included.
5. **Released together.** Every merge to `main` publishes the site (`pages.yml`). The page shows
   the commit it was built from (*Build abc1234 2026-11-22* under the status line), so a
   browser page can always be matched to a desktop version.

## The checks (automatic, on every pull request)

| Check | What it catches | Where |
|---|---|---|
| Same results | The browser's law table, delays, focal-law CSV (byte for byte), element coordinates, beam field, catalogue values, 2D framing and 3D bounds all equal the desktop's, on the shared scan cases (linear, matrix with skew, Y sweeps, dual, refusals) | `python/test_web.py` |
| Same panels | Every value a desktop panel saves (probe, wedge, component, scan, aperture, weld, beam field) is a browser field with the same default, and the browser has no extra ones | `python/test_parity.py` `TestPanels` (Qt, in the Docker job) |
| Same controls | Every desktop tab, menu entry, button, check box and choice is listed in `docs/web_parity.json` with its browser counterpart (checked to exist on the page) or a stated reason. A new desktop control fails the test until it is listed. | `test_parity.py` `TestRegister` |
| Nothing missing in the browser | Every module `pac_web.py` imports, followed through `python/`, is shipped to the browser; no desktop GUI module is needed | `test_parity.py` `TestSharedCode` |
| Same 3D view | The camera presets (Iso, X-Z, Y-Z, Top) and the solid colours and opacities are the desktop's | `test_parity.py` |
| It works in a real browser | Headless Chromium opens the built site, starts Python and draws every tab (Rays, Laws, Delays, Beam field, 3D) for a linear probe with a weld and for a matrix probe, at desktop and phone width; any page error fails it | `tools/web_smoke.py`, CI job `web` |
| It is served correctly | The web server sends the content types browsers need (`.mjs`, `.wasm`, `.py`) | CI job `web` |

**Screenshots on every pull request.** `web_smoke.py` saves its screenshots as the CI artefact
`web-screenshots`, at desktop and phone width, and the Docker job renders the desktop's.
The owner can compare the two without running either.

## The rule for changes (definition of done)

A pull request that changes something a user sees, or any result, either:
- **changes both front ends**, with a test in `test_web.py` or `test_parity.py` where possible, and
  screenshots of both; or
- **records the gap**: adds it to `docs/web_parity.json` (`"web": null` with a `"gap"`) and to the
  table below, with the reason and when it will be closed.

Python changes under `python/` reach the browser automatically. The worker list needs a new module
only if one is added, and `test_parity` says so. For JavaScript, the risk is page code
(`web/app.js`) that grows its own logic. Keep it to inputs and drawing.

## Known differences

| Difference | Why | Plan |
|---|---|---|
| **Exit** menu entry | A browser tab is closed by the browser | None needed |
| **Place focus** (browser only) | Dragging a small handle is awkward on a touch screen; tapping is not | Could be added to the desktop if wanted |
| Catalogue **Usable only** box | The browser always lists unusable entries greyed, with the reason, and they cannot be chosen | None needed |
| **Beam-field progress and Cancel** | The desktop computes in a thread with a progress bar and a Cancel button. The browser waits, which takes seconds for 2D and up to minutes for a 3D field of a matrix probe. | Next: compute in chunks and report progress; cancel by restarting the worker |
| **Desktop 3D solids not yet from `solid_prims`** | The desktop extrudes the wedge, component and weld outlines itself (same outlines, same extents) | Follow-on: `scene_vtk.add_setup` draws `solid_prims` |
| **Look of the 3D view** | Plotly's WebGL, not VTK: lighting, legend and axis styling differ | None needed: the geometry, colours, presets and section are the same and tested |
| **Speed** | Python in the browser runs about 1.2 to 3 times slower than on the desktop. The first visit downloads about 30 MB, about 20 s to start. | Measured in `PLAN-2026-11-web-app.md` |

## Not checked automatically (and why)

- **Pixel-level appearance.** The two renderers differ by design, so screenshots are compared by
  eye, not by a test.
- **Work laptops.** WebAssembly policy and network reach can only be tried there (owner's check,
  `PLAN-2026-11-web-app.md`).

## Files

- `docs/web_parity.json`: the register of desktop controls and their browser counterparts.
- `python/test_parity.py`: the register, panels, shipped modules and 3D checks.
- `python/test_web.py`: the results checks.
- `tools/web_smoke.py`: the real-browser check and screenshots.
- `.github/workflows/headless.yml`: runs all of the above on every pull request.
- `.github/pull_request_template.md`: the parity checklist on each pull request.
