"""
The browser version's Python side (runs in Pyodide, in a Web Worker). A thin layer over the
calculator's own modules, so the browser calculates and draws what the desktop window does:

* session.py      solver, sweep, table rows, focal-law CSV, catalogue links;
* scene_model.py  the geometry every view draws (the same primitives the Qt views draw);
* coverage.py, weld.py   coverage fans and skips, weld outlines and fusion-face gaps;
* field_job.py    the beam field (2D or 3D sections), as the desktop Beam Field tab;
* catalog.py      buildFE / nde-knowledge catalogues.

Every function takes and returns JSON text. Lengths in mm and times in us, as the panels; the
configuration has the desktop's keys, so files save and load in both. Frame: the calculator's
global frame (X along the wedge, Y across, Z down).
"""
from __future__ import annotations

import base64
import json
import math
import os
import time

import numpy as np

import field_job
from beam_field import MODEL_NOTE
from beam_metrics import beam_axis
from catalog import Catalog, CatalogError
from coverage import MODE_ASSUMPTION, SweepCoverage
from scene_model import build_scene, coverage_prims, user_element_numbers, weld_prims
from session import (DUAL_PROBE_TYPES, MATRIX_PROBE_TYPES, TABLE_HEADINGS, CatalogLinks,
                     asset_message, build_solver, calculate, law_result, write_laws_csv)

FLOOR_DB = field_job.FLOOR_DB
MAX_POINTS = field_job.MAX_POINTS[2]
MAX_RAYS = 48
VALIDATION_NOTE = ("Validated in 2D against an FE solve (buildFE Task 125: a steered 45 degree shear beam); "
                   "see docs/beam_field_model.html for where the model can be trusted.")
WELD_TYPES = {"None": None, "Single-V": "single-V", "Double-V": "double-V", "Single-J": "single-J",
              "DXF file": "dxf"}
WELD_FIELDS = {"bevel_deg": ("single-V", "double-V", "single-J"), "bevel2_deg": ("double-V",),
               "root_gap_mm": ("single-V", "double-V", "single-J"),
               "root_face_mm": ("single-V", "double-V", "single-J"), "root_depth_mm": ("double-V",),
               "root_radius_mm": ("single-J",)}
FILES = "/userfiles"                 # files the user opened (DXF, catalogues): Pyodide's memory only

_state = {"links": CatalogLinks(), "catalogs": {}}


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def _num(v):
    """JSON-safe number: NaN and infinities become null."""
    v = float(v)
    return v if math.isfinite(v) else None


def _list(a, nd=4):
    a = np.asarray(a, dtype=float)
    out = np.round(a, nd).tolist()
    if not np.isfinite(a).all():
        def clean(x):
            return [clean(y) for y in x] if isinstance(x, list) else (x if math.isfinite(x) else None)
        out = clean(out)
    return out


