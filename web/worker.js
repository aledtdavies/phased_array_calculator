// Web Worker (an ES module worker: Pyodide 314 ships as ES modules): runs Pyodide (Python
// compiled to WebAssembly) and the calculator's own Python modules, off the page's thread so the
// page stays responsive while it calculates.
//
// PYODIDE_BASE: where Pyodide is loaded from, as the site's own config.js says (written by
// tools/build_web.py; the page passes it on): the pinned public CDN, or the site's own copy
// ("pyodide/", the --offline build). Anything else is refused: the worker receives the user's
// inputs, so it runs code only from this site or the pinned CDN release (review of PR #37).
const CDN = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
const PYODIDE_BASE = (() => {
  const asked = new URL(self.location.href).searchParams.get("pyodide") || CDN;
  const url = new URL(asked, self.location.href);
  if (url.href !== CDN && url.origin !== self.location.origin) {
    throw new Error("Pyodide must come from this site or " + CDN + ", not " + url.href);
  }
  return url.href.endsWith("/") ? url.href : url.href + "/";
})();
const PY_FILES = ["probe.py", "wedge.py", "material.py", "delay_law.py", "focal_rules.py",
                  "session.py", "beam_field.py", "beam_metrics.py", "pac_web.py"];

let pyodide = null;
const ready = (async () => {
  const t = {};
  let t0 = performance.now();
  const { loadPyodide } = await import(PYODIDE_BASE + "pyodide.mjs");
  pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });
  t.pyodide = (performance.now() - t0) / 1e3;
  t0 = performance.now();
  await pyodide.loadPackage(["numpy", "scipy"]);
  t.packages = (performance.now() - t0) / 1e3;
  t0 = performance.now();
  for (const f of PY_FILES) {
    const r = await fetch("py/" + f);
    if (!r.ok) throw new Error(`cannot load py/${f}: ${r.status}`);
    pyodide.FS.writeFile(f, await r.text());
  }
  pyodide.runPython("import pac_web");
  t.modules = (performance.now() - t0) / 1e3;
  return t;
})();

self.onmessage = async (e) => {
  const { id, op, arg } = e.data;
  try {
    const timings = await ready;
    if (op === "init") {
      self.postMessage({ id, ok: true, result: { timings, python: pyodide.runPython("import sys; sys.version.split()[0]") } });
      return;
    }
    if (!["calc", "field"].includes(op)) throw new Error("unknown operation " + op);
    const fn = pyodide.pyimport("pac_web")[op];
    const t0 = performance.now();
    const text = fn(JSON.stringify(arg));
    const result = JSON.parse(text);
    result.wall = (performance.now() - t0) / 1e3;
    self.postMessage({ id, ok: true, result });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message || err) });
  }
};
