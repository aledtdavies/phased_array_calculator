// Drawing for the browser version: the desktop's scene primitives (scene_model.py), the delays
// and the beam field, with Plotly (pan and zoom by mouse or touch). Colours follow the desktop
// views (scene.py, qt_views2d.py). Frame: mm, X along the wedge, Y across, Z down (drawn down).
"use strict";

const COLOURS = {
  active: "#dc2626", tx: "#2563eb", inactive: "#94a3b8", ray: { single: "#2563eb", tx: "#1f77b4", rx: "#d62728" },
  wedgeFace: "rgba(34,197,94,0.22)", wedgeEdge: "#15803d", probeFace: "rgba(100,116,139,0.35)", probeEdge: "#334155",
  material: "rgba(148,163,184,0.18)", backwall: "#334155", focus: "#dc2626", sweep: "#93c5fd", pick: "#f59e0b",
  weldFace: "rgba(252,211,77,0.35)", weldEdge: "#92400e",
  coverage: { 1: "rgba(37,99,235,0.16)", 2: "rgba(124,58,237,0.14)", 3: "rgba(219,39,119,0.12)" },
  coverageEdge: { 1: "#2563eb", 2: "#7c3aed", 3: "#db2777" },
  fusion: { "fusion-face": ["#92400e", 2.5, "Fusion faces"], "fusion-covered": ["#16a34a", 4, "Fusion face, covered"],
            "fusion-gap": ["#dc2626", 4, "Fusion face, gap"] },
};
const COVERAGE_NAME = { 1: "Coverage, direct", 2: "Coverage, 1st skip", 3: "Coverage, 2nd skip" };
const PLOT_CONFIG = { responsive: true, displaylogo: false, scrollZoom: true,
                      modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"], edits: { shapePosition: false } };
const BASE_LAYOUT = { margin: { l: 52, r: 12, t: 30, b: 42 }, paper_bgcolor: "#fff", plot_bgcolor: "#fff",
                      font: { family: "system-ui, Segoe UI, Arial", size: 12 }, dragmode: "pan",
                      legend: { orientation: "h", y: -0.16, font: { size: 11 } }, hovermode: "closest" };

// Turbo (Google's colour map; Mikhailov's polynomial fit), as the desktop's dB maps.
function turboRgb(t) {
  const c = (v) => Math.round(Math.max(0, Math.min(255, v)));
  const r = 34.61 + t * (1172.33 + t * (-10793.56 + t * (33300.12 + t * (-38394.49 + t * 14825.05))));
  const g = 23.31 + t * (557.33 + t * (1225.33 + t * (-3574.96 + t * (1073.77 + t * 707.56))));
  const b = 27.2 + t * (3211.1 + t * (-15327.97 + t * (27814 + t * (-22569.18 + t * 6838.66))));
  return `rgb(${c(r)},${c(g)},${c(b)})`;
}
const TURBO = [...Array(33).keys()].map((i) => [i / 32, turboRgb(i / 32)]);

const narrow = () => window.matchMedia("(max-width: 600px)").matches;   // phones: no legend, more plot
// On narrow screens an equal-scale plot is as tall as its data needs (not padded to a fixed height).
function fitHeight(div, hSpan, zSpan, extra = 110) {
  if (!narrow()) return undefined;
  const w = Math.max(200, div.clientWidth - 70);
  return Math.round(Math.max(220, Math.min(560, w * zSpan / Math.max(hSpan, 1e-9) + extra)));
}

const P = (coords, dim) => [coords.map((c) => c[dim]), coords.map((c) => c[2])];

function pairs(coords, dim) {                      // 'segments': consecutive pairs of points
  const h = [], z = [];
  for (let i = 0; i + 1 < coords.length; i += 2) {
    h.push(coords[i][dim], coords[i + 1][dim], null); z.push(coords[i][2], coords[i + 1][2], null);
  }
  return [h, z];
}
function closed(coords, dim) {
  const [h, z] = P(coords, dim); return [h.concat([h[0]]), z.concat([z[0]])];
}
function quads(coords, dim) {                      // 'quads': groups of four corners
  const h = [], z = [];
  for (let i = 0; i + 3 < coords.length; i += 4) {
    for (let k = 0; k < 4; k++) { h.push(coords[i + k][dim]); z.push(coords[i + k][2]); }
    h.push(coords[i][dim], null); z.push(coords[i][2], null);
  }
  return [h, z];
}

// Scene primitives -> Plotly traces and annotations for a projection (dim 0: X-Z, 1: Y-Z).
function sceneTraces(prims, dim, opts = {}) {
  const traces = [], notes = [];
  const add = (t) => traces.push(Object.assign({ type: "scatter", hoverinfo: "skip" }, t));
  for (const p of prims) {
    const m = p.meta || {};
    switch (p.role) {
      case "wedge": {
        if (dim === 0) {
          const [h, z] = closed(p.coords, 0);
          add({ x: h, y: z, mode: "lines", fill: "toself", fillcolor: COLOURS.wedgeFace, line: { color: COLOURS.wedgeEdge, width: 1.3 },
                name: m.source === "catalogue" ? "Wedge (catalogue)" : "Wedge (schematic)" });
        } else if (m.y0 !== undefined) {
          const zs = p.coords.map((c) => c[2]), z0 = Math.min(...zs), z1 = Math.max(...zs);
          add({ x: [m.y0, m.y1, m.y1, m.y0, m.y0], y: [z0, z0, z1, z1, z0], mode: "lines", fill: "toself",
                fillcolor: COLOURS.wedgeFace, line: { color: COLOURS.wedgeEdge, width: 1.3 }, name: "Wedge" });
        }
        break;
      }
      case "probe-body":
        if (dim === 0) { const [h, z] = closed(p.coords, 0);
          add({ x: h, y: z, mode: "lines", fill: "toself", fillcolor: COLOURS.probeFace, line: { color: COLOURS.probeEdge, width: 1 }, showlegend: false }); }
        break;
      case "dimension":
        if (dim === 0) { const [h, z] = P(p.coords, 0);
          add({ x: h, y: z, mode: "lines", line: { color: "#15803d", width: 1, dash: "dot" }, showlegend: false });
          if (m.text && m.text_at) notes.push({ x: m.text_at[0], y: m.text_at[1], text: m.text, showarrow: false, font: { color: "#15803d", size: 11 }, xanchor: "left" }); }
        break;
      case "wedge-angle": case "contact":
        if (dim === 0 && m.text) notes.push({ x: p.coords[0][0], y: p.coords[0][2], text: m.text, showarrow: false, font: { color: "#15803d", size: 11 } });
        break;
      case "element": {
        const colour = !m.active ? COLOURS.inactive : (m.array === "tx" ? COLOURS.tx : COLOURS.active);
        const [h, z] = P(p.coords, dim);
        const label = !m.active ? "Inactive elements" : ({ single: "Elements", tx: "Tx elements", rx: "Rx elements" }[m.array] || "Elements");
        add({ x: h, y: z, mode: "markers", marker: { color: m.active ? colour : "rgba(0,0,0,0)", size: 7, symbol: "square",
              line: { color: colour, width: 1.2 } }, name: label, customdata: m.indices, hoverinfo: "text",
              text: (m.indices || []).map((i) => `element ${opts.numbers ? opts.numbers[i] : i + 1}`), meta: "element" });
        break;
      }
      case "focus-sweep": {
        const [h, z] = P(p.coords, dim);
        add({ x: h, y: z, mode: "markers", marker: { color: COLOURS.sweep, size: 5 }, name: "Focal points (sweep)" });
        break;
      }
      case "coverage": {
        const [h, z] = quads(p.coords, dim);
        add({ x: h, y: z, mode: "lines", fill: "toself", fillcolor: COLOURS.coverage[m.leg] || COLOURS.coverage[3],
              line: { color: COLOURS.coverageEdge[m.leg] || "#888", width: 0.4 }, name: COVERAGE_NAME[m.leg] || "Coverage" });
        break;
      }
      case "weld":
        if (dim === 0) { const [h, z] = closed(p.coords, 0);
          add({ x: h, y: z, mode: "lines", fill: "toself", fillcolor: COLOURS.weldFace, line: { color: COLOURS.weldEdge, width: 1.4 }, name: "Weld" }); }
        break;
      case "fusion-face": case "fusion-covered": case "fusion-gap":
        if (dim === 0) { const [c, w, name] = COLOURS.fusion[p.role]; const [h, z] = P(p.coords, 0);
          add({ x: h, y: z, mode: "lines", line: { color: c, width: w }, name, legendgroup: p.role }); }
        break;
      case "envelope-ray": {
        const [h, z] = pairs(p.coords, dim);
        const col = opts.lawColour ? opts.lawColour(m.law) : COLOURS.ray[m.array] || COLOURS.ray.single;
        add({ x: h, y: z, mode: "lines", line: { color: col, width: opts.lawColour ? 1 : 1.6 }, name: "Rays", legendgroup: "rays" });
        break;
      }
      case "ray": {
        const [h, z] = pairs(p.coords, dim);
        add({ x: h, y: z, mode: "lines", line: { color: COLOURS.ray[m.array] || COLOURS.ray.single, width: 0.6 }, opacity: 0.55,
              name: "Rays", legendgroup: "rays", showlegend: false });
        break;
      }
      case "interface-point": {
        const [h, z] = P(p.coords, dim);
        add({ x: h, y: z, mode: "markers", marker: { color: "#0f172a", size: 3.5 }, name: "Interface points" });
        break;
      }
      case "central-ray": {
        const [h, z] = P(p.coords, dim);
        add({ x: h, y: z, mode: "lines", line: { color: "#0f172a", width: 2, dash: "dash" }, name: "Central ray (skips)" });
        break;
      }
      case "focus": {
        if (opts.lawColour) break;
        const [h, z] = P(p.coords, dim);
        add({ x: h, y: z, mode: "markers", marker: { color: COLOURS.focus, size: 14, symbol: "cross-thin", line: { color: COLOURS.focus, width: 3 } },
              name: dim === 0 ? "Focus (drag or place)" : "Focus", hoverinfo: "text", text: h.map((x, i) => `F = (${(+p.coords[i][0]).toFixed(1)}, ${(+p.coords[i][1]).toFixed(1)}, ${(+p.coords[i][2]).toFixed(1)}) mm`) });
        break;
      }
      default: break;                               // element-face, interface-point-all: not drawn in 2D
    }
  }
  return { traces: dedupeLegend(traces), notes };
}

function dedupeLegend(traces) {
  const seen = new Set();
  for (const t of traces) { if (t.showlegend === false) continue; const k = t.name; if (!k) { t.showlegend = false; continue; }
    if (seen.has(k)) t.showlegend = false; else seen.add(k); }
  return traces;
}

// The projection plot of the setup and the current law.
function drawProjection(div, dim, data) {
  const { setup, law, all, frame, thickness, numbers, pick, focusEditable } = data;
  const { traces, notes } = sceneTraces(setup, dim, { numbers });
  if (all) {
    const n = Math.max(1, data.nLaws - 1);
    const col = (i) => `hsl(${220 - 220 * (i / n)},70%,45%)`;
    traces.push(...sceneTraces(all, dim, { lawColour: col }).traces.map((t) => Object.assign(t, { name: "All laws", legendgroup: "all" })));
  }
  if (law) { const t = sceneTraces(law, dim, { numbers }); traces.push(...t.traces); notes.push(...t.notes); }
  if (pick) traces.push({ type: "scatter", x: [pick[dim]], y: [pick[2]], mode: "markers", hoverinfo: "skip", name: "Selected element",
                          marker: { color: COLOURS.pick, size: 13, symbol: "diamond", line: { color: "#000", width: 1 } } });
  for (const t of traces) if (t.showlegend === false && t.name) delete t.showlegend;   // one legend entry per name, across all
  dedupeLegend(traces);
  const lo = frame.lo, hi = frame.hi;
  let h0 = lo[dim], h1 = hi[dim], z0 = Math.min(lo[2], 0), z1 = Math.max(hi[2], thickness || 0);
  const pad = (a, b) => Math.max(2, 0.08 * (b - a));
  const ph = pad(h0, h1), pz = pad(z0, z1);
  if (h1 - h0 < 10) { const c = (h0 + h1) / 2; h0 = c - 10; h1 = c + 10; }
  const shapes = [
    { type: "rect", xref: "x", yref: "y", x0: h0 - 1e3, x1: h1 + 1e3, y0: 0, y1: thickness > 0 ? thickness : z1 + 1e3, fillcolor: COLOURS.material, line: { width: 0 }, layer: "below" },
    { type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: 0, y1: 0, line: { color: "#000", width: 2 } },
  ];
  if (thickness > 0) shapes.push({ type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: thickness, y1: thickness, line: { color: COLOURS.backwall, width: 1.5 } });
  if (focusEditable && data.focus) {
    const f = data.focus, r = 0.012 * Math.max(h1 - h0, z1 - z0);
    shapes.push({ type: "circle", xref: "x", yref: "y", x0: f[0] - r, x1: f[0] + r, y0: f[2] - r, y1: f[2] + r,
                  line: { color: COLOURS.focus, width: 2 }, fillcolor: "rgba(220,38,38,0.15)", editable: true, name: "focus-handle" });
  }
  const layout = Object.assign({}, BASE_LAYOUT, {
    title: { text: dim === 0 ? "Ray tracing X-Z" : "Ray tracing Y-Z (seen from −X)", font: { size: 13 } },
    xaxis: { title: { text: dim === 0 ? "X (mm)" : "Y (mm)" }, range: [h0 - ph, h1 + ph], zeroline: false, gridcolor: "#eef2f7", constrain: "domain" },
    yaxis: { title: { text: "Z depth (mm)" }, range: [z1 + pz, z0 - pz], scaleanchor: "x", scaleratio: 1, zeroline: false, gridcolor: "#eef2f7", constrain: "domain" },
    height: fitHeight(div, h1 - h0 + 2 * ph, z1 - z0 + 2 * pz),
    shapes, annotations: notes, uirevision: data.revision, showlegend: !narrow(),
  });
  return Plotly.react(div, traces, layout, PLOT_CONFIG);
}

// Delays: bars for linear and dual linear arrays, maps for matrix arrays.
function drawDelays(div, probe, law, vmax, pick) {
  const d = law ? law.delays_us : [];
  // one scale across the sweep, widened while a dragged focus needs more (as the desktop view)
  const lawMax = Math.max(0, ...d.filter((v) => v !== null && v !== undefined));
  vmax = Math.max(vmax || 0, lawMax) || 1;
  const numbers = probe.numbers, per = probe.nx * probe.ny, arrays = probe.total / per;
  const names = arrays === 2 ? ["Tx array", "Rx array"] : ["Aperture"];
  const title = law ? (law.custom ? "Delays: dragged focus" : `Delays: law ${law.law + 1}`) : "Delays";
  if (!probe.matrix) {
    const traces = [];
    for (let b = 0; b < arrays; b++) {
      const x = [], y = [], ix = [], ex = [], ey = [];
      for (let k = 0; k < per; k++) { const i = b * per + k; if (d[i] === null || d[i] === undefined) { ex.push(numbers[i]); ey.push(0); } else { x.push(numbers[i]); y.push(d[i]); ix.push(i); } }
      traces.push({ type: "bar", x, y, customdata: ix, name: names[b], marker: { color: arrays === 2 && b === 0 ? COLOURS.tx : "#2563eb" },
                    hovertemplate: "element %{x}: %{y:.4f} µs<extra></extra>" });
      if (ex.length) traces.push({ type: "scatter", x: ex, y: ey, mode: "markers", name: "Inactive", hoverinfo: "skip",
                                   marker: { symbol: "x-thin", size: 7, line: { color: COLOURS.inactive, width: 1.5 } }, showlegend: b === 0 });
    }
    if (pick !== null && pick !== undefined && d[pick] !== null) traces.push({ type: "scatter", x: [numbers[pick]], y: [d[pick]], mode: "markers", name: "Selected", hoverinfo: "skip",
                                                       marker: { color: COLOURS.pick, size: 12, symbol: "triangle-down", line: { color: "#000", width: 1 } } });
    const layout = Object.assign({}, BASE_LAYOUT, { title: { text: title, font: { size: 13 } }, bargap: 0.15,
      xaxis: { title: { text: "Element" }, range: [0.5, probe.total + 0.5] }, yaxis: { title: { text: "Delay (µs)" }, range: [0, (vmax || 1) * 1.1] } });
    return Plotly.react(div, traces, layout, PLOT_CONFIG);
  }
  const traces = [], layout = Object.assign({}, BASE_LAYOUT, { title: { text: title, font: { size: 13 } }, annotations: [] });
  for (let b = 0; b < arrays; b++) {
    const z = [], text = [], cd = [];
    for (let iy = 0; iy < probe.ny; iy++) { const zr = [], tr = [], cr = [];
      for (let ix = 0; ix < probe.nx; ix++) { const i = b * per + ix * probe.ny + iy; zr.push(d[i]); tr.push(`element ${numbers[i]}`); cr.push(i); }
      z.push(zr); text.push(tr); cd.push(cr); }
    const ax = b === 0 ? "" : String(b + 1);
    traces.push({ type: "heatmap", z, text, customdata: cd, x: [...Array(probe.nx).keys()].map((k) => k + 1), y: [...Array(probe.ny).keys()].map((k) => k + 1),
                  colorscale: "Viridis", zmin: 0, zmax: vmax || 1, xaxis: "x" + ax, yaxis: "y" + ax, showscale: b === arrays - 1,
                  colorbar: { title: { text: "µs" } }, hovertemplate: "%{text}<br>X %{x}, Y %{y}<br>%{z:.4f} µs<extra></extra>", hoverongaps: false });
    const w = 1 / arrays;
    // fixed ranges, square cells: the axes shrink to fit ('domain') instead of widening their ranges
    layout["xaxis" + ax] = { domain: [b * w + 0.02, (b + 1) * w - 0.04], title: { text: `${names[b]}: X index` },
                             range: [0.5, probe.nx + 0.5], constrain: "domain", dtick: Math.max(1, Math.ceil(probe.nx / 16)) };
    layout["yaxis" + ax] = { title: { text: b === 0 ? "Y index" : "" }, range: [0.5, probe.ny + 0.5], constrain: "domain",
                             scaleanchor: "x" + ax, dtick: Math.max(1, Math.ceil(probe.ny / 16)) };
    if (pick !== null && pick !== undefined && Math.floor(pick / per) === b) {
      const local = pick % per;
      layout.shapes = [{ type: "rect", xref: "x" + ax, yref: "y" + ax, x0: Math.floor(local / probe.ny) + 0.5, x1: Math.floor(local / probe.ny) + 1.5,
                         y0: (local % probe.ny) + 0.5, y1: (local % probe.ny) + 1.5, line: { color: COLOURS.pick, width: 3 } }];
    }
  }
  return Plotly.react(div, traces, layout, PLOT_CONFIG);
}

// Beam field: one section, dB re the maximum (turbo, 0 to -30), the -6 dB contour, focus and axis.
function drawField(div, sec, focus, metrics, dim) {
  const traces = [
    { type: "heatmap", x: sec.h, y: sec.z, z: sec.db, colorscale: TURBO, zmin: -30, zmax: 0, colorbar: { title: { text: "dB" } },
      hovertemplate: "%{x:.1f}, %{y:.1f} mm<br>%{z:.1f} dB<extra></extra>" },
    { type: "contour", x: sec.h, y: sec.z, z: sec.db, showscale: false, hoverinfo: "skip", name: "−6 dB",
      contours: { start: -6, end: -6, size: 1, coloring: "lines" }, line: { color: "#fff", width: 1.5 }, colorscale: [[0, "#fff"], [1, "#fff"]] },
    { type: "scatter", x: [dim === 0 ? focus[0] : focus[1]], y: [focus[2]], mode: "markers", hoverinfo: "skip", name: "Focus",
      marker: { symbol: "cross-thin", size: 14, line: { color: "#fff", width: 2.5 } } },
  ];
  if (metrics && dim === 0) {
    const zz = [0, sec.z[sec.z.length - 1]], t = Math.tan(metrics.angle_deg * Math.PI / 180);
    traces.push({ type: "scatter", x: zz.map((z) => metrics.exit_x_mm + t * z), y: zz, mode: "lines", hoverinfo: "skip", name: "Beam axis",
                  line: { color: "#fff", width: 1, dash: "dot" } });
  }
  const layout = Object.assign({}, BASE_LAYOUT, { showlegend: false,
    title: { text: `${sec.name} section at ${sec.fixed[0]} = ${sec.fixed[1].toFixed(1)} mm`, font: { size: 13 } },
    xaxis: { title: { text: `${sec.name[0]} (mm)` }, range: [sec.h[0], sec.h[sec.h.length - 1]], zeroline: false, constrain: "domain" },
    yaxis: { title: { text: "Z depth (mm)" }, range: [sec.z[sec.z.length - 1], Math.min(0, sec.z[0])], scaleanchor: "x", zeroline: false, constrain: "domain" },
    height: fitHeight(div, sec.h[sec.h.length - 1] - sec.h[0], sec.z[sec.z.length - 1] - Math.min(0, sec.z[0]), 90) });
  return Plotly.react(div, traces, layout, PLOT_CONFIG);
}

// After a focus moves: widen (never narrow) a projection so the law's rays and focus lie at least
// `margin` of the view's size inside its edges; a view that already shows them is left alone
// (the desktop's reframe_law). Returns true if the view changed.
function ensureVisible(div, dim, prims, margin = 0.1) {
  const fl = div._fullLayout; if (!fl || !fl.xaxis || !prims) return Promise.resolve(false);
  const hs = [], zs = [];
  for (const p of prims) for (const c of p.coords) { hs.push(c[dim]); zs.push(c[2]); }
  if (!hs.length) return Promise.resolve(false);
  const lo = [Math.min(...hs), Math.min(...zs)], hi = [Math.max(...hs), Math.max(...zs)];
  let [x0, x1] = fl.xaxis.range, [zb, zt] = fl.yaxis.range;       // y reversed: [bottom (deep), top]
  const z0 = Math.min(zb, zt), z1 = Math.max(zb, zt);
  const mx = margin * (x1 - x0), mz = margin * (z1 - z0);
  if (lo[0] >= x0 + mx && hi[0] <= x1 - mx && lo[1] >= z0 + mz && hi[1] <= z1 - mz) return Promise.resolve(false);
  const nx0 = Math.min(x0, lo[0] - 2 * mx), nx1 = Math.max(x1, hi[0] + 2 * mx);
  const nz0 = Math.min(z0, lo[1] - 2 * mz), nz1 = Math.max(z1, hi[1] + 2 * mz);
  return Plotly.relayout(div, { "xaxis.range": [nx0, nx1], "yaxis.range": [nz1, nz0] }).then(() => true);
}

// Pixel position on a Plotly 2D plot -> data coordinates (for tap-to-place on touch screens).
function plotToData(div, clientX, clientY) {
  const fl = div._fullLayout; if (!fl || !fl.xaxis) return null;
  const r = div.getBoundingClientRect(), xa = fl.xaxis, ya = fl.yaxis;
  const px = clientX - r.left - xa._offset, py = clientY - r.top - ya._offset;
  if (px < 0 || py < 0 || px > xa._length || py > ya._length) return null;
  return [xa.p2l(px), ya.p2l(py)];
}

window.PacViews = { drawProjection, drawDelays, drawField, plotToData, ensureVisible, COLOURS };
