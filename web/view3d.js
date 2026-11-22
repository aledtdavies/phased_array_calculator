// The 3D view for the browser version: the desktop's 3D tab (scene_vtk.py) in Plotly's WebGL
// scenes. The same scene primitives, solids (scene_model.solid_prims: cross-sections extruded
// across Y), bounds, section plane and camera presets as the desktop. Frame: mm, X along the
// wedge, Y across, Z down; -Z is up on screen, so depth is drawn downward.
"use strict";
(() => {
const { COLOURS, TURBO, COVERAGE_NAME, BASE_LAYOUT, PLOT_CONFIG, narrow } = window.PacViews;

// Camera presets: (azimuth, elevation) in degrees of the view direction, as scene_vtk.VIEWS.
const VIEWS3D = { Iso: [-35, 28], "X-Z": [0, 0], "Y-Z": [-90, 0], Top: [0, 89.9] };
const SOLID_STYLE = { component: ["#94a3b8", 0.10, "Component"], wedge: ["#22c55e", 0.15, "Wedge"], weld: ["#fcd34d", 0.30, "Weld"] };
const SOLID_EDGE = { component: "#334155", wedge: "#15803d", weld: "#92400e" };
const FUSION3D = { "fusion-face": ["#92400e", "Fusion faces"], "fusion-covered": ["#16a34a", "Fusion face, covered"],
                   "fusion-gap": ["#dc2626", "Fusion face, gap"] };
const VIRIDIS = [[0, "#440154"], [0.25, "#3b528b"], [0.5, "#21918c"], [0.75, "#5ec962"], [1, "#fde725"]];
const ARRAY_NAME = { single: "Elements", tx: "Tx elements", rx: "Rx elements" };

// Plotly keeps +z up on screen whatever the camera's up vector, so the scene is drawn turned 180
// degrees about X: plotted (x, -y, -z). A rotation, not a mirror: the views read as the desktop's,
// with depth downward; the Y and Z axes are labelled with the true values.
const xs = (c) => c.map((p) => p[0]), ys = (c) => c.map((p) => -p[1]), zs = (c) => c.map((p) => -p[2]);
function lines3d(polylines) {                      // polylines -> x, y, z with gaps between them
  const x = [], y = [], z = [];
  for (const s of polylines) { for (const p of s) { x.push(p[0]); y.push(-p[1]); z.push(-p[2]); } x.push(null); y.push(null); z.push(null); }
  return { x, y, z };
}
// A cross-section (x, z) with its triangles, extruded from y0 to y1: a closed mesh, and its
// feature edges (both caps, and the lengthwise edges at corners sharper than 30 degrees, as the
// desktop's extract_feature_edges(30)).
function prism(xz, tris, y0, y1) {
  const n = xz.length, x = [], y = [], z = [], I = [], J = [], K = [];
  for (const yy of [y0, y1]) for (const p of xz) { x.push(p[0]); y.push(-yy); z.push(-p[1]); }
  for (const t of tris) { I.push(t[0], t[0] + n); J.push(t[1], t[1] + n); K.push(t[2], t[2] + n); }
  for (let a = 0; a < n; a++) { const b = (a + 1) % n; I.push(a, b); J.push(b, b + n); K.push(a + n, a + n); }
  const edges = [];
  for (const yy of [y0, y1]) edges.push(xz.concat([xz[0]]).map((p) => [p[0], yy, p[1]]));
  for (let a = 0; a < n; a++) {
    const p0 = xz[(a - 1 + n) % n], p1 = xz[a], p2 = xz[(a + 1) % n];
    const u = [p1[0] - p0[0], p1[1] - p0[1]], v = [p2[0] - p1[0], p2[1] - p1[1]];
    const nu = Math.hypot(u[0], u[1]), nv = Math.hypot(v[0], v[1]); if (!nu || !nv) continue;
    if ((u[0] * v[0] + u[1] * v[1]) / (nu * nv) < Math.cos(Math.PI / 6)) edges.push([[p1[0], y0, p1[1]], [p1[0], y1, p1[1]]]);
  }
  return { x, y, z, i: I, j: J, k: K, edges };
}
function niceTicks(a, b, n = 6) {                 // round tick values over [a, b]
  const raw = (b - a) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) || 10 * mag;
  const out = []; for (let t = Math.ceil(a / step) * step; t <= b + 1e-9 * step; t += step) out.push(Math.round(t / step) * step);
  return out;
}
function quadMesh(coords) {                        // groups of four corners -> two triangles each
  const I = [], J = [], K = [];
  for (let q = 0; q + 3 < coords.length; q += 4) { I.push(q, q); J.push(q + 1, q + 2); K.push(q + 2, q + 3); }
  return { x: xs(coords), y: ys(coords), z: zs(coords), i: I, j: J, k: K };
}
// A preset camera (scene_vtk.set_camera): from +Y (so +X runs right with -Z up), turned by the
// azimuth, raised by the elevation. Axis views are parallel projections; the oblique view is not.
function cameraFor(view) {
  const [az, el] = VIEWS3D[view].map((d) => d * Math.PI / 180);
  const d = [Math.cos(el) * Math.sin(az), Math.cos(el) * Math.cos(az), -Math.sin(el)], r = narrow() ? 3.6 : 2.0;   // phones: further back, the scene fits the narrow view
  // in the plotted (x, -y, -z) frame: the eye's y and z, and the up vector, change sign
  return { eye: { x: r * d[0], y: -r * d[1], z: -r * d[2] }, center: { x: 0, y: 0, z: 0 },
           up: view === "Top" ? { x: 0, y: 1, z: 0 } : { x: 0, y: 0, z: 1 },
           projection: { type: view === "Iso" ? "perspective" : "orthographic" } };
}

// data: setup and law primitives, v3 (calc's view3d: lo, hi, section_y, solids), pick (the
// element readout, with its position and interface point), focus, field (beam field sections or
// null), section and locus (the check boxes), numbers (element numbers), camera (a preset to apply).
function drawScene3D(div, data) {
  const { setup, law, v3, pick, field, section, locus, numbers } = data;
  const lo = v3.lo, hi = v3.hi, cut = section ? v3.section_y : -Infinity;
  const traces = [], legend = new Set();
  const named = (t, name) => {
    t.name = name || ""; t.showlegend = !!name && !legend.has(name); if (name) { legend.add(name); t.legendgroup = name; } return t;
  };
  // the section keeps the part on the +Y side of the plane (as the desktop's clip)
  const clipY = (y0, y1) => [Math.max(y0, cut), y1];
  const lineTrace = (polys, line, extra = {}) => Object.assign({ type: "scatter3d", mode: "lines", hoverinfo: "skip", line }, lines3d(polys), extra);
  const markerTrace = (c, marker, extra = {}) => Object.assign({ type: "scatter3d", mode: "markers", x: xs(c), y: ys(c), z: zs(c), hoverinfo: "skip", marker }, extra);
  const meshTrace = (m, color, opacity) => ({ type: "mesh3d", x: m.x, y: m.y, z: m.z, i: m.i, j: m.j, k: m.k, color, opacity,
                                              flatshading: true, hoverinfo: "skip", lighting: { ambient: 0.85, diffuse: 0.35, specular: 0.05 } });

  for (const s of v3.solids) {
    const [y0, y1] = clipY(s.y0, s.y1); if (!(y1 > y0)) continue;
    const m = prism(s.xz, s.tris, y0, y1);
    const [col, op] = SOLID_STYLE[s.role];
    const name = s.role === "wedge" ? (s.source === "catalogue" ? "Wedge (catalogue)" : "Wedge (schematic)") : SOLID_STYLE[s.role][2];
    traces.push(named(meshTrace(m, col, op), name));
    traces.push(lineTrace(m.edges, { color: SOLID_EDGE[s.role], width: 1.5 }, { showlegend: false }));
  }
  if (!v3.solids.some((s) => s.role === "component")) {      // no thickness: the interface plane
    const y0 = Math.max(lo[1], cut);
    traces.push(named(meshTrace({ x: [lo[0], hi[0], hi[0], lo[0]], y: [-y0, -y0, -hi[1], -hi[1]], z: [0, 0, 0, 0], i: [0, 0], j: [1, 2], k: [2, 3] },
                                "#94a3b8", 0.15), "Interface"));
  }
  const faces = setup.some((q) => q.role === "element-face");
  for (const p of setup) {
    const m = p.meta || {};
    const col = !m.active ? COLOURS.inactive : (m.array === "tx" ? COLOURS.tx : COLOURS.active);
    if (p.role === "element-face") {
      let name = m.active ? ARRAY_NAME[m.array] : "Inactive elements";
      if (m.schematic && m.active) name += " (schematic size)";
      if (m.active) traces.push(named(meshTrace(quadMesh(p.coords), col, 1), name));
      else {
        const outl = []; for (let q = 0; q + 3 < p.coords.length; q += 4) outl.push([0, 1, 2, 3, 0].map((k) => p.coords[q + k]));
        traces.push(named(lineTrace(outl, { color: col, width: 1.5 }), name));
      }
    } else if (p.role === "element") {          // the centres: what a tap picks
      traces.push(named(markerTrace(p.coords, { color: col, size: faces ? 2.5 : 4 },
                                    { customdata: m.indices, meta: "element", hoverinfo: "text",
                                      text: (m.indices || []).map((i) => `element ${numbers ? numbers[i] : i + 1}`) }),
                        faces ? null : (m.active ? ARRAY_NAME[m.array] : "Inactive elements")));
    } else if (FUSION3D[p.role]) {              // each run of a fusion face as a strip along Y
      const [y0, y1] = clipY(lo[1], hi[1]); if (!(y1 > y0)) continue;
      const strips = [];
      for (let a = 0; a + 1 < p.coords.length; a++) { const A = p.coords[a], B = p.coords[a + 1];
        strips.push([A[0], y0, A[2]], [B[0], y0, B[2]], [B[0], y1, B[2]], [A[0], y1, A[2]]); }
      const [fc, name] = FUSION3D[p.role];
      traces.push(named(meshTrace(quadMesh(strips), fc, 0.85), name));
    } else if (p.role === "coverage") {
      traces.push(named(meshTrace(quadMesh(p.coords), COLOURS.coverageEdge[m.leg] || "#64748b", 0.15), COVERAGE_NAME[m.leg] || "Coverage"));
    } else if (p.role === "focus-sweep" && locus && p.coords.length > 1) {
      traces.push(named(markerTrace(p.coords, { size: 3.5, color: m.law, colorscale: VIRIDIS, showscale: false }), "Focal points (sweep)"));
    }
  }
  for (const p of law || []) {
    const m = p.meta || {};
    if (p.role === "ray") {
      const segs = []; for (let a = 0; a + 1 < p.coords.length; a += 2) segs.push([p.coords[a], p.coords[a + 1]]);
      traces.push(named(lineTrace(segs, { color: COLOURS.ray[m.array] || COLOURS.ray.single, width: 1.5 }, { opacity: 0.6 }), "Rays"));
    } else if (p.role === "interface-point") {
      traces.push(named(markerTrace(p.coords, { size: 2, color: "#000" }), "Interface points"));
    } else if (p.role === "central-ray") {
      traces.push(named(lineTrace([p.coords], { color: "#000", width: 4 }), "Central ray (skips)"));
    } else if (p.role === "focus") {
      traces.push(named(markerTrace(p.coords, { size: 6, color: "#000" },
                                    { hoverinfo: "text", text: [`F = (${p.coords[0].map((v) => (+v).toFixed(1)).join(", ")}) mm`] }), "Focal point"));
    }
  }
  for (const [k, s] of (field || []).entries()) {   // beam field sections: turbo, -30 to 0 dB
    const X = [], Y = [], Z = [], xz = s.name === "X-Z";
    for (const z of s.z) { X.push(s.h.map((h) => (xz ? h : s.fixed[1]))); Y.push(s.h.map((h) => -(xz ? s.fixed[1] : h))); Z.push(s.h.map(() => -z)); }
    traces.push({ type: "surface", x: X, y: Y, z: Z, surfacecolor: s.db, colorscale: TURBO, cmin: -30, cmax: 0, showscale: k === 0,
                  colorbar: narrow() ? { title: { text: "dB" }, len: 0.3, thickness: 9, x: 1, xanchor: "right", y: 1, yanchor: "top", tickfont: { size: 9 } }
                                     : { title: { text: "Beam field (dB)" }, len: 0.5, thickness: 14 }, hoverinfo: "skip", name: `Beam field ${s.name}`,
                  lighting: { ambient: 1, diffuse: 0, specular: 0, fresnel: 0 }, showlegend: false });
  }
  if (pick) {
    traces.push(named(markerTrace([pick.position], { size: 7, color: COLOURS.pick, line: { color: "#000", width: 1 } }), "Selected element"));
    if (pick.active && pick.interface && data.focus)
      traces.push(lineTrace([[pick.position, pick.interface, data.focus]], { color: COLOURS.pick, width: 6 }, { showlegend: false }));
  }
  // axes over the bounds; Y and Z plotted negated, so their ticks are labelled with the true values
  const ax = (t, a, b, flip) => {
    const o = { title: { text: t }, range: flip ? [-b, -a] : [a, b], showbackground: false, gridcolor: "#e2e8f0", zeroline: false, tickfont: { size: 10 } };
    if (flip) { const v = niceTicks(a, b); o.tickvals = v.map((t) => -t); o.ticktext = v.map((t) => String(+t.toFixed(6))); }
    return o;
  };
  const span = [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]], big = Math.max(...span);
  const scene = { xaxis: ax("X (mm)", lo[0], hi[0]), yaxis: ax("Y (mm)", lo[1], hi[1], true), zaxis: ax("Z depth (mm)", lo[2], hi[2], true),
                  aspectmode: "manual", aspectratio: { x: 1.6 * span[0] / big, y: 1.6 * span[1] / big, z: 1.6 * span[2] / big },
                  dragmode: "turntable", uirevision: data.revision };
  if (narrow()) scene.domain = { x: [0, 1], y: [0, 1] };   // phones: the colour bar lies over the scene, not beside it
  if (data.camera) scene.camera = data.camera;
  const layout = Object.assign({}, BASE_LAYOUT, {
    margin: { l: 0, r: 0, t: 8, b: 0 }, showlegend: !narrow(), legend: { x: 0, y: 1, bgcolor: "rgba(255,255,255,0.85)", font: { size: 11 } },
    uirevision: data.revision, scene,
    height: narrow() ? Math.round(Math.max(320, Math.min(560, div.clientWidth * 1.05))) : undefined,
  });
  return Plotly.react(div, traces, layout, PLOT_CONFIG);
}

Object.assign(window.PacViews, { drawScene3D, cameraFor, VIEWS3D });
})();
