"""
The browser version, end to end in a real browser (headless Chromium through Playwright): the
page starts Python, calculates, and every tab draws, for a linear probe with a weld and coverage
and for a matrix probe. Fails on any page error. Saves screenshots (desktop and phone width).

    python tools/build_web.py site --offline
    python tools/web_smoke.py site out/web-smoke

Run in CI by .github/workflows/headless.yml (job 'web'); the screenshots are an artefact.
Plan: docs/plans/PLAN-2026-11-web-desktop-parity.md.
"""
from __future__ import annotations

import functools
import http.server
import os
import sys
import threading
import time

from playwright.sync_api import sync_playwright

TYPES = {".mjs": "text/javascript", ".js": "application/javascript", ".wasm": "application/wasm",
         ".json": "application/json", ".py": "text/plain", ".whl": "application/zip"}

LINEAR = """
const T = __pacTest;
T.setValues('probe', {probe_type: 'Linear', num_elements: 64, pitch_mm: 0.75, freq_mhz: 2.25});
T.setValues('wedge', {angle_deg: 36, height_mm: 5, velocity_ms: 2337, offset_mm: 4});
T.setValues('material', {vel_long_ms: 5900, vel_shear_ms: 3230, thickness_mm: 25});
T.setValues('sub_aperture', {start_element: 1, num_active_elements: 32});
T.setValues('scan', {wave_type: 'Shear', focus_mode: 'Constant Sound Path', param_val: 60, start_angle: 40, end_angle: 70, step_angle: 5});
T.setValues('weld', {type: 'Single-V', centre_x_mm: 60, bevel_deg: 30, root_gap_mm: 2, root_face_mm: 1.5});
document.getElementById('coverage').value = '1';
await T.calculate();
"""
MATRIX = """
const T = __pacTest;
T.setValues('weld', {type: 'None'});
document.getElementById('coverage').value = '0';
T.setValues('probe', {probe_type: 'Matrix', num_elements: 16, num_elements_y: 4, pitch_y_mm: 1.0});
T.setValues('scan', {focus_mode: 'Constant Depth', param_val: 20, start_angle: 40, end_angle: 60, step_angle: 10,
                     start_skew: -10, end_skew: 10, step_skew: 10});
await T.calculate();
"""
# A plot is drawn when Plotly has given it traces.
DRAWN = "(id) => { const d = document.getElementById(id); return !!(d && d.data && d.data.length); }"
# Everything the 3D view draws lies inside its axis ranges: the traces whose points fall outside
# (a moved focus or a field section clipped by the axes), as "name: axis".
OUTSIDE_3D = """() => {
  const gd = document.getElementById('plot3d'), sc = gd._fullLayout.scene, bad = [];
  const flat = (a) => (Array.isArray(a) ? a.flat(Infinity) : Array.from(a || [])).filter((v) => v !== null && isFinite(v));
  for (const t of gd.data) for (const k of ['x', 'y', 'z']) {
    const r = sc[k + 'axis'].range, lo = Math.min(r[0], r[1]) - 1e-6, hi = Math.max(r[0], r[1]) + 1e-6;
    if (flat(t[k]).some((v) => v < lo || v > hi)) bad.push((t.name || t.type) + ': ' + k);
  }
  return bad;
}"""


