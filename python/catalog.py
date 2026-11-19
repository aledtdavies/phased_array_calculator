"""
Probe and wedge catalogues: read buildFE and nde-knowledge catalogue files and map their
entries onto this calculator's Probe and Wedge inputs.

Two file formats are read, detected from their content:

* ``buildfe-0.1``: buildFE ``catalog/probes.json`` / ``catalog/wedges.json`` (buildFE
  docs/formats/ASSET_LIBRARY.md). Every value is ``{value, source}`` and each entry may carry a
  stamped content hash ``sha256``. The hash is recomputed here exactly as
  ``buildfe.asset.digest`` does (SHA-256 of ``buildfe-asset:v1|<kind>|<canonical values>``,
  sorted keys, numbers as ``%.17g``, a wedge's ``nominal`` block left out), so an entry is
  reported ``ok``, ``changed`` or ``unstamped`` as ``buildfe.asset.check`` would report it.
* ``nde-knowledge-1``: the values-only export ``exports/catalog/{probes,wedges}.json`` of
  nde-knowledge (``catalogVersion`` "1"), the source buildFE copies in (buildFE Task 167).
  Plain SI values, no per-value provenance, no content hash; the file's own SHA-256 identifies
  the copy that was read.

Frames and units (SI throughout, angles in degrees only where a name ends in ``_deg``/``Deg``):

* Probe: elements numbered 1..N along the primary axis (calculator X); for matrix arrays the
  secondary axis is calculator Y.
* Wedge: buildFE's wedge frame has x along the contact face, x = 0 at the low end of the probe
  face, y up from the contact face, elements ascending up the face towards +x, the beam leaving
  towards +x. The calculator's global frame is X along the same face, Z = -y (Z > 0 in the
  component), so a catalogue wedge maps with X = x, Z = -y: element 1's centre (x1, y1) gives
  ``probe_offset_x = x1`` and ``height_at_element1 = y1``, and the face angle is the wedge angle.
  A face that descends towards +x would need a mirrored frame and is refused, never flipped.
* Wedge height is referred to element 1, the phased-array convention (the aperture is
  selectable), not to an index point.

Nothing is guessed: a value a catalogue does not give is left ``None`` and listed in the
asset's ``missing`` list for the user to enter, and a value derived here is listed in
``notes``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from typing import Optional

FORMAT_BUILDFE = "buildfe-0.1"
FORMAT_NDE_KNOWLEDGE = "nde-knowledge-1"

# Catalogue probe types the calculator can represent, and the calculator's name for each.
PROBE_TYPES = {
    "linear-array": "Linear",
    "matrix-array": "Matrix",
    "dual-linear-array": "Dual Linear",
    "dual-matrix-array": "Dual Matrix",
}

_SOURCE_STATUSES = {"datasheet", "literature", "measured", "provisional"}
_APERTURE_TOL = 0.05   # relative pitch x n vs printed aperture disagreement worth a note


class CatalogError(ValueError):
    """A catalogue file or entry that cannot be read or mapped."""


# ---------------------------------------------------------------------------
# buildFE content hash (buildfe.asset.digest / buildfe.config.canonical)
# ---------------------------------------------------------------------------
def _numeric_array(x):
    """
    The values of a JSON list as MATLAB's jsondecode holds them, flattened as
    buildfe.config.canonical writes them (x(:)', column-major), or None when
    jsondecode would give a cell array (mixed or ragged content). A list of
    numbers is a vector; equal-length nested numeric lists are a matrix (or
    N-D array) whose first index is the outer list.
    """
    def numeric(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    def shape(v):
        if numeric(v):
            return ()
        if isinstance(v, (list, tuple)) and v:
            inner = {shape(e) for e in v}
            if len(inner) == 1 and None not in inner:
                return (len(v),) + inner.pop()
        return None

    s = shape(x)
    if not s:
        return None
    flat = []

    # Index tuples with the first index varying fastest (column-major).
    def indices(dims):
        if not dims:
            yield ()
            return
        for rest in indices(dims[1:]):
            for i in range(dims[0]):
                yield (i,) + rest

    for idx in indices(s):
        v = x
        for i in idx:
            v = v[i]
        flat.append(v)
    return flat


def _canonical(x) -> str:
    if isinstance(x, dict):
        return "{" + ",".join(json.dumps(k) + ":" + _canonical(x[k]) for k in sorted(x)) + "}"
    if isinstance(x, (list, tuple)):
        flat = _numeric_array(x)
        if flat is not None:
            if len(flat) == 1:
                return _canonical(flat[0])      # jsondecode gives a scalar
            return "[" + ",".join(_canonical(v) for v in flat) + "]"
        return "[" + ",".join(_canonical(v) for v in x) + "]"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, str):
        return json.dumps(x, ensure_ascii=False)
    if isinstance(x, (int, float)):
        v = float(x)
        if v == 0:
            v = 0.0            # -0 is written as 0
        return format(v, ".17g")
    raise CatalogError(f"cannot serialise a value of type {type(x).__name__}")


def buildfe_digest(spec: dict, kind: str) -> str:
    """SHA-256 content hash of a buildFE asset's values (buildfe.asset.digest)."""
    if kind == "wedge":
        spec = {k: v for k, v in spec.items() if k != "nominal"}
    text = f"buildfe-asset:v1|{kind}|{_canonical(spec)}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
@dataclass
class CatalogRef:
    """Where an asset came from, kept with configurations so a setup can be traced."""
    kind: str                       # 'probe' or 'wedge'
    id: str
    manufacturer: str
    model: str
    file: str
    file_sha256: str
    format: str
    catalog_version: str
    sha256: Optional[str] = None    # buildFE content hash, computed (buildFE files only)
    stamp: str = "not-applicable"   # 'ok', 'changed', 'unstamped' or 'not-applicable'

    def as_dict(self) -> dict:
        return dict(self.__dict__)

    def label(self) -> str:
        tail = f", hash {self.sha256[:12]} ({self.stamp})" if self.sha256 else ""
        return f"{self.id} [{self.format}{tail}]"


@dataclass
class ProbeAsset:
    ref: CatalogRef
    probe_type: str                 # calculator probe type
    num_elements: int               # per array, primary axis
    pitch: Optional[float]          # m
    frequency: Optional[float]      # Hz
    num_elements_y: int = 1
    pitch_y: Optional[float] = None
    element_width: Optional[float] = None
    elevation: Optional[float] = None
    sources: dict = field(default_factory=dict)   # value name -> source status
    notes: list = field(default_factory=list)
    missing: list = field(default_factory=list)

    def panel_values(self) -> dict:
        """Probe panel fields (GUI units: mm, MHz) for the values the catalogue gives."""
        vals = {"probe_type": self.probe_type, "num_elements": self.num_elements,
                "num_elements_y": self.num_elements_y}
        if self.pitch is not None:
            vals["pitch_mm"] = self.pitch * 1e3
        if self.pitch_y is not None:
            vals["pitch_y_mm"] = self.pitch_y * 1e3
        if self.frequency is not None:
            vals["freq_mhz"] = self.frequency * 1e-6
        return vals


@dataclass
class WedgeAsset:
    ref: CatalogRef
    angle_deg: Optional[float]
    height_at_element1: Optional[float]   # m, element 1 centre above the contact face
    velocity: Optional[float]             # m/s, longitudinal
    probe_offset_x: Optional[float]       # m, element 1 x in the wedge frame
    shear_velocity: Optional[float] = None
    material: Optional[str] = None
    outline: Optional[list] = None        # [(x, y), ...] wedge frame, m, anticlockwise
    nominal_angle_deg: Optional[float] = None
    nominal_mode: Optional[str] = None
    sources: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    missing: list = field(default_factory=list)

    def panel_values(self) -> dict:
        vals = {}
        if self.angle_deg is not None:
            vals["angle_deg"] = self.angle_deg
        if self.height_at_element1 is not None:
            vals["height_mm"] = self.height_at_element1 * 1e3
        if self.velocity is not None:
            vals["velocity_ms"] = self.velocity
        if self.probe_offset_x is not None:
            vals["offset_mm"] = self.probe_offset_x * 1e3
        return vals

    def outline_global_mm(self):
        """Outline in the calculator's X-Z plane (mm): X = x, Z = -y."""
        if self.outline is None:
            return None
        return [(x * 1e3, -y * 1e3) for x, y in self.outline]


# ---------------------------------------------------------------------------
# Catalogue file
# ---------------------------------------------------------------------------
class Catalog:
    """One catalogue file: probes and/or wedges."""

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        if not os.path.isfile(self.path):
            raise CatalogError(f"catalogue file not found: {path}")
        with open(self.path, "rb") as f:
            raw = f.read()
        self.file_sha256 = hashlib.sha256(raw).hexdigest()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise CatalogError(f"{path} is not a JSON catalogue: {e}") from None
        if not isinstance(data, dict) or not ({"probes", "wedges"} & set(data)):
            raise CatalogError(f"{path} has neither a 'probes' nor a 'wedges' list")
        self.catalog_version = str(data.get("catalogVersion", ""))
        self.probes = list(data.get("probes", []))
        self.wedges = list(data.get("wedges", []))
        self.format = self._detect_format()

    def _detect_format(self) -> str:
        entries = self.probes + self.wedges
        if self.catalog_version == "0.1" or any(
                isinstance(v, dict) and "value" in v and "source" in v
                for e in entries for g in ("parameters", "material", "outline")
                if isinstance(e.get(g), dict) for v in e[g].values()):
            return FORMAT_BUILDFE
        if self.catalog_version == "1":
            return FORMAT_NDE_KNOWLEDGE
        raise CatalogError(f"{self.path}: unknown catalogue format (catalogVersion "
                           f"'{self.catalog_version}'); expected buildFE 0.1 or nde-knowledge 1")

    # -- listing ----------------------------------------------------------
    def entries(self, kind: str):
        if kind not in ("probe", "wedge"):
            raise CatalogError("kind must be 'probe' or 'wedge'")
        return self.probes if kind == "probe" else self.wedges

    def summary(self, kind: str):
        """[(id, manufacturer, model, type_or_family, usable, reason)] for a picker."""
        rows = []
        for e in self.entries(kind):
            try:
                asset = self.probe(e["id"]) if kind == "probe" else self.wedge(e["id"])
                usable = True
                reason = ("needs: " + ", ".join(asset.missing)) if asset.missing else ""
            except CatalogError as err:
                usable, reason = False, str(err)
            rows.append((e.get("id", ""), e.get("manufacturer", ""), e.get("model", ""),
                         e.get("type", e.get("family", "")), usable, reason))
        return rows

    def _find(self, kind, id_):
        for e in self.entries(kind):
            if e.get("id") == id_:
                return e
        raise CatalogError(f"no {kind} '{id_}' in {self.path}")

    # -- buildFE value blocks ---------------------------------------------
    def _buildfe_values(self, e, kind, groups):
        """Replace {value, source} by values; refuse unsourced values (buildfe.array.catalogEntry)."""
        sources = e.get("sources", {})
        spec, status = {}, {}
        for g in groups:
            block = e.get(g)
            if block is None:
                continue
            for name, item in block.items():
                if not isinstance(item, dict) or "value" not in item or "source" not in item:
                    raise CatalogError(f"{kind} '{e['id']}': {g}.{name} has no {{value, source}}")
                src = sources.get(item["source"])
                if src is None:
                    raise CatalogError(f"{kind} '{e['id']}': {g}.{name} cites undefined "
                                       f"source '{item['source']}'")
                if src.get("status") not in _SOURCE_STATUSES:
                    raise CatalogError(f"{kind} '{e['id']}': source '{item['source']}' has "
                                       f"unknown status '{src.get('status')}'")
                if g == "parameters":
                    spec[name] = item["value"]
                else:
                    spec.setdefault(g, {})[name] = item["value"]
                status[f"{g}.{name}"] = src["status"]
        return spec, status

    def _ref(self, kind, e, spec=None):
        ref = CatalogRef(kind=kind, id=e["id"], manufacturer=e.get("manufacturer", ""),
                         model=e.get("model", ""), file=self.path, file_sha256=self.file_sha256,
                         format=self.format, catalog_version=self.catalog_version)
        if self.format == FORMAT_BUILDFE and spec is not None:
            ref.sha256 = buildfe_digest(spec, kind)
            stamped = e.get("sha256")
            ref.stamp = "unstamped" if not stamped else ("ok" if stamped == ref.sha256 else "changed")
        return ref

    # -- probes -----------------------------------------------------------
    def probe(self, id_: str) -> ProbeAsset:
        e = self._find("probe", id_)
        if self.format == FORMAT_BUILDFE:
            spec, status = self._buildfe_values(e, "probe", ["parameters"])
            ref = self._ref("probe", e, spec)
            vals = dict(spec)
        else:
            status = {}
            ref = self._ref("probe", e)
            vals = e
        ptype = e.get("type")
        if ptype not in PROBE_TYPES:
            raise CatalogError(f"probe '{id_}' is a {ptype}; the calculator handles "
                               f"{', '.join(PROBE_TYPES)} only")
        n = vals.get("nElements")
        if (not isinstance(n, (int, float)) or isinstance(n, bool) or not math.isfinite(n)
                or n < 1 or n != int(n)):
            raise CatalogError(f"probe '{id_}' has no usable element count")
        n = int(n)
        notes, missing = [], []
        is_matrix = ptype in ("matrix-array", "dual-matrix-array")
        ny = 1
        if is_matrix:
            ny = vals.get("nElementsSecondary")
            if (not isinstance(ny, (int, float)) or isinstance(ny, bool) or not math.isfinite(ny)
                    or ny < 1 or ny != int(ny)):
                raise CatalogError(f"matrix probe '{id_}' has no usable secondary element count "
                                   f"(got {ny!r})")
            ny = int(ny)

        pitch = _pitch(vals.get("pitch"), vals.get("activeAperture"), n, "pitch", notes)
        pitch_y = None
        if is_matrix:
            pitch_y = _pitch(vals.get("pitchSecondary"), vals.get("activeApertureSecondary"), ny,
                             "secondary pitch", notes)
            if pitch_y is None:
                missing.append("secondary pitch")
        if pitch is None:
            missing.append("pitch")
        freq = vals.get("centreFrequency")
        if freq is None:
            missing.append("frequency")
        if ptype.startswith("dual-"):
            missing.append("array separation (not in the catalogue)")
        if e.get("sourceInconsistency"):
            notes.append("catalogue note: " + e["sourceInconsistency"])
        if "(one of its two arrays)" in e.get("model", ""):
            notes.append("entry describes one array of a dual probe")
        provisional = sorted(k for k, s in status.items() if s == "provisional")
        if provisional:
            notes.append("provisional values: " + ", ".join(provisional))
        return ProbeAsset(ref=ref, probe_type=PROBE_TYPES[ptype], num_elements=n, pitch=pitch,
                          frequency=freq, num_elements_y=ny, pitch_y=pitch_y,
                          element_width=vals.get("elementWidth"), elevation=vals.get("elevation"),
                          sources=status, notes=notes, missing=missing)

    # -- wedges -----------------------------------------------------------
    def wedge(self, id_: str) -> WedgeAsset:
        e = self._find("wedge", id_)
        if self.format == FORMAT_BUILDFE:
            return self._buildfe_wedge(e)
        return self._nde_wedge(e)

    def _buildfe_wedge(self, e) -> WedgeAsset:
        spec, status = self._buildfe_values(e, "wedge", ["material", "outline", "nominal"])
        ref = self._ref("wedge", e, spec)
        mat, outline = spec.get("material", {}), spec.get("outline", {})
        geom = wedge_outline(outline, e["id"])
        notes = []
        provisional = sorted(k for k, s in status.items() if s == "provisional")
        if provisional:
            notes.append("provisional values: " + ", ".join(provisional))
        missing = []
        if mat.get("longitudinalSpeed") is None:
            missing.append("wedge velocity")
        nominal = spec.get("nominal", {})
        return WedgeAsset(ref=ref, angle_deg=geom["angle_deg"],
                          height_at_element1=geom["first_element"][1],
                          velocity=mat.get("longitudinalSpeed"),
                          probe_offset_x=geom["first_element"][0],
                          shear_velocity=mat.get("shearSpeed"), material=mat.get("name"),
                          outline=geom["vertices"],
                          nominal_angle_deg=nominal.get("refractedAngleDeg"),
                          nominal_mode=nominal.get("mode"), sources=status, notes=notes,
                          missing=missing)

    def _nde_wedge(self, e) -> WedgeAsset:
        ref = self._ref("wedge", e)
        notes, missing = [], []
        angle = e.get("wedgeAngleDeg")
        if angle is None:
            missing.append("wedge angle")
        missing += ["height at element 1", "wedge velocity"]
        if e.get("material"):
            notes.append(f"material named '{e['material']}' without a wave speed")
        if e.get("curvature") and str(e["curvature"]).lower() != "flat":
            notes.append(f"curved wedge ({e['curvature']}); the calculator models a flat interface")
        if e.get("sourceInconsistency"):
            notes.append("catalogue note: " + e["sourceInconsistency"])
        return WedgeAsset(ref=ref, angle_deg=angle, height_at_element1=None, velocity=None,
                          probe_offset_x=None, material=e.get("material"),
                          nominal_angle_deg=e.get("nominalAngleDeg"), nominal_mode=e.get("wave"),
                          notes=notes, missing=missing)


def _pitch(pitch, aperture, n, name, notes):
    """The printed pitch, or aperture / n (DERIVED, noted) when only the aperture is given."""
    if pitch is not None:
        if aperture is not None and n > 0 and aperture > 0:
            if abs(pitch * n - aperture) > _APERTURE_TOL * aperture:
                notes.append(f"{name} x elements = {pitch * n * 1e3:.2f} mm differs from the "
                             f"printed aperture {aperture * 1e3:.2f} mm")
        return pitch
    if aperture is not None and n > 0:
        notes.append(f"{name} derived as aperture / elements = {aperture * 1e3:.3f} mm / {n}")
        return aperture / n
    return None


def wedge_outline(outline: dict, id_: str = "") -> dict:
    """
    A buildFE wedge outline (buildfe.array.wedgeOutline) as vertices, face angle and element 1.

    Wedge frame: x along the contact face, y up from it, metres. 'simple': contactLength, height,
    faceAngleDeg, firstElement [x, y] (flat base, a low vertical toe at x = 0, the probe face
    rising at faceAngleDeg through element 1, a flat cap at y = height, a vertical rear).
    'polygon': vertices, faceEdge [i, j] (1-based; elements ascend from vertex i towards j),
    firstElementAlong (from vertex i). Returns vertices (anticlockwise), angle_deg and
    first_element (x, y). Refuses outlines buildFE refuses, and faces the calculator cannot
    represent (a face descending towards +x).
    """
    kind = outline.get("type")
    if kind == "simple":
        L, H = outline["contactLength"], outline["height"]
        a = outline["faceAngleDeg"]
        x1, y1 = outline["firstElement"]
        if not 0 < a < 90:
            raise CatalogError(f"wedge '{id_}': faceAngleDeg must lie between 0 and 90 (got {a})")
        t = math.tan(math.radians(a))
        toe = y1 - x1 * t
        cap_x = x1 + (H - y1) / t
        if not (0 < toe < H and 0 < cap_x < L):
            raise CatalogError(f"wedge '{id_}': the simple outline cannot pass through element 1 "
                               f"at [{x1:g} {y1:g}] m (toe height {toe:g} m, cap at x = {cap_x:g} m)")
        verts = [(0.0, 0.0), (L, 0.0), (L, H), (cap_x, H), (0.0, toe)]
        return {"vertices": verts, "angle_deg": float(a), "first_element": (float(x1), float(y1))}
    if kind == "polygon":
        V = [tuple(map(float, v)) for v in outline["vertices"]]
        i, j = (int(k) - 1 for k in outline["faceEdge"])
        along = float(outline["firstElementAlong"])
        K = len(V)
        if K < 3 or not all(math.isfinite(c) for v in V for c in v):
            raise CatalogError(f"wedge '{id_}': an outline needs at least 3 finite vertices")
        if (j - i) % K not in (1, K - 1):
            raise CatalogError(f"wedge '{id_}': faceEdge is not an edge of the outline")
        area = 0.5 * sum(V[k][0] * V[(k + 1) % K][1] - V[(k + 1) % K][0] * V[k][1] for k in range(K))
        (sx, sy), (ex, ey) = V[i], V[j]
        if area < 0:
            V = V[::-1]
        if sum(abs(v[1]) < 1e-12 for v in V) < 2:
            raise CatalogError(f"wedge '{id_}': the outline has no contact face on y = 0")
        dx, dy = ex - sx, ey - sy
        length = math.hypot(dx, dy)
        if not (dx > 0 and dy > 0):
            raise CatalogError(f"wedge '{id_}': the probe face must rise towards +x with the "
                               f"elements ascending (the calculator's frame); this face does not")
        x1, y1 = sx + along * dx / length, sy + along * dy / length
        return {"vertices": V, "angle_deg": math.degrees(math.atan2(dy, dx)),
                "first_element": (x1, y1)}
    raise CatalogError(f"wedge '{id_}': unknown outline type '{kind}'")


def default_catalog_dir() -> Optional[str]:
    """A catalogue folder to open first: $PAC_CATALOG_DIR, else a sibling buildFE checkout."""
    env = os.environ.get("PAC_CATALOG_DIR")
    if env and os.path.isdir(env):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    for rel in (("..", "..", "buildFE", "catalog"),
                ("..", "..", "nde-knowledge", "exports", "catalog")):
        d = os.path.normpath(os.path.join(here, *rel))
        if os.path.isdir(d):
            return d
    return None
