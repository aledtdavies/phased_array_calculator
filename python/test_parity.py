"""
Desktop and browser parity (docs/plans/PLAN-2026-11-web-desktop-parity.md).

The two front ends share the calculation and the geometry (python/); these tests catch the drift
that sharing cannot: a desktop control with no browser counterpart, a browser that leaves out a
module it needs, panels whose fields or defaults differ, or 3D camera presets that differ.
"""
import ast
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
WEB = os.path.join(ROOT, "web")
REGISTER = os.path.join(ROOT, "docs", "web_parity.json")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def desktop_sources():
    return {f: _read(os.path.join(HERE, f)) for f in sorted(os.listdir(HERE))
            if f.startswith("qt_") and f.endswith(".py")}


def desktop_controls():
    """{(kind, label)} of the desktop window's tabs, menu entries, buttons, check boxes and choices."""
    out = set()
    for name, s in desktop_sources().items():
        out |= {("tab", m) for m in re.findall(r'addTab\([^,]+,\s*"([^"]+)"', s)}
        out |= {("button", m) for m in re.findall(r'QPushButton\("([^"]+)"', s)}
        out |= {("check", m) for m in re.findall(r'QCheckBox\("([^"]+)"', s)}
        out |= {("choice", m) for m in re.findall(r'add_combo\("([^"]+)"', s)}
        # a combo box laid out with a label: ("Label:", self.combo)
        for attr in re.findall(r'self\.(\w+) = QtWidgets\.QComboBox\(\)', s):
            out |= {("choice", m.rstrip(":")) for m in re.findall(r'\("([^"]+)",\s*self\.%s\)' % attr, s)}
        if name == "qt_app.py":
            body = s.split("def _menu(self):")[1].split("\n    def ")[0]
            out |= {("menu", m) for m in re.findall(r'\("([^"]+)",\s*(?:self\.|lambda)', body)}
    return out


class TestRegister(unittest.TestCase):
    """Every desktop control is in docs/web_parity.json, with its browser counterpart or the reason
    it has none; and the register names only controls that still exist."""

    @classmethod
    def setUpClass(cls):
        cls.reg = json.loads(_read(REGISTER))
        cls.page = "\n".join(_read(os.path.join(WEB, f)) for f in
                             ("index.html", "app.js", "views.js", "view3d.js", "panels.json"))

    def test_every_desktop_control_is_registered(self):
        listed = {(c["kind"], c["desktop"].rstrip(":")) for c in self.reg["controls"]}
        missing = sorted(c for c in desktop_controls() if (c[0], c[1].rstrip(":")) not in listed)
        self.assertEqual(missing, [], "desktop controls with no entry in docs/web_parity.json: give each its "
                                      "browser counterpart (or a 'gap' saying why there is none)")

    def test_registered_controls_still_exist_on_the_desktop(self):
        src = "\n".join(desktop_sources().values())
        for c in self.reg["controls"]:
            self.assertIn('"' + c["desktop"].rstrip(":"), src, f"{c['desktop']}: not in the desktop window any more")

    def test_every_counterpart_is_on_the_page(self):
        for c in self.reg["controls"] + self.reg["interactions"]:
            if c["web"] is None:
                self.assertTrue(c.get("gap"), f"{c['desktop']}: no browser counterpart and no reason given")
            else:
                self.assertIn(c["web"], self.page, f"{c['desktop']}: the page has no {c['web']}")

    def test_no_open_gaps_but_the_listed_ones(self):
        gaps = sorted(c["desktop"] for c in self.reg["controls"] if c["web"] is None)
        self.assertEqual(gaps, ["Exit"], "a new gap: add it to the plan's gap list as well")


