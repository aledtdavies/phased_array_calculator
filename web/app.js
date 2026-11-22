// Page logic of the browser prototype: reads the inputs, asks the worker (Pyodide) to calculate,
// and draws the table, the X-Z ray view, the delays and the beam field. No libraries.
"use strict";
const $ = (id) => document.getElementById(id);
// Where Pyodide comes from is set by the site's own config.js (build time), never by the page's URL.
const pyParam = window.PAC_PYODIDE_BASE || "";
const worker = new Worker("worker.js" + (pyParam ? "?pyodide=" + encodeURIComponent(pyParam) : ""), { type: "module" });
let nextId = 0;
const pending = new Map();
worker.onmessage = (e) => {
  const { id, ok, result, error } = e.data;
  const p = pending.get(id); pending.delete(id);
  ok ? p.resolve(result) : p.reject(new Error(error));
};
worker.onerror = (e) => {               // a failure loading the worker or Pyodide itself
  state.error = `worker: ${e.message || "failed to start"}`;
  status("Could not start Python: " + state.error);
  for (const p of pending.values()) p.reject(new Error(state.error));
  pending.clear();
};
const call = (op, arg) => new Promise((resolve, reject) => {
  const id = nextId++; pending.set(id, { resolve, reject }); worker.postMessage({ id, op, arg });
});

const state = { ready: false, calc: null, law: 0, timings: [], busy: false, error: null, fieldDone: false,
                calcDirty: false, field: null };
window.__pac = state;                       // for automated checks (screenshots, timings)
const num = (id) => parseFloat($(id).value);
const status = (t) => { $("status").textContent = t; };
function timing(name, s) {
  state.timings.push([name, s]);
  $("timings").innerHTML = state.timings.map(([n, v]) => `<tr><td>${n}</td><td>${v.toFixed(2)} s</td></tr>`).join("");
}

// Inputs the laws depend on, and inputs only the beam field depends on.
const FIELD_IDS = ["pulse", "cycles", "grid_mm", "element_width_mm", "wedge_shear_ms", "wedge_density", "component_density"];
const SETUP_IDS = [...document.querySelectorAll("aside input, aside select")].map((e) => e.id).filter((id) => !FIELD_IDS.includes(id));

function lock(on) {                          // nothing changes while Python works on a request
  state.busy = on;
  for (const e of document.querySelectorAll("aside input, aside select, aside button")) e.disabled = on;
  $("lawSlider").disabled = on || !state.calc || state.calc.laws.length < 2;
  if (!on) $("fieldBtn").disabled = !state.calc || !state.calc.laws.length || state.calcDirty;
}

function fieldParams() {
  return { law: state.law, pulsed: $("pulse").value === "1", cycles: num("cycles"), grid_mm: num("grid_mm"),
           element_width_mm: num("element_width_mm"), wedge_shear_ms: num("wedge_shear_ms"),
           wedge_density: num("wedge_density"), component_density: num("component_density") };
}

function markStale(why) {                    // a shown field no longer matches what is selected
  if (!state.field || !state.field.fresh) return;
  state.field.fresh = false;
  $("field").style.opacity = 0.35;
  $("fieldNote").textContent = `Stale (${why}): press “Beam field” again. ` + state.field.text;
}

function config() {
  return {
    probe: { probe_type: "Linear", num_elements: num("num_elements"), pitch_mm: num("pitch_mm"), freq_mhz: num("freq_mhz") },
    wedge: { angle_deg: num("angle_deg"), height_mm: num("height_mm"), velocity_ms: num("velocity_ms"), offset_mm: num("offset_mm") },
    material: { vel_long_ms: num("vel_long_ms"), vel_shear_ms: num("vel_shear_ms"), thickness_mm: num("thickness_mm") },
    sub_aperture: { start_element: num("start_element"), num_active_elements: num("num_active_elements") },
    scan: { wave_type: $("wave_type").value, focus_mode: $("focus_mode").value, param_val: num("param_val"),
            start_angle: num("start_angle"), end_angle: num("end_angle"), step_angle: num("step_angle") },
  };
}

async function calculate() {
  state.error = null; lock(true);
  status("Calculating…");
  try {
    const r = await call("calc", config());
    state.calc = r; state.law = 0; state.calcDirty = false;
    markStale("the laws were recalculated");
    timing(`Calculate ${r.laws.length} laws`, r.wall);
    drawTable(); setupSlider(); drawLaw();
    status(`${r.laws.length} laws calculated in ${r.seconds.toFixed(2)} s.`);
  } catch (err) { state.error = err.message; status("Error: " + err.message); }
  lock(false);
}

