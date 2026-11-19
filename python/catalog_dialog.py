"""Tk picker for probe and wedge catalogue entries (see catalog.py)."""
import tkinter as tk
from tkinter import ttk


class CatalogPicker(tk.Toplevel):
    """
    Modal list of a catalogue's entries with a filter box. Entries the
    calculator cannot use are listed greyed with the reason. After
    wait_window(), .selected is the chosen id or None.
    """

    def __init__(self, parent, catalog, kind):
        super().__init__(parent)
        self.title(f"Choose a {kind} - {catalog.format}, {len(catalog.entries(kind))} entries")
        self.geometry("900x480")
        self.transient(parent)
        self.selected = None
        self.rows = catalog.summary(kind)

        top = ttk.Frame(self, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.filter_var, width=40)
        ent.pack(side=tk.LEFT, padx=5)
        self.usable_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Usable only", variable=self.usable_only,
                        command=self._fill).pack(side=tk.LEFT, padx=10)
        self.filter_var.trace_add("write", lambda *a: self._fill())

        cols = ("id", "manufacturer", "model", "type", "note")
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=6)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, (240, 120, 200, 110, 300)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("unusable", foreground="#94a3b8")
        self.tree.bind("<Double-1>", lambda e: self._ok())

        btns = ttk.Frame(self, padding=6)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Use entry", command=self._ok).pack(side=tk.RIGHT, padx=3)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=3)

        self._fill()
        ent.focus_set()
        self.grab_set()

    def _fill(self):
        text = self.filter_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        for id_, maker, model, kind, usable, reason in self.rows:
            if self.usable_only.get() and not usable:
                continue
            if text and text not in f"{id_} {maker} {model} {kind}".lower():
                continue
            self.tree.insert("", "end", iid=id_, values=(id_, maker, model, kind, reason),
                             tags=() if usable else ("unusable",))

    def _ok(self):
        sel = self.tree.selection()
        if not sel:
            return
        if "unusable" in self.tree.item(sel[0], "tags"):
            return
        self.selected = sel[0]
        self.destroy()
