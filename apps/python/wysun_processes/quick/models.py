"""Keyed list models for Wysun Processes. Updates are applied as removals, moves and insertions so QML views can
animate rows sliding into their new place instead of being rebuilt every second."""
from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Qt, Signal, Slot, Property


class KeyedModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, roles, parent=None):
        super().__init__(parent)
        self._roles = list(roles)
        self._ids = {name: Qt.UserRole + 1 + i for i, name in enumerate(self._roles)}
        self._items = []

    def roleNames(self):
        return {value: QByteArray(name.encode()) for name, value in self._ids.items()}

    def roleFor(self, name):
        return self._ids[name]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        name = self._roles[role - Qt.UserRole - 1] if Qt.UserRole < role <= Qt.UserRole + len(self._roles) else None
        return self._items[index.row()].get(name) if name else None

    @Property(int, notify=countChanged)
    def count(self):
        return len(self._items)

    @Slot(int, result='QVariantMap')
    def get(self, row):
        return dict(self._items[row]) if 0 <= row < len(self._items) else {}

    @Slot(str, result=int)
    def indexOf(self, key):
        for i, item in enumerate(self._items):
            if item.get('key') == key:
                return i
        return -1

    def keys(self):
        return [item['key'] for item in self._items]

    def items(self):
        return self._items

    def replace(self, items):
        """Make the model hold `items` (dicts with a unique 'key'), moving rows that only changed place."""
        before = len(self._items)
        wanted = [item['key'] for item in items]
        keep = set(wanted)
        for row in range(len(self._items) - 1, -1, -1):
            if self._items[row]['key'] not in keep:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._items[row]
                self.endRemoveRows()
        for target, item in enumerate(items):
            key = item['key']
            if target < len(self._items) and self._items[target]['key'] == key:
                self._items[target] = item
                continue
            current = next((i for i in range(target, len(self._items)) if self._items[i]['key'] == key), -1)
            if current >= 0:
                self.beginMoveRows(QModelIndex(), current, current, QModelIndex(), target)
                del self._items[current]
                self._items.insert(target, item)
                self.endMoveRows()
            else:
                self.beginInsertRows(QModelIndex(), target, target)
                self._items.insert(target, item)
                self.endInsertRows()
        if self._items:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._items) - 1, 0))
        if len(self._items) != before:
            self.countChanged.emit()
