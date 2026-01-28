from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from picture_annotator.gui.store import ImageEntry


class ImageListModel(QAbstractListModel):
    def __init__(self, images: list[ImageEntry]) -> None:
        super().__init__()
        self._images = images

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent and parent.isValid() else len(self._images)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: ANN401
        if not index.isValid():
            return None
        entry = self._images[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.relative_path
        if role == Qt.ItemDataRole.UserRole:
            return entry
        return None

    def entry_at(self, row: int) -> ImageEntry:
        return self._images[row]


class BoxListModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self._detections: list[dict[str, Any]] = []

    def set_detections(self, detections: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        # Copy the list so external mutations (e.g. store/session) don't desync the view/model.
        self._detections = list(detections)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent and parent.isValid() else len(self._detections)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:  # noqa: ANN401
        if not index.isValid():
            return None
        det = self._detections[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            det_id = det.get("id")
            return str(det_id) if isinstance(det_id, int) else "?"
        if role == Qt.ItemDataRole.UserRole:
            return det
        return None

    def detection_at(self, row: int) -> dict[str, Any]:
        return self._detections[row]

    def index_of(self, det: dict[str, Any]) -> int | None:
        try:
            return self._detections.index(det)
        except ValueError:
            return None

    def append_detection(self, det: dict[str, Any]) -> None:
        row = len(self._detections)
        self.beginInsertRows(QModelIndex(), row, row)
        self._detections.append(det)
        self.endInsertRows()

    def remove_detection(self, det: dict[str, Any]) -> None:
        row = self.index_of(det)
        if row is None:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._detections.pop(row)
        self.endRemoveRows()