class TestSharedCode(unittest.TestCase):
    def test_the_browser_ships_every_module_it_imports(self):
        """pac_web's imports, followed through python/, are all in the worker's list (else the browser
        fails at run time where the desktop works)."""
        worker = _read(os.path.join(WEB, "worker.js"))
        shipped = set(re.findall(r'"(\w+)\.py"', worker.split("PY_FILES = [")[1].split("]")[0]))
        local = {f[:-3] for f in os.listdir(HERE) if f.endswith(".py")}
        seen, todo = set(), ["pac_web"]
        while todo:
            mod = todo.pop()
            if mod in seen:
                continue
            seen.add(mod)
            path = os.path.join(WEB if mod == "pac_web" else HERE, mod + ".py")
            for node in ast.walk(ast.parse(_read(path))):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    names = [node.module.split(".")[0]]
                todo += [n for n in names if n in local]
        self.assertEqual(sorted(seen - shipped), [], "modules pac_web needs that worker.js does not load")
        for gui in ("qt_app", "qt_panels", "scene_vtk", "visualisation", "main"):
            self.assertNotIn(gui, seen, f"the browser layer must not need the desktop GUI module {gui}")

    def test_camera_presets_are_the_desktops(self):
        vtk = _read(os.path.join(HERE, "scene_vtk.py"))
        desk = {k: (float(a), float(b)) for k, a, b in
                re.findall(r'"([\w-]+)":\s*\(([-\d.]+),\s*([-\d.]+)\)', vtk.split("VIEWS = {")[1].split("}")[0])}
        js = _read(os.path.join(WEB, "view3d.js"))
        web = {k: (float(a), float(b)) for k, a, b in
               re.findall(r'"?([\w-]+)"?:\s*\[([-\d.]+),\s*([-\d.]+)\]', js.split("const VIEWS3D = {")[1].split("}")[0])}
        self.assertEqual(web, desk)

    def test_3d_styles_are_the_desktops(self):
        """Solid colours and opacities, as scene_vtk draws them."""
        vtk = _read(os.path.join(HERE, "scene_vtk.py"))
        js = _read(os.path.join(WEB, "view3d.js"))
        self.assertIn('WELD_FACE, WELD_EDGE = "#fcd34d", "#92400e"', vtk)
        self.assertIn('weld: ["#fcd34d", 0.30', js)
        self.assertIn('color=WELD_FACE, opacity=0.30', vtk)
        self.assertIn("COLOR_MATERIAL, opacity=0.10", vtk)
        self.assertIn('component: ["#94a3b8", 0.10', js)
        self.assertIn("COLOR_WEDGE_FACE, opacity=0.15", vtk)
        self.assertIn('wedge: ["#22c55e", 0.15', js)


# The Qt panels (the desktop's own fields and defaults) against web/panels.json.
os.environ.setdefault("QT_API", "pyside6")
HEADLESS = sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
try:
    if HEADLESS:
        raise ImportError("no display")
    from qtpy import QtWidgets
    import qt_field
    import qt_panels
    HAVE_QT = True
except Exception:          # qtpy raises its own error when no binding is installed
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 not available")
class TestPanels(unittest.TestCase):
    def test_the_browser_panels_have_the_desktop_fields_and_defaults(self):
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])  # noqa: F841
        panels = json.loads(_read(os.path.join(WEB, "panels.json")))
        web = {s["id"]: {f["key"]: f["default"] for f in s["fields"] if not f["key"].startswith("_")}
               for s in panels["sections"]}
        desk = {"probe": qt_panels.ProbePanel(), "wedge": qt_panels.WedgePanel(), "material": qt_panels.MaterialPanel(),
                "scan": qt_panels.ScanPanel(), "sub_aperture": qt_panels.SubAperturePanel(),
                "weld": qt_panels.WeldPanel(), "beam_field": qt_field.FieldTab()}
        for sec, panel in desk.items():
            want = panel.get_values()
            got = web[sec]
            # every value the desktop panel saves is a browser field with the same default
            for k, v in want.items():
                self.assertIn(k, got, f"{sec}.{k}: on the desktop, not in the browser")
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    self.assertAlmostEqual(float(got[k]), float(v), msg=f"{sec}.{k}")
                else:
                    self.assertEqual(got[k], v, f"{sec}.{k}")
            extra = sorted(set(got) - set(want))
            self.assertEqual(extra, [], f"{sec}: browser fields the desktop does not save")


if __name__ == "__main__":
    unittest.main()