async function beamField() {
  if (state.calcDirty) { status("The inputs changed: press “Calculate laws” first."); return; }
  const req = fieldParams();                 // the request as made: the result is labelled with it
  const angle = state.calc.laws[req.law].angle;
  state.error = null; state.fieldDone = false; lock(true);
  status("Computing the beam field…");
  try {
    const r = await call("field", req);
    drawField(r);
    const kind = req.pulsed ? `pulsed, ${req.cycles} cycles` : "continuous wave";
    timing(`Beam field, law ${r.law + 1}: ${r.points} points (${kind}, grid ${r.grid_mm.toFixed(2)} mm)`, r.wall);
    const text = `Law ${r.law + 1} (${angle.toFixed(1)}°): ${r.points} points, grid ${r.grid_mm.toFixed(2)} mm, ${kind}; computed in ${r.seconds_field.toFixed(1)} s. White: −6 dB.`;
    state.field = { law: r.law, params: JSON.stringify(req), fresh: true, text };
    $("field").style.opacity = 1;
    $("fieldNote").textContent = text;
    $("fieldModel").textContent = r.note;
    $("fieldModel").innerHTML = $("fieldModel").innerHTML.replace("docs/beam_field_model.html",
      '<a href="docs/beam_field_model.html" target="_blank" rel="noopener">the model note (docs/beam_field_model.html)</a>');
    status("Beam field done."); state.fieldDone = true;
  } catch (err) { state.error = err.message; status("Error: " + err.message); }
  lock(false);
}

function selectLaw(i) {
  if (state.busy) return;
  state.law = i; $("lawSlider").value = i; drawLaw();
  if (state.field && state.field.law !== i) markStale(`it shows law ${state.field.law + 1}`);
}

for (const id of SETUP_IDS) $(id).addEventListener("input", () => {
  if (!state.calc) return;
  state.calcDirty = true; $("fieldBtn").disabled = true;
  markStale("the inputs changed");
  status("The inputs changed: press “Calculate laws” to update the laws.");
});
for (const id of FIELD_IDS) $(id).addEventListener("input", () => markStale("the field settings changed"));

function drawTable() {
  const r = state.calc;
  $("laws").innerHTML = `<thead><tr>${r.headings.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>` +
    r.rows.map((row) => `<tr data-law="${row[0] === "-" ? "" : Number(row[0]) - 1}">${row.map((v) => `<td>${v}</td>`).join("")}</tr>`).join("") + "</tbody>";
  for (const tr of $("laws").querySelectorAll("tbody tr")) {
    tr.onclick = () => { if (tr.dataset.law !== "") selectLaw(Number(tr.dataset.law)); };
  }
}
function setupSlider() {
  const s = $("lawSlider"); s.max = Math.max(0, state.calc.laws.length - 1); s.value = 0; s.disabled = state.calc.laws.length < 2;
  s.oninput = () => selectLaw(Number(s.value));
}

