from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from picture_annotator.config import load_config
from picture_annotator.gui.canvas import ImageCanvas
from picture_annotator.gui.models import BoxListModel, ImageListModel
from picture_annotator.gui.store import AnnotationSession, AnnotationStore, ImageEntry


def _app_root() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.argv[0]).resolve().parent

    # Source/dev mode
    return Path(__file__).resolve().parents[3]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._root = _app_root()
        self._config_path = (self._root / "config" / "config.toml").resolve()

        if not self._config_path.exists():
            raise FileNotFoundError(f"未找到配置文件: {self._config_path}")

        self._config = load_config(self._config_path)
        self._store = AnnotationStore(app_root=self._root, config=self._config)

        self._images = self._store.list_images()
        self._images_model = ImageListModel(self._images)
        self._boxes_model = BoxListModel()

        self._current: AnnotationSession | None = None
        self._sync_selection = False
        self._switching_image = False

        self._build_ui()
        self._bind_signals()

        if self._images:
            self._select_image_row(0)
        self._update_title()

    def _build_ui(self) -> None:
        self.setWindowTitle("标注编辑器")
        self.resize(1400, 900)

        toolbar = QToolBar("工具栏")
        self.addToolBar(toolbar)

        self.act_prev = QAction("上一张", self)
        toolbar.addAction(self.act_prev)

        self.act_next = QAction("下一张", self)
        toolbar.addAction(self.act_next)

        toolbar.addSeparator()

        self.act_save = QAction("保存", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        toolbar.addAction(self.act_save)

        self.act_add = QAction("新增框(A)", self)
        self.act_add.setCheckable(True)
        self.act_add.setShortcut(QKeySequence(Qt.Key.Key_A))
        toolbar.addAction(self.act_add)

        self.act_delete = QAction("删除框(Del)", self)
        toolbar.addAction(self.act_delete)

        toolbar.addSeparator()

        self.act_fit = QAction("适配窗口", self)
        toolbar.addAction(self.act_fit)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Left: image list + search
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(QLabel("图片"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("搜索图片…")
        left_layout.addWidget(self.txt_search)
        self.view_images = QListView()
        self.view_images.setModel(self._images_model)
        self.view_images.setSelectionMode(QListView.SelectionMode.SingleSelection)
        left_layout.addWidget(self.view_images, 1)
        splitter.addWidget(left)

        # Center: canvas
        self.canvas = ImageCanvas()
        splitter.addWidget(self.canvas)

        # Right: boxes list
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.addWidget(QLabel("框（按 id 显示）"))
        self.view_boxes = QListView()
        self.view_boxes.setModel(self._boxes_model)
        self.view_boxes.setSelectionMode(QListView.SelectionMode.SingleSelection)
        right_layout.addWidget(self.view_boxes, 1)
        self.btn_delete = QPushButton("删除选中框")
        right_layout.addWidget(self.btn_delete)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 6)
        splitter.setStretchFactor(2, 1)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        self.statusBar().showMessage(f"图片数量：{len(self._images)}")

        # Letter shortcuts are attached to non-text widgets so they don't interfere with typing in the search box.
        self._install_letter_shortcuts()

    def _bind_signals(self) -> None:
        self.act_prev.triggered.connect(self._prev_image)
        self.act_next.triggered.connect(self._next_image)
        self.act_save.triggered.connect(self._save_current)
        self.act_fit.triggered.connect(self._fit_to_view)

        self.act_add.toggled.connect(self.canvas.set_add_mode)
        self.act_delete.triggered.connect(self._delete_selected_box)
        self.btn_delete.clicked.connect(self._delete_selected_box)

        self.canvas.boxSelectionChanged.connect(self._on_canvas_selection_changed)
        self.canvas.boxEdited.connect(self._on_box_edited)
        self.canvas.boxCreated.connect(self._on_box_created)

        self.view_images.selectionModel().currentChanged.connect(self._on_image_selected)
        self.view_boxes.selectionModel().currentChanged.connect(self._on_box_selected_in_list)

        self.txt_search.textChanged.connect(self._apply_image_filter)

    def _install_letter_shortcuts(self) -> None:
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        def add_shortcut(widget, key: Qt.Key, handler) -> None:  # noqa: ANN001
            sc = QShortcut(QKeySequence(key), widget)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(handler)

        for w in (self.canvas, self.view_images, self.view_boxes):
            add_shortcut(w, Qt.Key.Key_Q, self._prev_image)
            add_shortcut(w, Qt.Key.Key_E, self._next_image)
            add_shortcut(w, Qt.Key.Key_D, self._delete_selected_box)

    def _update_title(self) -> None:
        dirty = bool(self._current and self._current.dirty)
        suffix = " *" if dirty else ""
        self.setWindowTitle(f"标注编辑器{suffix}")

    def _apply_image_filter(self, text: str) -> None:
        t = text.strip().lower()
        if not t:
            self._images_model = ImageListModel(self._images)
        else:
            filtered = [e for e in self._images if t in e.relative_path.lower()]
            self._images_model = ImageListModel(filtered)
        self.view_images.setModel(self._images_model)
        self.view_images.selectionModel().currentChanged.connect(self._on_image_selected)

    def _on_image_selected(self, current, previous) -> None:  # noqa: ANN001
        if self._switching_image:
            return
        if not current.isValid():
            return

        prev_entry: ImageEntry | None = None
        if previous.isValid():
            prev_entry = previous.data(Qt.ItemDataRole.UserRole)

        next_entry: ImageEntry = current.data(Qt.ItemDataRole.UserRole)

        self._switching_image = True
        try:
            if self._current is not None:
                ok = self._save_current()
                if not ok:
                    if prev_entry is not None:
                        self._select_image_entry(prev_entry)
                    return

            self._load_image(next_entry)
        finally:
            self._switching_image = False

    def _load_image(self, entry: ImageEntry) -> None:
        session, report = self._store.load(entry)
        self._current = session

        pixmap = QPixmap(str(entry.image_path))
        if pixmap.isNull():
            QMessageBox.critical(self, "错误", f"无法打开图片：{entry.image_path}")
            return

        self.canvas.set_image(pixmap)
        self._boxes_model.set_detections(session.detections)
        self.canvas.set_boxes(session.detections)
        self.canvas.setFocus()

        if report.json_parse_failed:
            QMessageBox.warning(self, "提示", "标注 JSON 解析失败，已重置为空标注（保存时覆盖写回）。")
        if report.dropped_invalid:
            ids = ", ".join(str(x) for x in sorted(set(report.dropped_invalid))[:20])
            more = "…" if len(set(report.dropped_invalid)) > 20 else ""
            QMessageBox.warning(
                self,
                "提示",
                f"发现并丢弃了 {len(report.dropped_invalid)} 个无效框（示例 id：{ids}{more}）。",
            )
        if report.created_new_json:
            self.statusBar().showMessage("已创建空标注 JSON。")
        elif report.clamped_count:
            self.statusBar().showMessage(f"已自动裁剪 {report.clamped_count} 个越界框（保存时覆盖写回）。")
        else:
            self.statusBar().showMessage(entry.relative_path)

        self._update_title()

    def _save_current(self) -> bool:
        if self._current is None:
            return True
        try:
            self._store.save(self._current)
            self.statusBar().showMessage("已保存。")
            self._update_title()
            return True
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return False

    def _fit_to_view(self) -> None:
        self.canvas.fitInView(self.canvas.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _prev_image(self) -> None:
        row = self._current_image_row()
        if row is None:
            return
        self._select_image_row(max(0, row - 1))

    def _next_image(self) -> None:
        row = self._current_image_row()
        if row is None:
            return
        self._select_image_row(min(self._images_model.rowCount() - 1, row + 1))

    def _current_image_row(self) -> int | None:
        idx = self.view_images.currentIndex()
        return idx.row() if idx.isValid() else None

    def _select_image_row(self, row: int) -> None:
        idx = self._images_model.index(row, 0)
        self.view_images.setCurrentIndex(idx)

    def _select_image_entry(self, entry: ImageEntry) -> None:
        for row in range(self._images_model.rowCount()):
            if self._images_model.entry_at(row).image_path == entry.image_path:
                self._select_image_row(row)
                return

    def _on_box_selected_in_list(self, current, _previous) -> None:  # noqa: ANN001
        if self._sync_selection:
            return
        det = current.data(Qt.ItemDataRole.UserRole) if current.isValid() else None
        self._sync_selection = True
        try:
            self.canvas.select_detection(det)
        finally:
            self._sync_selection = False

    def _on_canvas_selection_changed(self, det: dict[str, Any] | None) -> None:
        if self._sync_selection:
            return
        self._sync_selection = True
        try:
            sel = self.view_boxes.selectionModel()
            sel.clearSelection()
            if det is None:
                return
            row = self._boxes_model.index_of(det)
            if row is None:
                return
            idx = self._boxes_model.index(row, 0)
            sel.setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        finally:
            self._sync_selection = False

    def _delete_selected_box(self) -> None:
        if self._current is None:
            return
        idx = self.view_boxes.currentIndex()
        if not idx.isValid():
            return
        det = idx.data(Qt.ItemDataRole.UserRole)
        if not isinstance(det, dict):
            return

        self._store.delete_box(self._current, det)
        self._boxes_model.remove_detection(det)
        self.canvas.set_boxes(self._current.detections)
        self._update_title()

    def _on_box_edited(self, det: dict[str, Any]) -> None:
        if self._current is None:
            return
        _ = det
        self._current.dirty = True
        self._update_title()

    def _on_box_created(self, bbox: tuple[float, float, float, float]) -> None:
        if self._current is None:
            return
        det = self._store.add_box(self._current, bbox)
        self._boxes_model.append_detection(det)
        self.canvas.set_boxes(self._current.detections)
        self.canvas.select_detection(det)
        self._update_title()

    def closeEvent(self, event) -> None:  # noqa: N802, ANN001
        if not self._save_current():
            event.ignore()
            return
        super().closeEvent(event)


def run() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
