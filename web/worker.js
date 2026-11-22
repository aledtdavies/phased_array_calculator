// Web Worker (an ES module worker: Pyodide 314 ships as ES modules): runs Pyodide (Python
// compiled to WebAssembly) and the calculator's own Python modules, off the page's thread so the
// page stays responsive while it calculates.
//
// PYODIDE_BASE: where Pyodide is loaded from, as the site's own config.js says (written by
// tools/build_web.py; the page passes it on): the pinned public CDN, or the site's own copy
// ("pyodide/", the --offline build). Anything else is refused: the worker receives the user's
// inputs, so it runs code only from this site or the pinned CDN release.
const CDN = "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/";
const PYODIDE_BASE = (() => {
  const asked = new URL(self.location.href).searchParams.get("pyodide") || CDN;
  const url = new URL(asked, self.location.href);
  if (url.href !== CDN && url.origin !== self.location.origin) {
    throw new Error("Pyodide must come from this site or " + CDN + ", not " + url.href);
  }
  return url.href.endsWith("/") ? url.href : url.href + "/";
})();
// The calculator's modules, shared with the desktop window (python/), and the browser layer.
const PY_FILES = ["probe.py", "wedge.py", "material.py", "delay_law.py", "focal_rules.py", "session.py",
                  "beam_field.py", "beam_metrics.py", "field_job.py", "scene_model.py", "coverage.py",
                  "weld.py", "catalog.py", "pac_web.py"];
// What the page may ask for: pac_web's functions, nothing else.
const OPS = ["put_file", "catalog_open", "catalog_apply", "catalog_status", "config_loaded", "calc", "law",
             "all_laws", "custom", "element", "laws_csv", "element_coords", "field"];
// DXF welds: ezdxf (a pure-Python wheel shipped with the site) and its dependencies from Pyodide.
const EZDXF_WHEEL = "wheels/ezdxf-1.4.5-py3-none-any.whl";

let pyodide = null;
let ezdxfReady = null;
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
  for (const f of PY_FILES.concat(["materials.json"])) {
    const r = await fetch(new URL("py/" + f, self.location.href));
    if (!r.ok) throw new Error(`cannot load py/${f}: ${r.status}`);
    pyodide.FS.writeFile(f, await r.text());
  }
  pyodide.runPython("import pac_web");
  t.modules = (performance.now() - t0) / 1e3;
  return t;
})();

function ensureEzdxf() {
  if (!ezdxfReady) {
    ezdxfReady = (async () => {
      await pyodide.loadPackage(["micropip", "pyparsing", "typing-extensions", "fonttools"]);
      const micropip = pyodide.pyimport("micropip");
      await micropip.install(new URL(EZDXF_WHEEL, self.location.href).href, { deps: false });
    })();
    ezdxfReady.catch(() => { ezdxfReady = null; });   // a failed load is tried again next time
  }
  return ezdxfReady;
}

self.onmessage = async (e) => {
  const { id, op, arg } = e.data;
  try {
    const timings = await ready;
    if (op === "init") {
      self.postMessage({ id, ok: true, result: { timings, python: pyodide.runPython("import sys; sys.version.split()[0]") } });
      return;
    }
    if (!OPS.includes(op)) throw new Error("unknown operation " + op);
    if (op === "calc" && arg.weld && arg.weld.type === "DXF file") await ensureEzdxf();
    const fn = pyodide.pyimport("pac_web")[op];
    const t0 = performance.now();
    const result = JSON.parse(fn(JSON.stringify(arg)));
    if (["calc", "law", "custom", "all_laws", "field"].includes(op)) result.wall = (performance.now() - t0) / 1e3;
    self.postMessage({ id, ok: true, result });
  } catch (err) {
    // A Python error carries its traceback: the page shows its message (the last lines that are
    // not Pyodide's "See https://..." pointer).
    const lines = String(err && err.message || err).trim().split("\n").map((l) => l.trim()).filter(Boolean);
    while (lines.length > 1 && /^See https?:/.test(lines[lines.length - 1])) lines.pop();
    const msg = lines.pop() || "error";
    self.postMessage({ id, ok: false, error: msg.replace(/^\w*Error: /, "") });
  }
};