// ---- drawing helpers --------------------------------------------------------------------
function frame(svg, xs, zs, pad = 30) {
  const W = 600, H = 420;
  let x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
  const s = Math.min((W - 2 * pad) / (x1 - x0 || 1), (H - 2 * pad) / (z1 - z0 || 1));
  const ox = pad + ((W - 2 * pad) - s * (x1 - x0)) / 2, oz = pad + ((H - 2 * pad) - s * (z1 - z0)) / 2;
  return { X: (x) => ox + s * (x - x0), Z: (z) => oz + s * (z - z0), x0, x1, z0, z1 };
}
const el = (tag, attrs) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(" ")}/>`;

function drawLaw() {
  const r = state.calc; if (!r) return;
  if (!r.laws.length) {                      // no valid law: clear what an earlier scan drew
    $("lawLabel").textContent = "No valid law in this scan (see the table's refusals)";
    $("xz").innerHTML = ""; $("delays").innerHTML = "";
    return;
  }
  const law = r.laws[state.law];
  $("lawLabel").textContent = `Law ${state.law + 1}/${r.laws.length}: ${law.angle.toFixed(1)}°, F = (${law.focus[0].toFixed(1)}, ${law.focus[1].toFixed(1)}) mm`;
  for (const tr of $("laws").querySelectorAll("tbody tr")) tr.classList.toggle("sel", tr.dataset.law === String(state.law));
  // X-Z
  const th = num("thickness_mm");
  const allFoci = r.laws.map((l) => l.focus);
  const xs = r.elements.map((p) => p[0]).concat(allFoci.map((f) => f[0])), zs = r.elements.map((p) => p[1]).concat(allFoci.map((f) => f[1]), [th || 0]);
  const f = frame($("xz"), xs, zs);
  let g = `<rect x="0" y="${f.Z(0)}" width="600" height="${Math.max(0, (th ? f.Z(th) : 420) - f.Z(0))}" fill="#e2e8f0"/>`;
  g += el("line", { x1: 0, y1: f.Z(0), x2: 600, y2: f.Z(0), stroke: "#000", "stroke-width": 1.5 });
  if (th) g += el("line", { x1: 0, y1: f.Z(th), x2: 600, y2: f.Z(th), stroke: "#475569", "stroke-width": 1.2 });
  const act = new Set(r.active);
  const n = r.active.length, every = Math.max(1, Math.ceil(n / 24));
  r.active.forEach((ei, k) => {
    if (k % every && k !== n - 1) return;
    const e = r.elements[ei], ip = law.interface[k];
    g += `<polyline points="${f.X(e[0])},${f.Z(e[1])} ${f.X(ip[0])},${f.Z(ip[1])} ${f.X(law.focus[0])},${f.Z(law.focus[1])}" fill="none" stroke="#2563eb" stroke-width="0.9"/>`;
  });
  r.elements.forEach((e, i) => { g += el("circle", { cx: f.X(e[0]), cy: f.Z(e[1]), r: 1.8, fill: act.has(i) ? "#dc2626" : "#94a3b8" }); });
  allFoci.forEach((p) => { g += el("circle", { cx: f.X(p[0]), cy: f.Z(p[1]), r: 2, fill: "#93c5fd" }); });
  const F = law.focus;
  g += `<path d="M${f.X(F[0]) - 7},${f.Z(F[1])}h14M${f.X(F[0])},${f.Z(F[1]) - 7}v14" stroke="#dc2626" stroke-width="2.2"/>`;
  g += `<text x="8" y="414" font-size="11" fill="#64748b">X ${f.x0.toFixed(0)} to ${f.x1.toFixed(0)} mm; Z down</text>`;
  $("xz").innerHTML = g;
  // delays
  const d = law.delays, vmax = Math.max(...r.laws.flatMap((l) => l.delays)) || 1;
  const bw = 540 / d.length;
  let h = el("line", { x1: 40, y1: 390, x2: 590, y2: 390, stroke: "#000" });
  d.forEach((v, i) => { const hh = 350 * v / vmax; h += el("rect", { x: 45 + i * bw, y: 390 - hh, width: Math.max(1, bw - 1), height: hh, fill: "#2563eb" }); });
  for (const t of [0, 0.5, 1]) h += `<text x="4" y="${394 - 350 * t}" font-size="11">${(vmax * t).toFixed(2)}</text>`;
  h += `<text x="250" y="414" font-size="11">active element (µs on the left)</text>`;
  $("delays").innerHTML = h;
}

// turbo colour map (Mikhailov's polynomial approximation), t in 0..1
function turbo(t) {
  t = Math.min(1, Math.max(0, t));
  const r = 34.61 + t * (1172.33 + t * (-10793.56 + t * (33300.12 + t * (-38394.49 + t * 14825.05))));
  const g = 23.31 + t * (557.33 + t * (1225.33 + t * (-3574.96 + t * (1073.77 + t * 707.56))));
  const b = 27.2 + t * (3211.1 + t * (-15327.97 + t * (27814 + t * (-22569.18 + t * 6838.66))));
  return [r, g, b].map((v) => Math.max(0, Math.min(255, v)));
}

function drawField(r) {
  const nz = r.z.length, nx = r.x.length, cv = $("field");
  cv.width = nx; cv.height = nz;
  const ctx = cv.getContext("2d"), img = ctx.createImageData(nx, nz);
  for (let i = 0; i < nz; i++) for (let j = 0; j < nx; j++) {
    const v = r.db[i][j], k = 4 * (i * nx + j);
    let [R, G, B] = turbo((v + 30) / 30);
    const up = i > 0 ? r.db[i - 1][j] : v, left = j > 0 ? r.db[i][j - 1] : v;
    if ((v >= -6) !== (up >= -6) || (v >= -6) !== (left >= -6)) { R = G = B = 255; }   // -6 dB contour
    img.data[k] = R; img.data[k + 1] = G; img.data[k + 2] = B; img.data[k + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  cv.style.aspectRatio = `${(r.x[nx - 1] - r.x[0])} / ${(r.z[nz - 1] - r.z[0])}`;
}

$("calc").onclick = calculate;
$("fieldBtn").onclick = beamField;
(async () => {
  const t0 = performance.now();
  try {
    const r = await call("init");
    timing("Load Pyodide (Python " + r.python + ")", r.timings.pyodide);
    timing("Load numpy and scipy", r.timings.packages);
    timing("Load the calculator's modules", r.timings.modules);
    timing("Ready (total)", (performance.now() - t0) / 1e3);
    state.ready = true; $("calc").disabled = false;
    status("Ready. Python runs in this browser; inputs never leave it.");
  } catch (err) { state.error = err.message; status("Could not start Python: " + err.message); }
})();
