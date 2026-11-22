"""
Assemble the browser prototype as a static site: web/ (page, worker, pac_web.py) and the
calculator's Python modules under py/.

    python tools/build_web.py [out_dir]              # default site/; Pyodide from the public CDN
    python tools/build_web.py [out_dir] --offline    # Pyodide copied in: no internet needed to use it

The site needs only a static web server (GitHub Pages, Netlify, IIS, nginx, or
`python -m http.server` for a local look). Browsers refuse to run it from file:// (the worker
and the module fetches need http).

--offline downloads Pyodide's core files and the numpy and scipy wheels (with their dependencies,
from Pyodide's lock file) into <out_dir>/pyodide/, about 30 MB, and points the page at them, so a
work network without internet access can serve the whole thing. The download happens once, when
the site is built (on CI or any machine with internet access).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = ["probe.py", "wedge.py", "material.py", "delay_law.py", "focal_rules.py", "session.py",
      "beam_field.py", "beam_metrics.py", "field_job.py", "scene_model.py", "coverage.py", "weld.py",
      "catalog.py", "materials.json"]
WEB = ["index.html", "help.html", "style.css", "app.js", "views.js", "worker.js", "panels.json", "web.config"]
# Third-party files the site ships (always, whether or not Pyodide is copied in): pinned versions.
PLOTLY_VERSION = "4.3.0"
PLOTLY_URL = f"https://cdn.jsdelivr.net/npm/plotly.js-dist-min@{PLOTLY_VERSION}/plotly.min.js"
EZDXF_WHEEL = "ezdxf-1.4.5-py3-none-any.whl"
EZDXF_URL = ("https://files.pythonhosted.org/packages/fb/d7/9f420747a1edf562cabff228f8d1f7a16530ad021ea6f84c775ca15dec9b/"
             + EZDXF_WHEEL)
EZDXF_SHA256 = "70a79ec7d40990f60453e3c87ffe9f668907ee061cf6f4c0a3794d032ec2b40e"   # PyPI's published digest
PYODIDE_VERSION = "314.0.8"
PYODIDE_CDN = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_CORE = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
PACKAGES = ["numpy", "scipy", "micropip", "pyparsing", "typing-extensions", "fonttools"]   # the last four: DXF welds (ezdxf)
MARKER = ".pac-web-site"      # written into every built site: only such a folder is ever emptied


def _fetch(url, path):
    with urllib.request.urlopen(url, timeout=120) as r, open(path, "wb") as f:
        shutil.copyfileobj(r, f)


def vendor_pyodide(dest):
    """Pyodide core and the wheels PACKAGES need (dependencies from the lock file) into dest."""
    os.makedirs(dest, exist_ok=True)
    for name in PYODIDE_CORE:
        _fetch(PYODIDE_CDN + name, os.path.join(dest, name))
    with open(os.path.join(dest, "pyodide-lock.json"), encoding="utf-8") as f:
        pkgs = json.load(f)["packages"]
    need, todo = set(), list(PACKAGES)
    while todo:
        k = todo.pop()
        if k not in need:
            need.add(k)
            todo += [d.lower() for d in pkgs[k].get("depends", [])]
    for k in sorted(need):
        _fetch(PYODIDE_CDN + pkgs[k]["file_name"], os.path.join(dest, pkgs[k]["file_name"]))
    return sorted(need)


def vendor_third_party(out):
    """Plotly.js (the charts) and the ezdxf wheel (DXF welds), pinned, into the site."""
    import hashlib
    os.makedirs(os.path.join(out, "vendor"), exist_ok=True)
    _fetch(PLOTLY_URL, os.path.join(out, "vendor", "plotly.min.js"))
    os.makedirs(os.path.join(out, "wheels"), exist_ok=True)
    wheel = os.path.join(out, "wheels", EZDXF_WHEEL)
    _fetch(EZDXF_URL, wheel)
    with open(wheel, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    if digest != EZDXF_SHA256:
        os.remove(wheel)
        raise SystemExit(f"{EZDXF_WHEEL}: SHA-256 {digest} is not PyPI's {EZDXF_SHA256}")


def _check_destination(out):
    """
    Refuse a destination that is not a site this script built: the repository, any folder
    holding it, its source folders, or an existing folder that is neither empty nor marked.
    """
    out = os.path.realpath(out)
    root = os.path.realpath(ROOT)
    if os.path.commonpath([out, root]) == out:
        raise SystemExit(f"refusing to build into {out}: it is the repository or holds it")
    for d in ("python", "web", "tools", "docs", "matlab", "docker", "tests", "validation", ".git", ".github"):
        if os.path.commonpath([out, os.path.join(root, d)]) == os.path.join(root, d):
            raise SystemExit(f"refusing to build into {out}: it is inside the repository's {d}/")
    if os.path.isdir(out) and os.listdir(out) and not os.path.isfile(os.path.join(out, MARKER)):
        raise SystemExit(f"refusing to empty {out}: it is not empty and was not built by this script")
    return out


def build(out, offline=False):
    out = _check_destination(out)
    os.makedirs(out, exist_ok=True)
    for name in os.listdir(out):            # empty it (a server may hold the folder itself open)
        p = os.path.join(out, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    open(os.path.join(out, MARKER), "w").close()
    os.makedirs(os.path.join(out, "py"))
    for f in WEB:
        shutil.copy2(os.path.join(ROOT, "web", f), os.path.join(out, f))
    vendor_third_party(out)
    shutil.copy2(os.path.join(ROOT, "web", "pac_web.py"), os.path.join(out, "py", "pac_web.py"))
    for f in PY:
        shutil.copy2(os.path.join(ROOT, "python", f), os.path.join(out, "py", f))
    shutil.copy2(os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), os.path.join(out, "THIRD_PARTY_NOTICES.md"))
    # the beam field's model note and the figure it shows, at the paths the note and the page use
    os.makedirs(os.path.join(out, "docs", "plans", "images"))
    shutil.copy2(os.path.join(ROOT, "docs", "beam_field_model.html"), os.path.join(out, "docs", "beam_field_model.html"))
    shutil.copy2(os.path.join(ROOT, "docs", "plans", "images", "step6_beam_vs_buildfe.png"),
                 os.path.join(out, "docs", "plans", "images", "step6_beam_vs_buildfe.png"))
    open(os.path.join(out, ".nojekyll"), "w").close()        # GitHub Pages: serve files as they are
    base = ""
    if offline:
        vendor_pyodide(os.path.join(out, "pyodide"))
        base = "pyodide/"
    with open(os.path.join(out, "config.js"), "w", encoding="utf-8") as f:
        f.write("// Written by tools/build_web.py: where the page loads Pyodide from ('' = the public CDN).\n")
        f.write(f"window.PAC_PYODIDE_BASE = {json.dumps(base)};\n")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    print(build(args[0] if args else os.path.join(ROOT, "site"), offline="--offline" in sys.argv))