def serve(root):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def guess_type(self, path):
            return TYPES.get(os.path.splitext(path)[1], super().guess_type(path))

        def log_message(self, *a):
            pass
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main(site, out):
    os.makedirs(out, exist_ok=True)
    httpd = serve(site)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    errors, checks = [], []

    def check(name, ok, detail=""):
        checks.append((name, bool(ok)))
        print(("ok    " if ok else "FAIL  ") + name + (f": {detail}" if detail and not ok else ""), flush=True)

    with sync_playwright() as p:
        # SwiftShader: WebGL (the 3D view) without a GPU
        browser = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for label, size in (("desktop", {"width": 1366, "height": 860}), ("phone", {"width": 390, "height": 844})):
            page = browser.new_page(viewport=size, device_scale_factor=1)
            page.on("pageerror", lambda e, label=label: errors.append(f"{label}: {e}"))
            page.on("console", lambda m, label=label: errors.append(f"{label} console: {m.text}") if m.type == "error" else None)
            t0 = time.time()
            page.goto(url)
            page.wait_for_function("window.__pac && (window.__pac.ready || window.__pac.error)", timeout=300_000)
            err = page.evaluate("window.__pac.error")
            check(f"{label}: Python starts", not err, err)
            if err:
                page.close()
                continue
            print(f"      ready in {time.time() - t0:.0f} s", flush=True)
            shot = lambda name: page.screenshot(path=os.path.join(out, f"{label}_{name}.png"))  # noqa: E731

            def run(js, name):
                page.evaluate("async () => {" + js + "}")
                page.wait_for_function("!window.__pac.busy", timeout=600_000)
                page.wait_for_timeout(800)
                if name:
                    shot(name)

            run(LINEAR + ("T.closeSetup();" if label == "phone" else ""), "rays")
            n = page.evaluate("window.__pac.calc ? window.__pac.calc.laws.length : 0")
            check(f"{label}: linear laws", n == 7, f"{n} laws")
            check(f"{label}: X-Z view drawn", page.evaluate(DRAWN, "plotXZ"))
            check(f"{label}: weld note", "single-v" in page.inner_text("#notes").lower(), page.inner_text("#notes"))
            run("__pacTest.showTab('table');", "table")
            check(f"{label}: table rows", page.locator("#lawTable tbody tr").count() == 7)
            run("await __pacTest.pickElement(5); __pacTest.showTab('delays');", "delays")
            check(f"{label}: delays drawn", page.evaluate(DRAWN, "plotDelays"))
            check(f"{label}: element readout", "Element 6" in page.inner_text("#elementInfo"), page.inner_text("#elementInfo"))
            run("__pacTest.showTab('field'); await __pacTest.computeField();", "field")
            check(f"{label}: beam field drawn", page.evaluate(DRAWN, "plotField"), page.inner_text("#fieldStatus"))
            run("__pacTest.showTab('3d');", "3d")
            kinds = page.evaluate("(document.getElementById('plot3d').data || []).map((t) => t.type)")
            check(f"{label}: 3D view drawn with solids and the field", "mesh3d" in kinds and "surface" in kinds, kinds)
            check(f"{label}: 3D view has WebGL", page.locator("#plot3d canvas").count() > 0)
            run("document.getElementById('section3d').click(); document.querySelector('[data-view=\"X-Z\"]').click();", "3d_section")
            run("await __pacTest.showCustom(50, 15);", "3d_custom")
            check(f"{label}: dragged focus", page.evaluate("window.__pac.custom"))
            check(f"{label}: 3D view holds everything drawn", page.evaluate(OUTSIDE_3D) == [], page.evaluate(OUTSIDE_3D))
            run("await __pacTest.showCustom(200, 60);", "3d_far_focus")
            far = page.evaluate("window.__pac.custom && window.__pac.law.focus")
            check(f"{label}: far focus solved", bool(far) and abs(far[0] - 200) < 1e-6, far)
            check(f"{label}: 3D view widens to a far focus", page.evaluate(OUTSIDE_3D) == [], page.evaluate(OUTSIDE_3D))
            run("await __pacTest.showLaw(3); __pacTest.setValues('beam_field', {model: '3D', pulsed: false, grid_mm: 2, elevation_mm: 10});"
                "__pacTest.showTab('field'); await __pacTest.computeField(); __pacTest.showTab('3d');", "3d_field3d")
            surfaces = page.evaluate("document.getElementById('plot3d').data.filter((t) => t.type === 'surface').length")
            check(f"{label}: 3D field shows both sections", surfaces == 2, f"{surfaces} surfaces; {page.inner_text('#fieldStatus')}")
            check(f"{label}: 3D view holds both field sections", page.evaluate(OUTSIDE_3D) == [], page.evaluate(OUTSIDE_3D))
            # the 3D view opened while a field computes shows the field when it is done (review of #40)
            run("__pacTest.setValues('beam_field', {model: '2D', pulsed: false, grid_mm: 1}); await __pacTest.showLaw(2);"
                "const f = __pacTest.computeField(); __pacTest.showTab('3d'); await f;", "3d_field_while_open")
            surfaces = page.evaluate("document.getElementById('plot3d').data.filter((t) => t.type === 'surface').length")
            check(f"{label}: 3D view shows a field finished while it was open", surfaces == 1, f"{surfaces} surfaces")
            # a long field shows its progress, and Cancel stops it leaving the field shown as it was
            shown = page.evaluate("JSON.stringify(window.__pac.fieldSections)")
            page.evaluate("() => { __pacTest.setValues('beam_field', {model: '3D', pulsed: true, grid_mm: 0.2, elevation_mm: 10});"
                          " __pacTest.showTab('field'); window.__fieldRun = __pacTest.computeField(); }")
            page.wait_for_function("document.getElementById('fieldProgress').value > 0", timeout=300_000)
            check(f"{label}: field progress shown", page.is_visible("#fieldProgress") and page.is_visible("#fieldCancel"))
            shot("field_progress")
            page.click("#fieldCancel")
            page.wait_for_function("!window.__pac.busy", timeout=120_000)
            page.evaluate("async () => { await window.__fieldRun; }")
            status = page.inner_text("#fieldStatus")
            check(f"{label}: Cancel stops the field", status.startswith("Cancelled"), status)
            check(f"{label}: the field shown is kept", page.evaluate("JSON.stringify(window.__pac.fieldSections)") == shown)
            check(f"{label}: progress and Cancel hidden after", not page.is_visible("#fieldProgress")
                  and not page.is_visible("#fieldCancel"))
            shot("field_cancelled")
            # Cancel pressed while the last (here the only) step runs: the finished field is not shown
            shown = page.evaluate("JSON.stringify(window.__pac.fieldSections)")
            # (the page's worker is wrapped so Cancel is pressed as the step is sent: it lands mid-step)
            page.evaluate("""async () => {
              __pacTest.setValues('beam_field', {model: '2D', pulsed: false, grid_mm: 2});
              const post = worker.postMessage.bind(worker);
              worker.postMessage = (m) => { if (m.op === 'field_step') document.getElementById('fieldCancel').click(); post(m); };
              try { await __pacTest.computeField(); } finally { worker.postMessage = post; }
            }""")
            status = page.inner_text("#fieldStatus")
            check(f"{label}: Cancel during the last step", status.startswith("Cancelled")
                  and page.evaluate("JSON.stringify(window.__pac.fieldSections)") == shown, status)
            run("__pacTest.setValues('beam_field', {model: '2D', pulsed: true, grid_mm: 0.5});", None)
            run("__pacTest.showTab('rays'); await __pacTest.showLaw(2);", "rays_law3")
            cfg = page.evaluate("async () => JSON.stringify(await __pacTest.configDict())")
            check(f"{label}: configuration saves", '"probe"' in cfg and '"weld"' in cfg)
            run(MATRIX, "matrix_rays")
            info3d = page.inner_text("#info3d")
            check(f"{label}: a recalculation clears the 3D element readout", "delay" not in info3d or "tap an element" in info3d, info3d)
            n = page.evaluate("window.__pac.calc ? window.__pac.calc.laws.length : 0")
            check(f"{label}: matrix laws", n == 9, f"{n} laws")
            check(f"{label}: Y-Z view drawn", page.evaluate(DRAWN, "plotYZ"))
            run("__pacTest.showTab('3d'); document.querySelector('[data-view=\"Iso\"]').click();", "matrix_3d")
            check(f"{label}: matrix 3D drawn", page.evaluate(DRAWN, "plot3d"))
            page.close()
        browser.close()
    httpd.shutdown()
    for e in errors:
        print("page error:", e)
    failed = [n for n, ok in checks if not ok]
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed; {len(errors)} page errors; screenshots in {out}")
    return 1 if failed or errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "site", sys.argv[2] if len(sys.argv) > 2 else "web-smoke"))
