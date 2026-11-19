"""Qt picker for probe and wedge catalogue entries (see catalog.py); twin of catalog_dialog.py."""
from qtpy import QtCore, QtGui, QtWidgets

COLUMNS = ("Id", "Manufacturer", "Model", "Type", "Note")


class CatalogPicker(QtWidgets.QDialog):
    """
    A catalogue's entries with a filter box. Entries the calculator cannot use are hidden
    while 'Usable only' is ticked, and listed greyed with the reason otherwise. After exec(),
    .selected is the chosen id or None.
    """

    def __init__(self, parent, catalog, kind):
        super().__init__(parent)
        self.setWindowTitle(f"Choose a {kind} - {catalog.format}, {len(catalog.entries(kind))} entries")
        self.resize(950, 500)
        self.selected = None
        self.rows = catalog.summary(kind)

        lay = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Filter:"))
        self.filter = QtWidgets.QLineEdit()
        top.addWidget(self.filter, 1)
        self.usable_only = QtWidgets.QCheckBox("Usable only")
        self.usable_only.setChecked(True)
        top.addWidget(self.usable_only)
        lay.addLayout(top)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)

        buttons = QtWidgets.QDialogButtonBox()
        self.use_btn = buttons.addButton("Use entry", QtWidgets.QDialogButtonBox.AcceptRole)
        buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._ok)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self.filter.textChanged.connect(self._fill)
        self.usable_only.toggled.connect(self._fill)
        self.table.cellDoubleClicked.connect(lambda *_: self._ok())
        self._fill()
        self.filter.setFocus()

    def _fill(self, *_):
        text = self.filter.text().lower()
        self.table.setRowCount(0)
        grey = QtGui.QBrush(QtGui.QColor("#94a3b8"))
        for id_, maker, model, kind, usable, reason in self.rows:
            if self.usable_only.isChecked() and not usable:
                continue
            if text and text not in f"{id_} {maker} {model} {kind}".lower():
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, v in enumerate((id_, maker, model, kind, reason)):
                item = QtWidgets.QTableWidgetItem(str(v))
                item.setData(QtCore.Qt.UserRole, (id_, usable))
                if not usable:
                    item.setForeground(grey)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()

    def visible_ids(self):
        return [self.table.item(r, 0).text() for r in range(self.table.rowCount())]

    def choose(self, id_):
        """Select the row holding id_ (for tests and keyboard use)."""
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).text() == id_:
                self.table.selectRow(r)
                return True
        return False

    def _ok(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        id_, usable = self.table.item(rows[0].row(), 0).data(QtCore.Qt.UserRole)
        if not usable:
            return
        self.selected = id_
        self.accept()
