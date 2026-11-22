# Third-party notices

## arim

`python/beam_field.py` contains `_f0` and the L-wave strip directivity copied from arim
(https://github.com/ndtatbristol/arim), `src/arim/model.py`, commit 0cee9de, under the MIT licence:

```
MIT License

Copyright (c) 2016-2025 arim contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## The browser version's third-party files

The browser version (`web/`, built by `tools/build_web.py`) ships these files unchanged, at the
pinned versions below. Each keeps its own licence.

| Component | Version | Licence | Shipped as |
|---|---|---|---|
| [Pyodide](https://pyodide.org) (CPython for WebAssembly), with its Python standard library | 314.0.8 | MPL-2.0 (Pyodide); PSF licence (CPython) | `pyodide/` in the self-contained build, otherwise loaded from jsDelivr |
| NumPy | 2.4.6 (Pyodide build) | BSD-3-Clause | `pyodide/numpy-*.whl` |
| SciPy | 1.18.0 (Pyodide build) | BSD-3-Clause | `pyodide/scipy-*.whl` |
| micropip, pyparsing, typing-extensions, fonttools | Pyodide 314.0.8's builds | MPL-2.0; MIT; PSF; MIT | `pyodide/*.whl` (for DXF welds) |
| [ezdxf](https://github.com/mozman/ezdxf) | 1.4.5 | MIT | `wheels/ezdxf-1.4.5-py3-none-any.whl` |
| [plotly.js](https://github.com/plotly/plotly.js) (`plotly.js-dist-min`) | 4.3.0 | MIT (below) | `vendor/plotly.min.js` |

Each wheel carries its licence text inside it (`*.dist-info/`). The plotly.js licence:

```
MIT License

Copyright (c) 2016-2024 Plotly Technologies Inc.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```
