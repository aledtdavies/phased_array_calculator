// The browser version's page: input panels (web/panels.json, the desktop panels' fields and
// rules), the calculation through the worker (Pyodide running the calculator's own Python), law
// navigation, the views (views.js) and files (configurations, catalogues, DXF, exports).
// Nothing is sent anywhere: files are read in the browser and results are saved by download.
"use strict";
const $ = (id) => document.getElementById(id);
const V = window.PacViews;

// ---- worker ---------------------------------------------------------------------------------
// Where Pyodide comes from is set by the site's own config.js (build time), never by the page's URL.
const pyBase = window.PAC_PYODIDE_BASE || "";
const worker = new Worker("worker.js" + (pyBase ? "?pyodide=" + encodeURIComponent(pyBase) : ""), { type: "module" });
let nextId = 0;
const pending = new Map();
worker.onmessage = (e) => {
  const { id, ok, result, error } = e.data;
  const p = pending.get(id); if (!p) return; pending.delete(id);
  ok ? p.resolve(result) : p.reject(new Error(error));
};
worker.onerror = (e) => {
  S.error = `worker: ${e.message || "failed to start"}`;
  status("Could not start Python: " + S.error, true);
  for (const p of pending.values()) p.reject(new Error(S.error));
  pending.clear();
};
const call = (op, arg = {}) => new Promise((resolve, reject) => {
  const id = nextId++; pending.set(id, { resolve, reject }); worker.postMessage({ id, op, arg });
});

// ---- state ----------------------------------------------------------------------------------
const S = {
  ready: false, busy: false, error: null, schema: null, materials: null,
  calc: null, law: null, lawIndex: 0, custom: false, all: null, pick: null, pickInfo: null,
  dirty: false, field: null, fieldFresh: false, fieldSections: null, view3d: "Iso", camRev: 0, play: null, timings: [], revision: 0, placing: false,
  edits: 0,                                         // counts input edits: a result is current only if none came in while it was computed
  focusRev: 0,                                      // counts law and focus changes (sweep law, dragged or placed focus)
};
window.__pac = S;                                   // for automated checks