def _meta(m):
    out = {}
    for k, v in m.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = float(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = [x.item() if hasattr(x, "item") else x for x in v]
    return out


def _prims(prims, skip=("coverage-extent", "interface-point-all")):
    return [{"kind": p.kind, "role": p.role, "coords": _list(p.coords, 3), "meta": _meta(p.meta)}
            for p in prims if p.role not in skip]


def _out(d):
    return json.dumps(d, allow_nan=False)


def _user_file(name):
    return os.path.join(FILES, os.path.basename(name))


# ---------------------------------------------------------------------------------------------
# files and catalogues
# ---------------------------------------------------------------------------------------------
def put_file(arg):
    """Keep a file the user opened in the browser (base64) in memory; returns its path."""
    a = json.loads(arg)
    os.makedirs(FILES, exist_ok=True)
    path = _user_file(a["name"])
    with open(path, "wb") as f:
        f.write(base64.b64decode(a["data"]))
    return _out({"path": path})


def catalog_open(arg):
    """A catalogue file (already put_file'd): its usable entries for a picker."""
    a = json.loads(arg)
    kind = a["kind"]
    try:
        cat = Catalog(_user_file(a["name"]))
        if not cat.entries(kind):
            raise CatalogError(f"{a['name']} has no {kind}s")
    except CatalogError as e:
        raise ValueError(str(e)) from None
    _state["catalogs"][kind] = cat
    rows = [{"id": r[0], "maker": r[1], "model": r[2], "family": r[3], "usable": bool(r[4]), "reason": r[5]}
            for r in cat.summary(kind)]
    return _out({"format": cat.format, "entries": rows})


def catalog_apply(arg):
    """Apply a catalogue entry: the panel values it sets, the message to show, field inputs."""
    a = json.loads(arg)
    kind = a["kind"]
    cat = _state["catalogs"].get(kind)
    if cat is None:
        raise ValueError("open a catalogue first")
    try:
        asset = cat.probe(a["id"]) if kind == "probe" else cat.wedge(a["id"])
    except CatalogError as e:
        raise ValueError(str(e)) from None
    _state["links"].apply(kind, asset)
    if kind == "probe":
        field = {"element_width_mm": asset.element_width and asset.element_width * 1e3,
                 "elevation_mm": asset.elevation and asset.elevation * 1e3}
    else:
        field = {"wedge_shear_ms": asset.shear_velocity, "wedge_density": asset.density}
    return _out({"values": asset.panel_values(), "message": asset_message(kind, asset),
                 "id": asset.ref.id, "field": {k: v for k, v in field.items() if v is not None}})


def catalog_status(arg):
    """The catalogue references a saved configuration carries (as the desktop window saves)."""
    a = json.loads(arg)
    return _out(_state["links"].status({"probe": a["probe"], "wedge": a["wedge"]}))


def config_loaded(arg):
    """A configuration was loaded into the panels: keep its catalogue references."""
    a = json.loads(arg)
    _state["links"].loaded(a["config"], {"probe": a["config"].get("probe", {}),
                                         "wedge": a["config"].get("wedge", {})})
    return _out({"ok": True})


# ---------------------------------------------------------------------------------------------
# calculation
# ---------------------------------------------------------------------------------------------
def _weld_profile(w, thickness_mm):
    import weld
    k = WELD_TYPES.get(w.get("type", "None"))
    if k is None:
        return None
    if not thickness_mm > 0:
        raise ValueError("set the component Thickness to place a weld")
    if k == "dxf":
        if not w.get("dxf_path"):
            raise ValueError("choose the DXF file of the weld cross-section")
        return weld.dxf_profile(_user_file(w["dxf_path"]), thickness_mm, w["centre_x_mm"],
                                w.get("dxf_datum", "surface"), w.get("dxf_layer") or None,
                                w.get("dxf_units") or None)
    params = {key: float(w[key]) for key, kinds in WELD_FIELDS.items() if k in kinds}
    if k == "single-J":
        params["side"] = w.get("j_side", "near")
    return weld.template_profile(k, thickness_mm, float(w["centre_x_mm"]), **params)


def calc(arg):
    """Every law of the scan, the setup geometry, coverage and weld (Calculate Laws)."""
    t0 = time.perf_counter()
    cfg = json.loads(arg)
    pv = cfg["probe"]
    ptype = pv.get("probe_type", "Linear")
    solver = build_solver(pv, cfg["wedge"], cfg["material"], cfg["sub_aperture"])
    c = calculate(solver, cfg["scan"], ptype)
    links = _state["links"]
    thickness = float(cfg["material"].get("thickness_mm", 0.0) or 0.0)
    st = dict(solver=solver, calc=c, thickness_mm=thickness, custom=None, ptype=ptype,
              outline_mm=links.wedge_outline_mm(cfg["wedge"], ptype),
              element_size_m=links.element_size_m(pv), coverage=None, fusion=None, weld=None)
    _state.update(st)
    notes = {"coverage": "", "weld": "", "weld_error": ""}
    legs = int(cfg.get("view", {}).get("coverage_legs", 0))
    if legs and c.focal_points:
        if not thickness > 0:
            notes["coverage"] = "Set the component Thickness to show coverage."
        else:
            try:
                _state["coverage"] = SweepCoverage(solver, c.results, c.focal_points, thickness * 1e-3, legs,
                                                   c.wave_type.lower())
                notes["coverage"] = MODE_ASSUMPTION
            except (ValueError, ArithmeticError) as e:
                notes["coverage"] = f"No coverage: {e}"
    if c.focal_points and cfg.get("weld"):
        try:
            _state["weld"] = _weld_profile(cfg["weld"], thickness)
        except Exception as e:      # a weld fault must not stop the laws being shown
            notes["weld_error"] = str(e) if isinstance(e, ValueError) else f"{type(e).__name__}: {e}"
        if _state["weld"] is not None:
            import weld
            if _state["coverage"] is not None:
                _state["fusion"] = weld.fusion_coverage(_state["weld"], _state["coverage"])
            notes["weld"] = f"{_state['weld'].source}: " + (
                _state["fusion"].summary() if _state["fusion"] else "turn Coverage on for fusion-face gaps")
    probe = solver.probe
    setup = []
    if c.focal_points:
        scene = build_scene(solver, lambda i: None, [], outline_mm=st["outline_mm"],
                            sweep_focal_mm=np.asarray(c.focal_points) * 1e3,
                            element_size_m=st["element_size_m"])       # footprints: catalogue size or schematic
        setup = scene.prims
        if _state["coverage"] is not None:
            setup = setup + [p for p in coverage_prims(_state["coverage"]) if p.role != "central-ray"]
        if _state["weld"] is not None:
            setup = setup + weld_prims(_state["weld"], _state["fusion"])
    elements = solver._geometry()[0]
    frame = [elements * 1e3]
    if c.focal_points:
        frame.append(np.asarray(c.focal_points) * 1e3)
    if _state["coverage"] is not None:
        frame += [np.asarray(p) * 1e3 for p in _state["coverage"].paths]
    # everything drawn is framed, as the desktop views do: wedge, probe body, weld, fans, labels;
    # a wedge's Y extent (meta y0, y1) frames the Y-Z view
    for p in setup:
        frame.append(np.asarray(p.coords, dtype=float).reshape(-1, 3))
        if p.role == "wedge" and "y0" in p.meta:
            z = np.asarray(p.coords, dtype=float)[:, 2]
            frame.append(np.array([[0.0, p.meta["y0"], z.min()], [0.0, p.meta["y1"], z.max()]]))
    frame = np.vstack(frame)
    return _out({
        "headings": list(TABLE_HEADINGS),
        "rows": [[str(v) for v in values] + [idx] for values, idx in c.rows],
        "laws": [{"angle": r["angle"], "skew": r["skew"], "focus": _list([r["fx"] * 1e3, r["fy"] * 1e3, r["fz"] * 1e3])}
                 for r in c.results],
        "probe": {"type": ptype, "matrix": ptype in MATRIX_PROBE_TYPES, "dual": ptype in DUAL_PROBE_TYPES,
                  "nx": probe.num_elements, "ny": probe.num_elements_y, "total": probe.total_elements,
                  "numbers": user_element_numbers(probe).tolist(),
                  "active": [int(i) for i in probe.get_active_element_indices()]},
        "setup": _prims(setup),
        "frame": {"lo": _list(frame.min(axis=0)), "hi": _list(frame.max(axis=0))},
        "thickness_mm": thickness, "wave": c.wave_type, "notes": notes,
        "global_max_delay": _num(c.global_max_delay) if c.global_max_delay is not None else None,
        "seconds": time.perf_counter() - t0})


def _current(idx):
    c = _state["calc"]
    if idx is None:
        cu = _state["custom"]
        return cu["result"], cu["focal"]
    r = c.results[idx]
    return r, (r["fx"], r["fy"], r["fz"])


def _law_payload(idx):
    """One law's drawing (rays, interface points, focus, central ray) and delays."""
    r, focal = _current(idx)
    solver = _state["solver"]
    target = np.asarray(focal, dtype=float) * 1e3
    key = -1 if idx is None else idx
    scene = build_scene(solver, lambda i: (r["interface_points"] * 1e3, target), [key], current=key,
                        max_rays=MAX_RAYS)
    prims = [p for p in scene.prims if p.role in ("envelope-ray", "ray", "interface-point", "focus")]
    cov = _state["coverage"]
    if cov is not None:
        path = cov.path_for(focal) if idx is None else cov.paths[idx]
        path_mm = np.vstack([solver.aperture_centre()[None, :], path]) * 1e3
        prims += [p for p in coverage_prims(cov, path_mm) if p.role == "central-ray"]
    return {"law": idx, "custom": idx is None, "focus": _list(target),
            "angle": r.get("angle"), "skew": r.get("skew"),
            "prims": _prims(prims), "delays_us": _list(r["delays_us"], 5), "tof_us": _list(r["tof_us"], 5)}


def law(arg):
    """A law of the sweep (drawing and delays); clears a dragged focus."""
    a = json.loads(arg)
    _state["custom"] = None
    return _out(_law_payload(int(a["law"])))


def all_laws(arg):
    """Every law's envelope rays and focus (Show All)."""
    c, solver = _state["calc"], _state["solver"]
    if not c.results:
        return _out({"prims": []})
    get = lambda i: (c.results[i]["interface_points"] * 1e3, np.asarray(c.focal_points[i]) * 1e3)  # noqa: E731
    scene = build_scene(solver, get, list(range(len(c.results))))
    return _out({"prims": _prims([p for p in scene.prims if p.role in ("envelope-ray", "focus")])})


def custom(arg):
    """A law solved for a dragged focus (x, z in mm; Y of the law shown)."""
    a = json.loads(arg)
    _, focal = _current(None if _state["custom"] else int(a["from_law"]))
    x, z = a["x"] * 1e-3, a["z"] * 1e-3
    if not z > 0:
        raise ValueError("the focus must be below the surface (Z > 0)")
    result = law_result(_state["solver"], (x, focal[1], z), _state["calc"].wave_type)
    _state["custom"] = {"result": result, "focal": (x, focal[1], z)}
    return _out(_law_payload(None))


def element(arg):
    """What the views report for an element of the law shown (as the desktop 3D tab)."""
    a = json.loads(arg)
    idx = int(a["index"])
    probe = _state["solver"].probe
    per = probe.num_elements * probe.num_elements_y
    block, local = divmod(idx, per)
    ix, iy = divmod(local, probe.num_elements_y)
    array = ("Tx" if block == 0 else "Rx") if hasattr(probe, "array_separation") else ""
    r, _ = _current(None if _state["custom"] else int(a["law"]))
    delay, tof = float(r["delays_us"][idx]), float(r["tof_us"][idx])
    pos = _state["solver"]._geometry()[0][idx] * 1e3
    return _out({"index": idx, "number": int(user_element_numbers(probe)[idx]), "array": array,
                 "x_index": ix + 1, "y_index": iy + 1, "active": bool(math.isfinite(delay)),
                 "delay_us": _num(delay), "tof_us": _num(tof), "position": _list(pos, 3)})


# ---------------------------------------------------------------------------------------------
# exports
# ---------------------------------------------------------------------------------------------
def laws_csv(arg):
    """The focal-law CSV, exactly as the desktop window writes it."""
    path = "/tmp/laws.csv"
    write_laws_csv(path, _state["calc"].results)
    with open(path, encoding="utf-8") as f:
        return _out({"name": "focal_laws.csv", "text": f.read()})


def element_coords(arg):
    """Element coordinates as the desktop's Export Element Coordinates (csv, m or mat)."""
    a = json.loads(arg)
    fmt = a.get("format", "csv")
    if fmt not in ("csv", "m", "mat"):
        raise ValueError("format is csv, m or mat")
    cfg = a["config"]
    solver = build_solver(cfg["probe"], cfg["wedge"], cfg["material"], cfg["sub_aperture"])
    path = f"/tmp/element_coordinates.{fmt}"
    solver.export_element_positions(path)
    with open(path, "rb") as f:
        data = f.read()
    return _out({"name": os.path.basename(path), "base64": base64.b64encode(data).decode("ascii")})


# ---------------------------------------------------------------------------------------------
# beam field
# ---------------------------------------------------------------------------------------------
def field(arg):
    """The beam field of the law shown (or the dragged focus), as the desktop Beam Field tab."""
    t0 = time.perf_counter()
    a = json.loads(arg)
    v = a["values"]
    r, _ = _current(None if a.get("custom") else int(a["law"]))
    job = field_job.make_job(_state["solver"], r, _state["calc"].wave_type, _state["thickness_mm"], v)
    t1 = time.perf_counter()
    field_job.run_job(job)
    t2 = time.perf_counter()
    secs = []
    metrics = None
    for s in job["sections"]:
        h, z = s["h"] * 1e3, s["z"] * 1e3
        secs.append({"name": s["name"], "h": _list(h, 3), "z": _list(z, 3), "fixed": [s["fixed"][0], s["fixed"][1] * 1e3],
                     "db": _list(s["db"], 2)})
        if s["name"] == "X-Z":
            try:
                m = beam_axis(10 ** (s["db"] / 20), h, z, depths_mm=(r["fz"] * 1e3,))
                metrics = {"angle_deg": m.angle_deg, "exit_x_mm": m.exit_x_mm,
                           "width6_mm": _num(m.width6_mm[0]), "peak": [m.peak_x_mm, m.peak_z_mm]}
            except ValueError:
                pass
    return _out({"law": a.get("law"), "custom": bool(a.get("custom")), "sections": secs, "metrics": metrics,
                 "focus": _list([r["fx"] * 1e3, r["fy"] * 1e3, r["fz"] * 1e3]),
                 "grid_mm": job["step_mm"], "points": int(sum(len(s["h"]) * len(s["z"]) for s in secs)),
                 "note": MODEL_NOTE + ". " + VALIDATION_NOTE,
                 "seconds_field": t2 - t1, "seconds": time.perf_counter() - t0})
