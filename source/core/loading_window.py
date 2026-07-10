# OCR Translator
# Copyright (C) 2026 ZProjects
#
# This file is part of OCR Translator.
# OCR Translator is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OCR Translator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OCR Translator. If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QProgressBar, QApplication, QHBoxLayout, QPushButton, QStyle
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRectF, QPointF, QCoreApplication
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QFont as QF, QPen, QWheelEvent, QMouseEvent, QImage, QFontMetrics
from PIL import Image, ImageFilter
import numpy as np
import gc


from preferences import get_result_font_family



# ==========================================================
# Widget de imagen con zoom y drag
# ==========================================================
class ZoomableImageLabel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._text_overlays: list | None = None
        self._zoom = 1.0
        self._zoom_min = 0.2
        self._zoom_max = 8.0
        self._offset = QPointF(0, 0)
        self._drag_active = False
        self._drag_last = QPointF()
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)


    def setSourcePixmap(self, pixmap: QPixmap, text_overlays: list | None = None):
        self._pixmap = pixmap
        self._text_overlays = text_overlays
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self.update()

    def resetView(self):
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self.update()

    def clearPixmaps(self):
        self._pixmap = None
        self._text_overlays = None
        self.update()


    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1a1a1a"))
        if self._pixmap and not self._pixmap.isNull():
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            painter.translate(self._offset)
            painter.scale(self._zoom, self._zoom)
            painter.drawPixmap(0, 0, self._pixmap)

            if self._text_overlays:
                for ov in self._text_overlays:
                    font = QF(ov['font_family'], ov['font_size'])
                    painter.setFont(font)
                    rect = QRectF(ov['x'], ov['y'], ov['w'], ov['h'])
                    painter.setPen(QPen(ov['color']))
                    painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft | Qt.TextDontClip, ov['text'])
        painter.end()


    def wheelEvent(self, event: QWheelEvent):
        if not self._pixmap:
            return
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else (1 / 1.15)
        new_zoom = max(self._zoom_min, min(self._zoom_max, self._zoom * factor))
        cursor_pos = QPointF(event.position())
        img_point = (cursor_pos - self._offset) / self._zoom
        self._zoom = new_zoom
        self._offset = cursor_pos - img_point * self._zoom
        self.update()


    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_active = True
            self._drag_last = QPointF(event.position())
            self.setCursor(Qt.ClosedHandCursor)


    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_active:
            delta = QPointF(event.position()) - self._drag_last
            self._offset += delta
            self._drag_last = QPointF(event.position())
            self.update()


    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_active = False
            self.setCursor(Qt.OpenHandCursor)



# ==========================================================
# Señales
# ==========================================================
class _Signals(QObject):
    update_status = Signal(str)
    show_result   = Signal(str)
    close_window  = Signal(int)


    def __init__(self, parent=None):
        super().__init__(parent)



# ==========================================================
# _ResultWidget — closeEvent vía subclase
# ==========================================================
class _ResultWidget(QWidget):
    def __init__(self, owner: "UnifiedResultWindow"):
        super().__init__()
        self._owner = owner


    def closeEvent(self, event):
        if self._owner is not None:
            self._owner._hard_destroy()
            self._owner = None
        event.accept()