function status(text, error = false) { const s = $("status"); s.textContent = text; s.classList.toggle("error", error); }
let toastTimer = null;
function toast(text, error = false, ms = 4500) {
  const t = $("toast"); t.textContent = text; t.classList.toggle("error", error); t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// While Python works on a request, nothing it depends on can change: every input, the coverage
// and Show-all controls, files and the law bar are locked (as the desktop window locks its panels).
function busy(on, text) {
  S.busy = on;
  for (const e of document.querySelectorAll("#panels input, #panels select, #panels button, #coverage, #showAll, #placeBtn, #fileBtn"))
    e.disabled = on;
  $("calcBtn").disabled = on || !S.ready;
  $("fieldBtn").disabled = on || !S.calc || !S.calc.laws.length || S.dirty;
  for (const id of ["prevLaw", "nextLaw", "playBtn", "angleSlider", "skewSlider"]) $(id).disabled = on || !S.calc || S.calc.laws.length < 2;
  if (text) status(text);
}

// ---- panels ---------------------------------------------------------------------------------
const W = {};                                       // widgets by "section.key"
function fieldVisible(sec, f, vals) {
  const s = f.show; if (!s) return true;
  const ptype = vals.probe.probe_type, matrix = S.schema.matrix.includes(ptype), dual = S.schema.dual.includes(ptype);
  const ymode = vals.scan.y_focus_mode;
  if (s === "matrix") return matrix;
  if (s === "dual") return dual;
  if (s === "matrix+fixedY") return matrix && ymode === "Fixed Y";
  if (s === "matrix+ysweep") return matrix && ymode === "Y Sweep";
  if (s === "field3d") return vals.beam_field.model === "3D";
  if (s === "weld") return vals.weld.type !== "None";
  if (s.startsWith("weld:")) return s.slice(5).split(",").includes(vals.weld.type);
  return true;
}

function buildPanels() {
  const root = $("panels"); root.innerHTML = "";
  for (const sec of S.schema.sections) {
    const d = document.createElement("details"); d.className = "panel"; d.open = !!sec.open; d.id = "panel-" + sec.id;
    d.innerHTML = `<summary>${sec.title}</summary><div class="panel-body"></div>`;
    const body = d.querySelector(".panel-body");
    for (const f of sec.fields) {
      const row = document.createElement("div"); row.className = "field"; row.dataset.key = `${sec.id}.${f.key}`;
      const id = `f_${sec.id}_${f.key}`;
      let input;
      if (f.type === "select" || f.type === "bool" || f.type === "preset") {
        input = document.createElement("select");
        const opts = f.type === "preset" ? ["Custom"].concat((S.materials[f.preset] || []).map((m) => m.name)) : f.options;
        opts.forEach((o, i) => { const op = document.createElement("option"); op.value = String(o); op.textContent = f.labels ? f.labels[i] : String(o); input.appendChild(op); });
        input.value = String(f.default);
      } else if (f.type === "file") {
        input = document.createElement("div"); input.className = "file-row";
        input.innerHTML = `<button class="btn" type="button">Choose&hellip;</button><span>no file</span>`;
        input.querySelector("button").onclick = () => pickFile(f.accept, async (file) => {
          await putFile(file); setFileValue(sec.id, f.key, file.name); changed(sec.id, f.key);
        });
        input.dataset.value = "";
      } else {
        input = document.createElement("input");
        input.type = f.type === "text" ? "text" : "text"; input.inputMode = f.type === "text" ? "text" : "decimal";
        input.value = String(f.default); input.autocomplete = "off";
      }
      input.id = id;
      const label = document.createElement("label"); label.htmlFor = id; label.textContent = f.label;
      row.append(label, input); body.appendChild(row);
      W[`${sec.id}.${f.key}`] = { sec, f, input, row, label };
      const ev = input.tagName === "SELECT" ? "change" : "input";
      if (f.type !== "file") input.addEventListener(ev, () => changed(sec.id, f.key));
    }
    root.appendChild(d);
  }
  refreshPanels();
}

function setFileValue(sec, key, name) {
  const w = W[`${sec}.${key}`]; w.input.dataset.value = name || "";
  w.input.querySelector("span").textContent = name || "no file";
}

function readField(w) {
  const { f, input } = w;
  if (f.type === "file") return input.dataset.value || "";
  if (f.type === "bool") return input.value === "true";
  if (f.type === "select" || f.type === "preset" || f.type === "text") return input.value;
  const t = input.value.trim(), v = f.type === "int" ? Number(t) : Number(t);
  if (t === "" || !Number.isFinite(v) || (f.type === "int" && !Number.isInteger(v))) return NaN;
  return v;
}

function values(strict = false) {
  const out = {};
  for (const sec of S.schema.sections) out[sec.id] = {};
  for (const w of Object.values(W)) {
    if (w.f.type === "preset") continue;
    out[w.sec.id][w.f.key] = readField(w);
  }
  if (strict) {
    const bad = [];
    for (const w of Object.values(W)) {
      const v = out[w.sec.id] && out[w.sec.id][w.f.key];
      const visible = fieldVisible(w.sec, w.f, out);
      w.input.classList && w.input.classList.toggle("bad", typeof v === "number" && Number.isNaN(v) && visible);
      if (typeof v === "number" && Number.isNaN(v) && visible) bad.push(`${w.sec.title}: ${w.f.label}`);
    }
    if (bad.length) throw new Error("Not a number: " + bad.join("; "));
    // hidden fields that are not numbers are left out (as the desktop weld panel does)
    for (const sec of Object.keys(out)) for (const k of Object.keys(out[sec])) if (typeof out[sec][k] === "number" && Number.isNaN(out[sec][k])) delete out[sec][k];
  }
  return out;
}

// Refuse values the panels cannot show (an unknown option), before anything is changed.
function checkValues(secId, vals) {
  for (const [k, v] of Object.entries(vals || {})) {
    const w = W[`${secId}.${k}`]; if (!w || !(w.f.type === "select" || w.f.type === "bool")) continue;
    const s = String(w.f.type === "select" && k === "element_order" ? String(v).toLowerCase() : v);
    if (![...w.input.options].some((o) => o.value === s)) throw new Error(`${w.sec.title}: '${v}' is not an option for ${w.f.label}`);
  }
}
function setValues(secId, vals) {
  checkValues(secId, vals);
  for (const [k, v] of Object.entries(vals || {})) {
    const w = W[`${secId}.${k}`]; if (!w) continue;
    if (w.f.type === "file") { setFileValue(secId, k, v); continue; }
    if (w.f.type === "select" || w.f.type === "bool") {
      const s = String(w.f.type === "select" && k === "element_order" ? String(v).toLowerCase() : v);
      if (![...w.input.options].some((o) => o.value === s)) throw new Error(`${w.sec.title}: '${v}' is not an option for ${w.f.label}`);
      w.input.value = s;
    } else w.input.value = String(v);
  }
  refreshPanels();
}

function refreshPanels() {
  const vals = values();
  for (const w of Object.values(W)) w.row.hidden = !fieldVisible(w.sec, w.f, vals);
  const pv = W["scan.param_val"]; pv.label.textContent = pv.f.labels[vals.scan.focus_mode] || pv.f.label;
  // a fixed Y over-constrains the sound-path focus: not offered there (as the desktop panel)
  const ym = W["scan.y_focus_mode"].input, sp = vals.scan.focus_mode === "Constant Sound Path";
  [...ym.options].forEach((o) => { o.disabled = sp && o.value === "Fixed Y"; });
  if (sp && ym.value === "Fixed Y") ym.value = "Derived from Skew";
}

function changed(sec, key) {
  S.edits++;
  if (key === "_material") {                         // a preset fills the speeds
    const w = W[`${sec}._material`], list = S.materials[w.f.preset] || [], m = list.find((x) => x.name === w.input.value);
    if (m) { if (sec === "wedge") W["wedge.velocity_ms"].input.value = m.vl;
             else { W["material.vel_long_ms"].input.value = m.vl; W["material.vel_shear_ms"].input.value = m.vs; } }
  }
  refreshPanels();
  if (sec === "beam_field") { markFieldStale("the field settings changed"); return; }
  if (S.calc) {
    S.dirty = true; $("fieldBtn").disabled = true; markFieldStale("the setup changed");
    status("The inputs changed: press “Calculate laws” to update.");
  }
}

// ---- configuration (the desktop window's file format) ----------------------------------------
const FIELD_DEFAULTS = () => Object.fromEntries(S.schema.sections.find((s) => s.id === "beam_field").fields.map((f) => [f.key, f.default]));
async function configDict() {
  const v = values(true);
  const config = { probe: v.probe, wedge: v.wedge, material: v.material, scan: v.scan, sub_aperture: v.sub_aperture };
  if (v.weld.type !== "None") config.weld = v.weld;                 // saved only when there is a weld
  const fd = FIELD_DEFAULTS();
  if (Object.keys(fd).some((k) => fd[k] !== v.beam_field[k])) config.beam_field = v.beam_field;
  if (S.ready) { const refs = await call("catalog_status", { probe: v.probe, wedge: v.wedge }); if (Object.keys(refs).length) config.catalog = refs; }
  return config;
}
// Loading a configuration changes inputs: it waits for (and is refused during) a request, and
// counts as an edit, so a calculation finishing later cannot present its laws as current.
async function applyConfig(config) {
  if (!(await exclusive(() => applyConfigNow(config)))) throw new Error("Wait for the calculation to finish, then open the file again.");
}
async function applyConfigNow(config) {
  // the whole file is checked first: a file that cannot load changes nothing
  const plan = [];
  for (const sec of ["probe", "wedge", "material", "scan", "sub_aperture"]) if (config[sec]) plan.push([sec, config[sec]]);
  plan.push(["weld", config.weld || { type: "None" }], ["beam_field", config.beam_field || FIELD_DEFAULTS()]);
  for (const [sec, vals] of plan) checkValues(sec, vals);
  S.edits++;
  if (S.calc) { S.dirty = true; $("fieldBtn").disabled = true; markFieldStale("a configuration was loaded"); }
  for (const [sec, vals] of plan) setValues(sec, vals);
  for (const k of ["wedge._material", "material._material"]) W[k].input.value = "Custom";
  refreshPanels();
  // its catalogue references: given to Python now, or once it is ready (a file opened while it starts)
  if (S.ready) await call("config_loaded", { config }); else S.pendingConfig = config;
}

// ---- calculation and laws -------------------------------------------------------------------
async function calculate() {
  if (S.busy) return;
  let cfg;
  try { cfg = Object.assign(values(true), { view: { coverage_legs: Number($("coverage").value) } }); }
  catch (e) { status(e.message, true); toast(e.message, true); return; }
  if (cfg.weld.type === "None") delete cfg.weld;
  busy(true, "Calculating…");
  const edits = S.edits;
  try {
    const t0 = performance.now();
    const r = await call("calc", cfg);
    S.calc = r; S.dirty = S.edits !== edits; S.custom = false; S.pick = null; S.pickInfo = null; S.all = null; S.revision++;
    if (S.play && r.laws.length < 2) togglePlay();     // nothing to play: stop (the button is disabled below two laws)
    $("elementInfo").textContent = ELEMENT_HINT; $("info3d").textContent = HINT_3D;   // the old selection is gone
    markFieldStale("the laws were recalculated");
    drawTable(); setupNav();
    const notes = [r.notes.coverage, r.notes.weld, r.notes.weld_error ? "Weld not drawn: " + r.notes.weld_error : ""].filter(Boolean);
    $("notes").textContent = notes.join("\n");
    if (r.notes.weld_error) toast("The weld is not drawn: " + r.notes.weld_error, true);
    if (!r.laws.length) {
      status("No valid laws: check the geometry, angles and targets (the table lists the reasons).", true);
      clearViews();
    } else {
      status(`${r.laws.length} laws in ${((performance.now() - t0) / 1000).toFixed(2)} s.`);
      await loadLaw(0);
      if ($("showAll").checked) { S.all = (await call("all_laws")).prims; drawLawViews(); }
    }
    if (window.matchMedia("(max-width: 900px)").matches) closeSetup();
  } catch (e) { status("Error: " + e.message, true); toast(e.message, true); }
  busy(false);
}

function clearViews() {
  S.law = null;
  Plotly.purge($("plotXZ")); Plotly.purge($("plotYZ")); Plotly.purge($("plotDelays")); Plotly.purge($("plot3d"));
  for (const k of ["xz", "plotXZ", "plotYZ", "delays", "3d"]) wired.delete(k);      // purge removed their listeners
  $("lawLabel").textContent = "No valid law in this scan";
}

let navAngles = [], navSkews = [];
function setupNav() {
  const laws = S.calc.laws;
  navAngles = [...new Set(laws.map((l) => l.angle))].sort((a, b) => a - b);
  navSkews = [...new Set(laws.map((l) => l.skew))].sort((a, b) => a - b);
  $("angleSlider").max = Math.max(0, navAngles.length - 1); $("skewSlider").max = Math.max(0, navSkews.length - 1);
  $("skewRow").hidden = !S.calc.probe.matrix || navSkews.length < 2;
  $("plotYZ").hidden = !(S.calc.probe.matrix || S.calc.probe.dual);
  $("rayPlots").classList.toggle("two", !$("plotYZ").hidden);
  // (the law bar is enabled when calculate() releases the lock)
}
function syncSliders(l) {
  const ai = navAngles.indexOf(l.angle), si = navSkews.indexOf(l.skew);
  if (ai >= 0) $("angleSlider").value = ai; if (si >= 0) $("skewSlider").value = si;
  $("angleLabel").textContent = `Angle ${l.angle.toFixed(1)}°`; $("skewLabel").textContent = `Skew ${(+l.skew).toFixed(1)}°`;
}

// One request to Python at a time. Every action that asks Python (calculate, a law, a moved
// focus, the beam field, an element, Show all, exports) runs under this lock; one that arrives
// while another runs is refused, and the page puts back what it showed.
async function exclusive(fn) {
  if (S.busy) return false;
  busy(true);
  try { await fn(); } finally { busy(false); }
  return true;
}
async function showLaw(i) {
  if (!(await exclusive(() => loadLaw(i))) && S.calc && S.calc.laws.length) syncSliders(S.calc.laws[S.lawIndex]);
}
async function loadLaw(i) {
  if (!S.calc || !S.calc.laws.length) return;
  i = Math.max(0, Math.min(S.calc.laws.length - 1, i));
  S.lawIndex = i; S.custom = false; S.focusRev++;
  S.law = await call("law", { law: i });
  syncSliders(S.calc.laws[i]);
  const f = S.law.focus;
  $("lawLabel").textContent = `Law ${i + 1}/${S.calc.laws.length}: ${S.calc.laws[i].angle.toFixed(1)}°` +
    (S.calc.probe.matrix ? `, skew ${(+S.calc.laws[i].skew).toFixed(1)}°` : "") + `, F = (${f[0].toFixed(1)}, ${f[1].toFixed(1)}, ${f[2].toFixed(1)}) mm`;
  for (const tr of $("lawTable").querySelectorAll("tbody tr")) tr.classList.toggle("sel", tr.dataset.law === String(i));
  if (S.field && (S.field.custom || S.field.law !== i)) markFieldStale(S.field.custom ? "it shows a dragged focus" : `it shows law ${S.field.law + 1}`);
  await refreshPick();
  drawLawViews();
}

async function showCustom(x, z) {
  if (!(await exclusive(() => loadCustom(x, z)))) drawLawViews();   // refused while Python works: handle put back
}
async function loadCustom(x, z) {
  S.focusRev++;
  try {
    const r = await call("custom", { x, z, from_law: S.lawIndex });
    S.law = r; S.custom = true;
    $("lawLabel").textContent = `Dragged focus (not in the sweep): F = (${r.focus[0].toFixed(1)}, ${r.focus[1].toFixed(1)}, ${r.focus[2].toFixed(1)}) mm`;
    markFieldStale("the focus was moved");
    status("Dragged focus: the table and CSV are unchanged; a slider or table row returns to the sweep.");
    await refreshPick();
  } catch (e) { toast("No law for that focus: " + e.message, true); }
  await drawLawViews();
  // the views widen to keep the moved focus and its rays in sight (as the desktop on release)
  if (S.custom && S.law) {
    drawingLaw = true;
    try {
      await V.ensureVisible($("plotXZ"), 0, S.law.prims);
      if (!$("plotYZ").hidden) await V.ensureVisible($("plotYZ"), 1, S.law.prims);
    } finally { drawingLaw = false; }
  }
}

function projectionData(dim) {
  return { setup: S.calc.setup, law: S.law ? S.law.prims : null, all: $("showAll").checked ? S.all : null, nLaws: S.calc.laws.length,
           frame: S.calc.frame, thickness: S.calc.thickness_mm, numbers: S.calc.probe.numbers, revision: S.revision,
           pick: S.pickInfo ? S.pickInfo.position : null, focus: S.law ? S.law.focus : null, focusEditable: dim === 0 && !$("showAll").checked };
}
let drawingLaw = false;
async function drawLawViews() {
  if (!S.calc) return;
  drawingLaw = true;
  try {
    await V.drawProjection($("plotXZ"), 0, projectionData(0));
    if (!$("plotYZ").hidden) await V.drawProjection($("plotYZ"), 1, projectionData(1));
    if (isActive("delays")) await V.drawDelays($("plotDelays"), S.calc.probe, S.law, S.calc.global_max_delay, S.pick);
    if (isActive("3d")) await draw3D();
  } finally { drawingLaw = false; ensureListeners(); }
}

// The 3D view (the desktop's 3D tab): drawn while its tab is shown; the beam field only while it is current.
function draw3D() {
  if (!S.calc || !S.calc.view3d || !S.law) return Promise.resolve();
  const field = $("field3d").checked && S.fieldFresh ? S.fieldSections : null;
  return V.drawScene3D($("plot3d"), { setup: S.calc.setup, law: S.law.prims, v3: S.calc.view3d, pick: S.pickInfo, focus: S.law.focus,
    field, section: $("section3d").checked, locus: $("locus3d").checked, numbers: S.calc.probe.numbers,
    camera: V.cameraFor(S.view3d), revision: S.camRev }).then(ensureListeners);
}
function setView3d(name) {
  S.view3d = name; S.camRev++;                      // a preset replaces the camera the user turned
  for (const b of $("views3d").querySelectorAll("button")) b.classList.toggle("primary", b.dataset.view === name);
  if (isActive("3d")) draw3D();
}

async function drawAll() {
  if (!S.calc || !S.calc.laws.length) return;
  if (!(await exclusive(async () => { S.all = (await call("all_laws")).prims; }))) { $("showAll").checked = false; return; }
  drawLawViews();
}

function stepLaw(d) {                              // wraps round, as the desktop's law navigation
  if (!S.calc || !S.calc.laws.length) return;
  const n = S.calc.laws.length;
  showLaw(((S.lawIndex + d) % n + n) % n);
}
function sliderLaw() {
  const a = navAngles[+$("angleSlider").value], s = navSkews[+$("skewSlider").value];
  const i = S.calc.laws.findIndex((l) => l.angle === a && (!S.calc.probe.matrix || l.skew === s));
  showLaw(i >= 0 ? i : S.calc.laws.findIndex((l) => l.angle === a));
}
function togglePlay() {
  if (S.play) { clearInterval(S.play); S.play = null; $("playBtn").innerHTML = "&#9655;"; return; }
  $("playBtn").innerHTML = "&#10074;&#10074;";
  S.play = setInterval(async () => {
    if (S.busy || drawingLaw) return;
    await showLaw((S.lawIndex + 1) % S.calc.laws.length);
  }, 180);
}

// ---- elements -------------------------------------------------------------------------------
const HINT_3D = "Drag to rotate, scroll or pinch to zoom; tap an element for its delay.";
const ELEMENT_HINT = "Tap an element (here or in Rays) for its number, delay and time of flight.";
function elementText(info) {
  const arr = info.array ? `${info.array} array, ` : "";
  return `Element ${info.number} (${arr}X ${info.x_index}, Y ${info.y_index}): ` +
    (info.active ? `delay ${info.delay_us.toFixed(4)} µs, time of flight ${info.tof_us.toFixed(3)} µs` : "inactive in this law");
}
// The selected element's readout follows the law shown (called inside the lock).
async function refreshPick() {
  if (S.pick === null || S.pick === undefined) return;
  S.pickInfo = await call("element", { index: S.pick, law: S.lawIndex });
  $("elementInfo").textContent = $("info3d").textContent = elementText(S.pickInfo);
}
async function pickElement(index) {
  if (!S.calc || index === null || index === undefined) return;
  let info;
  if (!(await exclusive(async () => { info = await call("element", { index, law: S.lawIndex }); }).catch((e) => { toast(e.message, true); return false; }))) return;
  try {
    S.pick = index; S.pickInfo = info;
    const arr = info.array ? `${info.array} array, ` : "";
    const txt = `Element ${info.number} (${arr}X ${info.x_index}, Y ${info.y_index}): ` +
      (info.active ? `delay ${info.delay_us.toFixed(4)} µs, time of flight ${info.tof_us.toFixed(3)} µs` : "inactive in this law");
    $("elementInfo").textContent = txt; $("info3d").textContent = txt; toast(txt, false, 3500);
    drawLawViews();
  } catch (e) { toast(e.message, true); }
}

// ---- table ----------------------------------------------------------------------------------
function drawTable() {
  const r = S.calc;
  $("lawTable").innerHTML = `<thead><tr>${r.headings.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>` +
    r.rows.map((row) => { const idx = row[row.length - 1]; const cells = row.slice(0, -1);
      return `<tr data-law="${idx === null ? "" : Number(idx)}" class="${idx === null ? "refused" : ""}">${cells.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`; }).join("") + "</tbody>";
  for (const tr of $("lawTable").querySelectorAll("tbody tr")) tr.onclick = () => { if (tr.dataset.law !== "") { showLaw(+tr.dataset.law); } };
}

// ---- beam field -----------------------------------------------------------------------------
function markFieldStale(why) {
  if (!S.field || !S.fieldFresh) return;
  S.fieldFresh = false;
  for (const id of ["plotField", "plotFieldYZ"]) $(id).style.opacity = 0.35;
  if (isActive("3d")) draw3D();                       // a stale field leaves the 3D view
  $("fieldStatus").textContent = `Stale (${why}): compute again for the law shown.`;
}
async function computeField() {
  if (S.busy) return;
  if (S.dirty) { toast("The inputs changed: press “Calculate laws” first.", true); return; }
  let v; try { v = values(true).beam_field; } catch (e) { toast(e.message, true); return; }
  const req = { law: S.lawIndex, custom: S.custom, values: v };
  busy(true); $("fieldStatus").textContent = "Computing the beam field…"; status("Computing the beam field…");
  const edits = S.edits, focusRev = S.focusRev;
  // Computed a step at a time (about 0.4 s each), so the page shows progress and Cancel stops it
  // between steps; Python in the browser cannot be interrupted inside a step.
  S.fieldCancel = false;
  const bar = $("fieldProgress"), cancel = $("fieldCancel");
  bar.value = 0; bar.hidden = false; cancel.hidden = false; cancel.disabled = false;
  try {
    let st = await call("field_start", req);
    while (!st.finished) {
      if (S.fieldCancel) throw Object.assign(new Error("cancelled"), { cancelled: true });
      st = await call("field_step", { seconds: 0.4 });
      bar.value = st.done / st.points;
      const pc = `Computing the beam field… ${Math.floor(100 * st.done / st.points)} %`;
      $("fieldStatus").textContent = `${pc} (${st.done} of ${st.points} points)`; status(pc);
    }
    const r = st.result;
    const xz = r.sections[0], yz = r.sections[1];
    $("plotFieldYZ").hidden = !yz; $("fieldPlots").classList.toggle("two", !!yz);
    await V.drawField($("plotField"), xz, r.focus, r.metrics, 0);
    if (yz) await V.drawField($("plotFieldYZ"), yz, r.focus, null, 1);
    for (const id of ["plotField", "plotFieldYZ"]) $(id).style.opacity = 1;
    S.field = { law: req.law, custom: req.custom }; S.fieldSections = r.sections;
    // current only if nothing changed while it was computed (inputs, the law, a moved focus)
    S.fieldFresh = S.edits === edits && S.focusRev === focusRev && !S.dirty;
    const kind = v.pulsed ? `pulsed, ${v.cycles} cycles` : "continuous wave";
    const which = req.custom ? "dragged focus" : `law ${req.law + 1} (${S.calc.laws[req.law].angle.toFixed(1)}°)`;
    $("fieldStatus").textContent = `${which}: ${v.model}, ${kind}, ${r.points} points, grid ${r.grid_mm.toFixed(2)} mm; ${r.seconds_field.toFixed(1)} s.`;
    const m = r.metrics ? `Beam axis ${r.metrics.angle_deg.toFixed(1)}° from vertical; −6 dB width at the focus depth ${r.metrics.width6_mm === null ? "–" : r.metrics.width6_mm.toFixed(1) + " mm"}.\n` : "";
    $("fieldNote").innerHTML = "";
    $("fieldNote").textContent = m + r.note;
    $("fieldNote").innerHTML = $("fieldNote").innerHTML.replace("docs/beam_field_model.html",
      '<a href="docs/beam_field_model.html" target="_blank" rel="noopener">the model note</a>');
    if (!S.fieldFresh) { S.fieldFresh = true; markFieldStale("something changed while it was computed"); }
    if (isActive("3d")) await draw3D();            // the 3D view was opened while the field computed
    status("Beam field done.");
  } catch (e) {
    if (e.cancelled) {
      const was = S.field ? (S.fieldFresh ? "the field shown is unchanged." : "the field shown is still out of date.") : "no field computed.";
      $("fieldStatus").textContent = "Cancelled: " + was; status("Beam field cancelled.");
    } else { $("fieldStatus").textContent = "No field: " + e.message; status("No field: " + e.message, true); }
  } finally { bar.hidden = true; cancel.hidden = true; }
  busy(false);
}

// ---- files ----------------------------------------------------------------------------------
function pickFile(accept, then) {
  const inp = $("fileInput"); inp.value = ""; inp.accept = accept || "";
  inp.onchange = () => { const f = inp.files[0]; if (f) then(f).catch((e) => toast(e.message, true)); };
  inp.click();
}
function b64(buf) { let s = ""; const u = new Uint8Array(buf); for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); }
async function putFile(file) { await call("put_file", { name: file.name, data: b64(await file.arrayBuffer()) }); }
function download(name, data, type) {
  const blob = data instanceof Blob ? data : new Blob([data], { type: type || "text/plain" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}
function fromB64(s) { const b = atob(s), u = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }

function modal(title, body) {
  $("modalTitle").textContent = title; $("modalBody").innerHTML = ""; $("modalBody").append(body); $("modal").hidden = false;
}
function closeModal() { $("modal").hidden = true; }

async function loadCatalogue(kind) {
  pickFile(".json", async (file) => { await putFile(file); await cataloguePicker(kind, file.name); });
}
async function cataloguePicker(kind, name) {
  {
    const r = await call("catalog_open", { kind, name });
    const box = document.createElement("div");
    box.innerHTML = `<input type="search" placeholder="Filter ${kind}s…"><div class="pick-list"></div>`;
    const list = box.querySelector(".pick-list"), search = box.querySelector("input");
    const render = () => {
      const q = search.value.toLowerCase(); list.innerHTML = "";
      for (const e of r.entries) {
        const text = `${e.id} ${e.maker} ${e.model} ${e.family}`.toLowerCase(); if (q && !text.includes(q)) continue;
        const row = document.createElement("div"); row.className = "pick-row" + (e.usable ? "" : " unusable");
        const b = document.createElement("b"), small = document.createElement("small");      // catalogue text: never HTML
        b.textContent = e.id;
        small.textContent = [e.maker, e.model, e.family].filter(Boolean).join(" · ") + (e.usable ? "" : " — " + e.reason);
        row.append(b, small);
        if (e.usable) row.onclick = async () => {
          closeModal();
          try {
            let a;
            const ok = await exclusive(async () => {
              a = await call("catalog_apply", { kind, id: e.id });
              setValues(kind, a.values);
              if (kind === "wedge") W["wedge._material"].input.value = "Custom";
              setValues("beam_field", a.field);
              changed(kind, "");                     // counts as an edit; marks laws and field out of date
            });
            if (!ok) { toast("Wait for the calculation to finish, then choose the entry again.", true); return; }
            modal(`Catalogue ${kind}: ${a.id}`, Object.assign(document.createElement("pre"), { textContent: a.message, style: "white-space:pre-wrap;margin:0" }));
          } catch (err) { toast(err.message, true); }
        };
        list.appendChild(row);
      }
    };
    search.oninput = render; render();
    modal(`Choose a ${kind} — ${r.format}, ${r.entries.length} entries`, box);
    setTimeout(() => search.focus(), 50);
  }
}

async function menu(act) {
  $("fileMenu").classList.remove("open");
  if (S.busy) { toast("Wait for the calculation to finish."); return; }
  try {
    if (act === "save-config") { download("pac_config.json", JSON.stringify(await configDict(), null, 2), "application/json"); }
    else if (act === "open-config") pickFile(".json", async (file) => { await applyConfig(JSON.parse(await file.text())); toast(`Loaded ${file.name}. Press “Calculate laws”.`); });
    else if (act === "cat-probe") await loadCatalogue("probe");
    else if (act === "cat-wedge") await loadCatalogue("wedge");
    else if (act === "export-csv") {
      if (!S.calc || !S.calc.laws.length) throw new Error("Calculate laws first.");
      const r = await call("laws_csv"); download(r.name, r.text, "text/csv");
    } else if (act === "export-coords") {
      const box = document.createElement("div"); box.style.display = "flex"; box.style.gap = "8px"; box.style.flexWrap = "wrap";
      for (const [fmt, label] of [["csv", "CSV"], ["m", "MATLAB script (.m)"], ["mat", "MATLAB MAT file"]]) {
        const b = document.createElement("button"); b.className = "btn"; b.textContent = label;
        b.onclick = async () => { closeModal(); try { const v = values(true);
          const r = await call("element_coords", { format: fmt, config: { probe: v.probe, wedge: v.wedge, material: v.material, sub_aperture: v.sub_aperture } });
          download(r.name, new Blob([fromB64(r.base64)])); } catch (e) { toast(e.message, true); } };
        box.appendChild(b);
      }
      modal("Export element coordinates", box);
    }
  } catch (e) { toast(e.message, true); }
}

// ---- tabs, setup drawer, events -------------------------------------------------------------
const isActive = (tab) => $("view-" + tab).classList.contains("active");
function showTab(tab) {
  for (const b of document.querySelectorAll(".tab")) b.classList.toggle("active", b.dataset.tab === tab);
  for (const v of document.querySelectorAll(".view")) v.classList.toggle("active", v.id === "view-" + tab);
  if (tab === "delays" && S.calc && S.law) V.drawDelays($("plotDelays"), S.calc.probe, S.law, S.calc.global_max_delay, S.pick).then(ensureListeners);
  if (tab === "3d") draw3D();
  // only the plots now shown (a hidden one, e.g. the Y-Z field after a 2D field, cannot be resized)
  for (const id of ["plotXZ", "plotYZ", "plotDelays", "plotField", "plotFieldYZ", "plot3d"]) {
    const d = $(id); if (d && d.data && d.offsetParent !== null) Plotly.Plots.resize(d).catch(() => {});
  }
}
function openSetup() { $("setup").classList.add("open"); }
function closeSetup() { $("setup").classList.remove("open"); }

// Plot listeners: attached once per plot, after its first draw (Plotly adds .on then).
const wired = new Set();
function ensureListeners() {
  const xz = $("plotXZ");
  if (xz.on && !wired.has("xz")) {
    wired.add("xz");
    xz.on("plotly_relayout", (ev) => {                 // the focus handle was dragged
      if (drawingLaw || !S.calc) return;
      const k = Object.keys(ev).find((key) => /^shapes\[\d+\]\.x0$/.test(key)); if (!k) return;
      const n = k.match(/\d+/)[0];
      const x = (ev[`shapes[${n}].x0`] + ev[`shapes[${n}].x1`]) / 2, z = (ev[`shapes[${n}].y0`] + ev[`shapes[${n}].y1`]) / 2;
      showCustom(x, z);
    });
  }
  for (const id of ["plotXZ", "plotYZ"]) {
    const d = $(id);
    if (d.on && !wired.has(id)) { wired.add(id); d.on("plotly_click", (ev) => {
      const p = ev.points && ev.points[0]; if (p && p.data && p.data.meta === "element" && p.customdata !== undefined) pickElement(p.customdata); }); }
  }
  const p3 = $("plot3d");
  if (p3.on && !wired.has("3d")) { wired.add("3d"); p3.on("plotly_click", (ev) => {
    const p = ev.points && ev.points[0]; if (!p || !p.data || p.data.meta !== "element") return;
    const i = p.data.customdata[p.pointNumber]; if (i !== undefined && i !== null) pickElement(i); }); }
  const dl = $("plotDelays");
  if (dl.on && !wired.has("delays")) { wired.add("delays"); dl.on("plotly_click", (ev) => {
    const p = ev.points && ev.points[0]; if (p && p.customdata !== undefined && p.customdata !== null) pickElement(p.customdata); }); }
}

function wirePlots() {
  // Place the focus by tapping (touch screens, where dragging a shape is awkward)
  const xz = $("plotXZ");
  xz.addEventListener("click", (e) => {
    if (!S.placing || !S.calc || S.busy) return;
    const d = V.plotToData(xz, e.clientX, e.clientY); if (!d) return;
    S.placing = false; $("placeBtn").classList.remove("primary"); showCustom(d[0], d[1]);
  }, true);
}

async function start() {
  const [schema, materials] = await Promise.all([fetch("panels.json").then((r) => r.json()), fetch("py/materials.json").then((r) => r.json())]);
  S.schema = schema; S.materials = materials;
  buildPanels();
  // the toolbar's "place focus" button (tap the plot to put the focus there)
  const place = document.createElement("button"); place.id = "placeBtn"; place.className = "btn"; place.textContent = "Place focus";
  place.title = "Then tap the X-Z plot where the focus should be";
  place.onclick = () => { if (!S.law) return; S.placing = !S.placing; place.classList.toggle("primary", S.placing); if (S.placing) toast("Tap the X-Z plot where the focus should be."); };
  $("view-rays").querySelector(".toolbar").prepend(place);
  for (const b of document.querySelectorAll(".tab")) b.onclick = () => showTab(b.dataset.tab);
  $("calcBtn").onclick = calculate; $("fieldBtn").onclick = computeField;
  $("fieldCancel").onclick = () => { S.fieldCancel = true; $("fieldCancel").disabled = true; $("fieldStatus").textContent = "Cancelling…"; };
  $("prevLaw").onclick = () => stepLaw(-1); $("nextLaw").onclick = () => stepLaw(1); $("playBtn").onclick = togglePlay;
  $("angleSlider").oninput = sliderLaw; $("skewSlider").oninput = sliderLaw;
  $("coverage").onchange = () => { if (S.calc) calculate(); };
  for (const b of $("views3d").querySelectorAll("button")) b.onclick = () => setView3d(b.dataset.view);
  $("views3d").querySelector('[data-view="Iso"]').classList.add("primary");
  for (const id of ["locus3d", "section3d", "field3d"]) $(id).onchange = () => { if (isActive("3d")) draw3D(); };
  $("showAll").onchange = async () => { if ($("showAll").checked) await drawAll(); else drawLawViews(); };
  $("setupToggle").onclick = openSetup; $("setupClose").onclick = closeSetup;
  $("fileBtn").onclick = (e) => { e.stopPropagation(); $("fileMenu").classList.toggle("open"); };
  document.addEventListener("click", () => $("fileMenu").classList.remove("open"));
  for (const b of $("fileMenu").querySelectorAll("button")) b.onclick = (e) => { e.stopPropagation(); menu(b.dataset.act); };
  $("modalClose").onclick = closeModal; $("modal").onclick = (e) => { if (e.target === $("modal")) closeModal(); };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  wirePlots();
  if (window.matchMedia("(max-width: 900px)").matches) openSetup();
  const t0 = performance.now();
  try {
    const r = await call("init");
    S.timings = [["Pyodide", r.timings.pyodide], ["numpy, scipy", r.timings.packages], ["modules", r.timings.modules],
                 ["ready", (performance.now() - t0) / 1e3]];
    if (S.pendingConfig) { await call("config_loaded", { config: S.pendingConfig }); S.pendingConfig = null; }
    S.ready = true; busy(false);
    status(`Ready (Python ${r.python}, ${S.timings[3][1].toFixed(0)} s). Inputs never leave this browser.`);
    if (window.PAC_BUILD) $("buildId").textContent = "Build " + window.PAC_BUILD;
  } catch (e) { S.error = e.message; status("Could not start Python: " + e.message, true); }
}
start();

// For automated checks (screenshots, timings): the page's own actions, nothing more.
window.__pacTest = { setValues, values, calculate, showTab, computeField, showLaw, showCustom, pickElement, configDict,
                     applyConfig, openSetup, closeSetup, menu,
                     putBytes: async (name, buf) => call("put_file", { name, data: b64(buf) }), setFileValue, cataloguePicker };
