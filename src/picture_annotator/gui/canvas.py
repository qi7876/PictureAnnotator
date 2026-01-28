from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)

GREEN = QColor(0, 255, 0)
ORANGE = QColor(255, 140, 0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


@dataclass(frozen=True, slots=True)
class BBox:
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def to_rectf(self) -> QRectF:
        return QRectF(self.xmin, self.ymin, self.xmax - self.xmin, self.ymax - self.ymin)


class CornerHandle(QGraphicsRectItem):
    def __init__(self, *, owner: BBoxItem, corner: str, size: float = 10.0) -> None:
        super().__init__(-size / 2.0, -size / 2.0, size, size)
        self.owner = owner
        self.corner = corner  # "tl" or "br"
        self._updating = False

        self.setBrush(ORANGE)
        pen = QPen(ORANGE)
        pen.setCosmetic(True)
        self.setPen(pen)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(10)
        self.setVisible(False)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        self.owner.setSelected(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        super().mouseReleaseEvent(event)
        self.owner.notify_edited()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: ANN401
        if self._updating:
            return super().itemChange(change, value)

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            new_pos: QPointF = value
            return self.owner.constrain_handle(self.corner, new_pos)

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.owner.on_handle_moved(self.corner)

        return super().itemChange(change, value)

    def set_center(self, pos: QPointF) -> None:
        self._updating = True
        try:
            self.setPos(pos)
        finally:
            self._updating = False


class BBoxItem(QGraphicsRectItem):
    def __init__(
        self,
        *,
        det: dict[str, Any],
        image_width: int,
        image_height: int,
        on_edited: Callable[[dict[str, Any]], None] | None = None,
        line_width: int = 2,
    ) -> None:
        super().__init__()
        self.det = det
        self.image_width = int(image_width)
        self.image_height = int(image_height)
        self.min_size = 1.0
        self._on_edited = on_edited

        self._pen_normal = QPen(GREEN)
        self._pen_normal.setCosmetic(True)
        self._pen_normal.setWidth(int(line_width))

        self._pen_selected = QPen(ORANGE)
        self._pen_selected.setCosmetic(True)
        self._pen_selected.setWidth(int(line_width))

        self.setPen(self._pen_normal)
        self.setBrush(Qt.BrushStyle.NoBrush)
        self.setZValue(5)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self.tl = CornerHandle(owner=self, corner="tl")
        self.br = CornerHandle(owner=self, corner="br")

        self.update_from_det()

    def update_from_det(self) -> None:
        bbox = self.det.get("bbox", [0, 0, 1, 1])
        xmin, ymin, xmax, ymax = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        self.setRect(QRectF(xmin, ymin, max(1.0, xmax - xmin), max(1.0, ymax - ymin)))
        self.tl.set_center(QPointF(xmin, ymin))
        self.br.set_center(QPointF(xmax, ymax))

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: ANN401
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = self.isSelected()
            self.setPen(self._pen_selected if selected else self._pen_normal)
            self.tl.setVisible(selected)
            self.br.setVisible(selected)
        return super().itemChange(change, value)

    def constrain_handle(self, corner: str, pos: QPointF) -> QPointF:
        tl = self.tl.pos()
        br = self.br.pos()
        w = float(self.image_width)
        h = float(self.image_height)

        if corner == "tl":
            x = _clamp(pos.x(), 0.0, br.x() - self.min_size)
            y = _clamp(pos.y(), 0.0, br.y() - self.min_size)
            return QPointF(x, y)
        x = _clamp(pos.x(), tl.x() + self.min_size, w)
        y = _clamp(pos.y(), tl.y() + self.min_size, h)
        return QPointF(x, y)

    def on_handle_moved(self, corner: str) -> None:
        _ = corner
        tl = self.tl.pos()
        br = self.br.pos()
        rect = QRectF(tl.x(), tl.y(), br.x() - tl.x(), br.y() - tl.y())
        self.setRect(rect)
        self.det["bbox"] = [rect.left(), rect.top(), rect.right(), rect.bottom()]

    def notify_edited(self) -> None:
        if self._on_edited is not None:
            self._on_edited(self.det)


class ImageCanvas(QGraphicsView):
    boxSelectionChanged = Signal(object)  # det dict | None
    boxEdited = Signal(object)  # det dict
    boxCreated = Signal(tuple)  # (xmin,ymin,xmax,ymax)

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item = self._scene.addPixmap(QPixmap())
        self._pixmap_item.setZValue(0)

        self._items: list[BBoxItem] = []
        self._det_to_item: dict[int, BBoxItem] = {}  # key: det["id"]

        self._image_width = 0
        self._image_height = 0

        self._add_mode = False
        self._rubber_start: QPointF | None = None
        self._rubber_item: QGraphicsRectItem | None = None

        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

    def set_add_mode(self, enabled: bool) -> None:
        self._add_mode = bool(enabled)
        if self._add_mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
            self._scene.clearSelection()
        else:
            self.unsetCursor()

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))
        self._image_width = int(pixmap.width())
        self._image_height = int(pixmap.height())
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_boxes(self, detections: list[dict[str, Any]]) -> None:
        for it in self._items:
            self._scene.removeItem(it)
            self._scene.removeItem(it.tl)
            self._scene.removeItem(it.br)
        self._items.clear()
        self._det_to_item.clear()

        for det in detections:
            det_id = det.get("id")
            if not isinstance(det_id, int):
                continue
            item = BBoxItem(
                det=det,
                image_width=self._image_width,
                image_height=self._image_height,
                on_edited=self.boxEdited.emit,
            )
            self._scene.addItem(item)
            self._scene.addItem(item.tl)
            self._scene.addItem(item.br)
            self._items.append(item)
            self._det_to_item[det_id] = item

    def select_detection(self, det: dict[str, Any] | None) -> None:
        self._scene.blockSignals(True)
        try:
            self._scene.clearSelection()
            if det is None:
                return
            det_id = det.get("id")
            if not isinstance(det_id, int):
                return
            item = self._det_to_item.get(det_id)
            if item is not None:
                item.setSelected(True)
                self.centerOn(item)
        finally:
            self._scene.blockSignals(False)
        self._on_scene_selection_changed()

    def _on_scene_selection_changed(self) -> None:
        selected_items = [it for it in self._scene.selectedItems() if isinstance(it, BBoxItem)]
        if not selected_items:
            self.boxSelectionChanged.emit(None)
            return
        self.boxSelectionChanged.emit(selected_items[0].det)

    def wheelEvent(self, event) -> None:  # noqa: ANN001
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if self._add_mode and event.button() == Qt.MouseButton.LeftButton:
            self._rubber_start = self.mapToScene(event.pos())
            if self._rubber_item is None:
                self._rubber_item = QGraphicsRectItem()
                pen = QPen(ORANGE)
                pen.setCosmetic(True)
                pen.setStyle(Qt.PenStyle.DashLine)
                self._rubber_item.setPen(pen)
                self._rubber_item.setBrush(Qt.BrushStyle.NoBrush)
                self._rubber_item.setZValue(20)
                self._scene.addItem(self._rubber_item)
            self._rubber_item.setRect(QRectF(self._rubber_start, self._rubber_start))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._add_mode and self._rubber_start is not None and self._rubber_item is not None:
            cur = self.mapToScene(event.pos())
            rect = QRectF(self._rubber_start, cur).normalized()
            rect = self._clamp_rect(rect)
            self._rubber_item.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if self._add_mode and event.button() == Qt.MouseButton.LeftButton:
            if self._rubber_item is not None:
                rect = self._rubber_item.rect()
                self._scene.removeItem(self._rubber_item)
                self._rubber_item = None
                self._rubber_start = None

                if rect.width() >= 1.0 and rect.height() >= 1.0:
                    self.boxCreated.emit((rect.left(), rect.top(), rect.right(), rect.bottom()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _clamp_rect(self, rect: QRectF) -> QRectF:
        w = float(self._image_width)
        h = float(self._image_height)
        left = _clamp(rect.left(), 0.0, max(w - 1.0, 0.0))
        top = _clamp(rect.top(), 0.0, max(h - 1.0, 0.0))
        right = _clamp(rect.right(), left + 1.0, w)
        bottom = _clamp(rect.bottom(), top + 1.0, h)
        return QRectF(QPointF(left, top), QPointF(right, bottom))