# ==========================================================
# Ventana Unificada
# ==========================================================
class UnifiedResultWindow:

    def __init__(self, x1, y1, x2, y2, margin=0):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.margin = margin
        self.window: _ResultWidget | None = None
        self.is_closed = False
        self._image: Image.Image | None = None
        self._blocks = None
        self._signals: _Signals | None = None
        self._pixmap_before: QPixmap | None = None
        self._pixmap_after: QPixmap | None = None
        self._text_overlays: list | None = None
        self._showing_after = True
        self._zoom_label: ZoomableImageLabel | None = None
        self._toggle_btn: QPushButton | None = None
        self._reset_btn: QPushButton | None = None
        self._close_btn: QPushButton | None = None


    # ==========================================================
    # Destrucción determinista
    # ==========================================================
    def _hard_destroy(self):
        if self.is_closed:
            return
        self.is_closed = True

        if self._signals is not None:
            try:
                self._signals.update_status.disconnect()
                self._signals.show_result.disconnect()
                self._signals.close_window.disconnect()
            except Exception:
                pass
            self._signals = None

        if self._zoom_label is not None:
            try:
                self._zoom_label.clearPixmaps()
                self._zoom_label.deleteLater()
            except Exception:
                pass
            self._zoom_label = None

        self._pixmap_before = None
        self._pixmap_after = None
        self._text_overlays = None

        if self._image is not None:
            try:
                self._image.close()
            except Exception:
                pass
            self._image = None

        self._blocks = None

        if self._toggle_btn is not None:
            try:
                self._toggle_btn.clicked.disconnect()
            except Exception:
                pass
            self._toggle_btn = None

        if self._reset_btn is not None:
            try:
                self._reset_btn.clicked.disconnect()
            except Exception:
                pass
            self._reset_btn = None

        if self._close_btn is not None:
            try:
                self._close_btn.clicked.disconnect()
            except Exception:
                pass
            self._close_btn = None

        if hasattr(self, '_layout') and self._layout is not None:
            while self._layout.count():
                item = self._layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

        gc.collect()


    # ==========================================================
    # API Pública
    # ==========================================================
    def show_loading(self):
        self.width = min(max(self.x2 - self.x1, 320), 500)

        self.window = _ResultWidget(owner=self)
        self._signals = _Signals(self.window)
        self._signals.update_status.connect(self._do_update_status)
        self._signals.show_result.connect(self._do_show_result)
        self._signals.close_window.connect(self._delayed_close)
        self.window.setWindowTitle("OCR Translator")

        app_icon = QApplication.instance().windowIcon()
        if not app_icon.isNull():
            self.window.setWindowIcon(app_icon)

        self.window.setFixedSize(self.width, 180)
        self.window.move(self.x1, self.y1)
        self.window.setWindowFlags(Qt.Window)
        self.window.setAttribute(Qt.WA_DeleteOnClose, True)
        self.window.setAttribute(Qt.WA_QuitOnClose, False)
        self.window.setStyleSheet("background-color: #252525;")

        self._layout = QVBoxLayout(self.window)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(10)

        self._show_loading_content()
        return self.window


    def update_status(self, message):
        if self._signals and not self.is_closed:
            self._signals.update_status.emit(message)


    def show_result(self, translated_text, image=None, blocks=None):
        self._image = image
        self._blocks = blocks
        if self._signals and not self.is_closed:
            self._signals.show_result.emit(translated_text)


    def close_after(self, ms: int):
        if self._signals and not self.is_closed:
            self._signals.close_window.emit(ms)


    def _delayed_close(self, ms: int):
        QTimer.singleShot(ms, self.close)


    def close(self):
        if self.is_closed or not self.window:
            return
        try:
            self.window.close()
        except Exception:
            self._hard_destroy()


    def run(self):
        if self.window and not self.is_closed:
            self.window.show()


    # ==========================================================
    # Slots Qt
    # ==========================================================
    def _do_update_status(self, message):
        if self.is_closed or not hasattr(self, '_status_label'):
            return
        self._status_label.setText(message)


    def _do_show_result(self, translated_text):
        if self.is_closed or not self.window:
            return

        self.window.setVisible(False)

        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()

        self.window.setStyleSheet("background-color: #1e1e1e;")
        self._show_result_content(translated_text, self._image, self._blocks)
        self.window.setVisible(True)


    # ==========================================================
    # Handlers de botones (sin lambda closures)
    # ==========================================================
    def _on_reset_zoom(self):
        if self._zoom_label:
            self._zoom_label.resetView()


    def _on_close_clicked(self):
        self.close()


    # ==========================================================
    # Helpers de imagen
    # ==========================================================
    @staticmethod
    def _dominant_text_color_from_array(img_array: np.ndarray, bx1, by1, bx2, by2) -> QColor:
        img_h, img_w = img_array.shape[:2]
        x1 = max(0, min(bx1, bx2)); x2 = min(img_w, max(bx1, bx2))
        y1 = max(0, min(by1, by2)); y2 = min(img_h, max(by1, by2))
        if x2 <= x1 or y2 <= y1:
            return QColor(255, 255, 255)
        region = img_array[y1:y2, x1:x2]
        gray = np.mean(region, axis=2)
        median_brightness = np.median(gray)
        if median_brightness < 128:
            threshold = np.percentile(gray, 85)
            mask = gray >= threshold
        else:
            threshold = np.percentile(gray, 15)
            mask = gray <= threshold
        pixels = region[mask]
        if len(pixels) == 0:
            pixels = region.reshape(-1, 3)
        avg = np.mean(pixels, axis=0).astype(int)
        del region, gray, mask, pixels

        # --- Boost de saturación y brillo en HSV ---
        color = QColor(int(avg[0]), int(avg[1]), int(avg[2]))
        h, s, v, a = color.getHsv()
        if s < 40:
            if median_brightness < 128:
                v = min(255, int(v * 1.4) + 80)
                s = min(255, int(s * 2.0) + 30)
            else:
                v = max(0, int(v * 0.7) - 30)
                s = min(255, int(s * 2.0) + 30)
        else:
            s = min(255, int(s * 1.5) + 30)
            v = min(255, int(v * 1.2) + 25)
        color.setHsv(h, s, v, a)
        del avg
        return color


    @staticmethod
    def _pil_to_pixmap(image: Image.Image) -> QPixmap:
        rgba = image.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4,
                      QImage.Format_RGBA8888).copy()
        pixmap = QPixmap.fromImage(qimg)
        rgba.close()
        del data, qimg, rgba
        return pixmap


    @staticmethod
    def _build_original_pixmap(image: Image.Image, disp_w: int, disp_h: int) -> QPixmap:
        resized = image.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        px = UnifiedResultWindow._pil_to_pixmap(resized)
        resized.close()
        del resized
        return px


    def _build_blurred_background(self, image, blocks, disp_w, disp_h):
        img_w, img_h = image.size

        blurred = image.copy()
        for block in blocks:
            bx1, by1, bx2, by2 = block["box"]
            x1 = min(bx1, bx2); x2 = max(bx1, bx2)
            y1 = min(by1, by2); y2 = max(by1, by2)
            pad = 3
            cx1 = max(0, x1 - pad); cy1 = max(0, y1 - pad)
            cx2 = min(img_w, x2 + pad); cy2 = min(img_h, y2 + pad)
            if cx2 <= cx1 or cy2 <= cy1:
                continue
            region = image.crop((cx1, cy1, cx2, cy2))
            region = region.filter(ImageFilter.GaussianBlur(radius=6))
            blurred.paste(region, (cx1, cy1))
            region.close()
            del region

        blurred_resized = blurred.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        blurred.close()
        del blurred

        pixmap = self._pil_to_pixmap(blurred_resized)
        blurred_resized.close()
        del blurred_resized
        return pixmap


    def _build_text_overlays(self, image, blocks, translated_lines, scale_factor):
        rgb_image = image.convert("RGB")
        img_array = np.array(rgb_image)
        rgb_image.close()
        del rgb_image

        overlays = []
        line_idx = 0
        for block in blocks:
            if line_idx >= len(translated_lines):
                break
            bx1, by1, bx2, by2 = block["box"]
            rx1 = int(bx1 * scale_factor); ry1 = int(by1 * scale_factor)
            rx2 = int(bx2 * scale_factor); ry2 = int(by2 * scale_factor)

            text_color = self._dominant_text_color_from_array(img_array, bx1, by1, bx2, by2)
            box_w = rx2 - rx1; box_h = ry2 - ry1
            text = translated_lines[line_idx]
            line_idx += 1

            min_font_size = 7
            font_size = max(min_font_size, int(box_h * 0.8))
            font_family = get_result_font_family()
            font = QF(font_family, font_size)
            fm = QFontMetrics(font)
            while font_size > min_font_size and fm.horizontalAdvance(text) > box_w - 4:
                font_size -= 1
                font = QF(font_family, font_size)
                fm = QFontMetrics(font)

            if fm.horizontalAdvance(text) > box_w - 4:
                text = fm.elidedText(text, Qt.ElideRight, box_w - 4)

            overlays.append({
                'text': text,
                'x': rx1 + 2,
                'y': ry1,
                'w': box_w - 4,
                'h': box_h,
                'color': text_color,
                'font_family': font_family,
                'font_size': font_size,
            })

        del img_array
        return overlays


    # ==========================================================
    # Toggle antes/después
    # ==========================================================
    def _toggle_view(self):
        self._showing_after = not self._showing_after
        if self._showing_after:
            if self._zoom_label:
                self._zoom_label.setSourcePixmap(self._pixmap_after, self._text_overlays)
        else:
            if self._pixmap_before is None and self._image is not None:
                img_w, img_h = self._image.size
                max_w = 800
                if img_w > max_w:
                    scale = max_w / img_w
                    disp_w = max_w
                    disp_h = int(img_h * scale)
                else:
                    disp_w = img_w
                    disp_h = img_h
                self._pixmap_before = self._build_original_pixmap(self._image, disp_w, disp_h)
            if self._zoom_label:
                self._zoom_label.setSourcePixmap(self._pixmap_before)
            if self._toggle_btn:
                self._toggle_btn.setText(QCoreApplication.translate('Loading', 'View translation'))


    # ==========================================================
    # Renderizado de contenido
    # ==========================================================
    def _show_loading_content(self):
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setSpacing(12)

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        dot = QLabel("●")
        dot.setFont(QFont("Segoe UI", 10))
        dot.setStyleSheet("color: #0078d4;")
        dot.setFixedWidth(16)
        row_layout.addWidget(dot)

        self._status_label = QLabel(QCoreApplication.translate('Loading', 'Extracting text...'))
        self._status_label.setFont(QFont("Segoe UI", 11, QFont.Medium))
        self._status_label.setStyleSheet("color: #ffffff;")
        row_layout.addWidget(self._status_label)
        row_layout.addStretch()
        self._layout.addWidget(row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(3)
        self._progress.setStyleSheet("""
            QProgressBar { background-color: #333333; border: none; border-radius: 2px; }
            QProgressBar::chunk { background-color: #0078d4; border-radius: 2px; }
        """)
        self._layout.addWidget(self._progress)

        hint = QLabel(QCoreApplication.translate('Loading', 'This may take a few seconds'))
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet("color: #b0b0b0;")
        hint.setAlignment(Qt.AlignLeft)
        self._layout.addWidget(hint)


    def _show_result_content(self, translated_text, image=None, blocks=None):
        if image and blocks:
            img_w, img_h = image.size
            max_w = 800
            if img_w > max_w:
                scale = max_w / img_w
                disp_w = max_w
                disp_h = int(img_h * scale)
            else:
                disp_w = img_w
                disp_h = img_h

            app = QApplication.instance()
            fram_margin = 30
            if app:
                style = app.style()
                if style:
                    fram_margin = style.pixelMetric(QStyle.PM_TitleBarHeight)

            padding_x = 10
            padding_y = 10
            controls_h = 50
            total_w = disp_w + (padding_x * 2)
            total_h = disp_h + controls_h + fram_margin + padding_y

            self.window.setMinimumSize(0, 0)
            self.window.setMaximumSize(16777215, 16777215)
            self.window.resize(total_w, total_h)
            self._layout.setContentsMargins(padding_x, padding_y, padding_x, 0)
            self._layout.setSpacing(0)

            scale_factor = disp_w / img_w
            translated_lines = [l for l in translated_text.split('\n') if l.strip()]

            self._pixmap_after = self._build_blurred_background(
                image, blocks, disp_w, disp_h
            )
            self._text_overlays = self._build_text_overlays(
                image, blocks, translated_lines, scale_factor
            )

            self._zoom_label = ZoomableImageLabel()
            self._zoom_label.setFixedSize(disp_w, disp_h)
            self._zoom_label.setSourcePixmap(self._pixmap_after, self._text_overlays)
            self._showing_after = True

            img_layout = QHBoxLayout()
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.addWidget(self._zoom_label)
            img_layout.addStretch()
            self._layout.addLayout(img_layout)

        else:
            self.window.setMinimumSize(0, 0)
            self.window.setMaximumSize(16777215, 16777215)
            self.window.resize(400, 200)
            canvas_label = QLabel(translated_text)
            canvas_label.setStyleSheet("color: white; padding: 10px;")
            canvas_label.setFont(QFont(get_result_font_family(), 11))
            canvas_label.setWordWrap(True)
            self._layout.addWidget(canvas_label)

        btn_style_secondary = """
            QPushButton { background-color: #3a3a3a; color: #e0e0e0; border: 1px solid #555555; border-radius: 4px; padding: 0 12px; }
            QPushButton:hover   { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """
        btn_style_primary = """
            QPushButton { background-color: #0078d4; color: white; border: none; border-radius: 4px; padding: 0 16px; }
            QPushButton:hover   { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
        """

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 8, 10, 10)
        btn_bar.setSpacing(8)

        if image and blocks:
            self._toggle_btn = QPushButton(QCoreApplication.translate('Loading', 'View original'))
            self._toggle_btn.setToolTip(QCoreApplication.translate('Loading', 'Shows the original capture without translation'))
            self._toggle_btn.setFont(QFont("Segoe UI", 9))
            self._toggle_btn.setFixedHeight(32)
            self._toggle_btn.setStyleSheet(btn_style_secondary)
            self._toggle_btn.clicked.connect(self._toggle_view)
            btn_bar.addWidget(self._toggle_btn)

            self._reset_btn = QPushButton(QCoreApplication.translate('Loading', 'Reset zoom'))
            self._reset_btn.setFont(QFont("Segoe UI", 9))
            self._reset_btn.setFixedHeight(32)
            self._reset_btn.setToolTip(QCoreApplication.translate('Loading', 'Restores the original zoom and position'))
            self._reset_btn.setStyleSheet(btn_style_secondary)
            self._reset_btn.clicked.connect(self._on_reset_zoom)
            btn_bar.addWidget(self._reset_btn)

            hint = QLabel(QCoreApplication.translate('Loading', 'Scroll: zoom  •  Drag: move'))
            hint.setFont(QFont("Segoe UI", 8))
            hint.setStyleSheet("color: #888888;")
            btn_bar.addWidget(hint)

        btn_bar.addStretch()

        self._close_btn = QPushButton(QCoreApplication.translate('Loading', 'Close'))
        self._close_btn.setFont(QFont("Segoe UI", 9))
        self._close_btn.setFixedHeight(32)
        self._close_btn.setStyleSheet(btn_style_primary)
        self._close_btn.clicked.connect(self._on_close_clicked)
        btn_bar.addWidget(self._close_btn)

        self._layout.addLayout(btn_bar)
