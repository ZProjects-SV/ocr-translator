# OCR Translator
# Copyright (C) 2026 ZProjects
#
# This file is part of OCR Translator.
# OCR Translator is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OCR Translator is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OCR Translator. If not, see <https://www.gnu.org/licenses/>.
import io
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QProgressBar, QApplication, QHBoxLayout, QPushButton, QSizePolicy, QStyle
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRect, QPoint, QPointF
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QFont as QF, QPen, QWheelEvent, QMouseEvent
from PIL import Image, ImageFilter
import numpy as np

from preferences import (
    get_result_font_family,
)

# ==========================================================
# BLOQUE: Widget de imagen con zoom y drag
# ==========================================================
class ZoomableImageLabel(QLabel):
    """
    QLabel extendido que soporta:
    - Zoom con rueda del ratón (centrado en el cursor)
    - Arrastre con clic izquierdo para desplazar la imagen
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_original: QPixmap | None = None
        self._zoom = 1.0
        self._zoom_min = 0.2
        self._zoom_max = 8.0
        self._offset = QPointF(0, 0)          # desplazamiento acumulado
        self._drag_active = False
        self._drag_last = QPointF()
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)

    # ── API pública ─────────────────────────────────────────
    def setSourcePixmap(self, pixmap: QPixmap):
        """Carga el pixmap base y resetea la vista."""
        self._pixmap_original = pixmap
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._redraw()

    def resetView(self):
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._redraw()

    # ── Eventos ──────────────────────────────────────────────
    def wheelEvent(self, event: QWheelEvent):
        if not self._pixmap_original:
            return
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else (1 / 1.15)
        new_zoom = max(self._zoom_min, min(self._zoom_max, self._zoom * factor))

        # Zoom centrado en la posición del cursor
        cursor_pos = QPointF(event.position())
        # Punto en el espacio de la imagen antes del zoom
        img_point = (cursor_pos - self._offset) / self._zoom
        self._zoom = new_zoom
        # Recalcular offset para que el mismo punto quede bajo el cursor
        self._offset = cursor_pos - img_point * self._zoom
        self._redraw()

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
            self._redraw()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_active = False
            self.setCursor(Qt.OpenHandCursor)

    # ── Renderizado ──────────────────────────────────────────
    def _redraw(self):
        if not self._pixmap_original:
            return
        w = self.width()
        h = self.height()
        canvas = QPixmap(w, h)
        canvas.fill(QColor("#1a1a1a"))

        scaled = self._pixmap_original.scaled(
            int(self._pixmap_original.width() * self._zoom),
            int(self._pixmap_original.height() * self._zoom),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        painter = QPainter(canvas)
        painter.drawPixmap(
            int(self._offset.x()),
            int(self._offset.y()),
            scaled,
        )
        painter.end()
        super().setPixmap(canvas)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw()


# ==========================================================
# BLOQUE: Señales y Clase Principal (Controlador)
# ==========================================================
class _Signals(QObject):
    """Señales para comunicación entre hilos"""
    update_status = Signal(str)
    show_result   = Signal(str)
    close_window  = Signal(int)


class UnifiedResultWindow:
    """Ventana unificada: muestra loading y luego resultado en la misma ventana"""

    def __init__(self, x1, y1, x2, y2, margin=0):
        self.x1        = x1
        self.y1        = y1
        self.x2        = x2
        self.y2        = y2
        self.margin    = margin
        self.window    = None
        self.is_closed = False
        self._image    = None
        self._blocks   = None
        self._signals  = _Signals()

        # Pixmaps para antes/después
        self._pixmap_before: QPixmap | None = None
        self._pixmap_after:  QPixmap | None = None
        self._showing_after  = True           # estado del toggle
        self._zoom_label: ZoomableImageLabel | None = None
        self._toggle_btn: QPushButton | None = None

        self._signals.update_status.connect(self._do_update_status)
        self._signals.show_result.connect(self._do_show_result)
        self._signals.close_window.connect(self._delayed_close)


# ==========================================================
# BLOQUE: API Pública
# ==========================================================
    def show_loading(self):
        self.width = min(max(self.x2 - self.x1, 320), 500)

        self.window = QWidget()
        self.window.setWindowTitle("OCR Translator")

        app_icon = QApplication.instance().windowIcon()
        if not app_icon.isNull():
            self.window.setWindowIcon(app_icon)

        self.window.setFixedSize(self.width, 180)
        self.window.move(self.x1, self.y1)
        self.window.setWindowFlags(Qt.Window)
        self.window.setAttribute(Qt.WA_DeleteOnClose, False)
        self.window.setAttribute(Qt.WA_QuitOnClose, False)
        self.window.setStyleSheet("background-color: #252525;")

        self._layout = QVBoxLayout(self.window)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(10)

        self._show_loading_content()
        self.window.closeEvent = self._on_close_event
        return self.window

    def update_status(self, message):
        self._signals.update_status.emit(message)

    def show_result(self, translated_text, image=None, blocks=None):
        self._image  = image
        self._blocks = blocks
        self._signals.show_result.emit(translated_text)

    def close_after(self, ms: int):
        self._signals.close_window.emit(ms)

    def _delayed_close(self, ms: int):
        QTimer.singleShot(ms, self.close)

    def close(self):
        if self.is_closed or not self.window:
            return
        self.is_closed = True
        try:
            self.window.close()
        except Exception:
            pass

    def run(self):
        if self.window and not self.is_closed:
            self.window.show()


# ==========================================================
# BLOQUE: Slots de Actualización (Hilo Principal Qt)
# ==========================================================
    def _do_update_status(self, message):
        if self.is_closed or not hasattr(self, '_status_label'):
            return
        self._status_label.setText(message)

    def _do_show_result(self, translated_text):
        if self.is_closed or not self.window:
            return

        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.window.setStyleSheet("background-color: #1e1e1e;")
        self._show_result_content(translated_text, self._image, self._blocks)


# ==========================================================
# BLOQUE: Renderizado de UI (Loading y Resultado Final)
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

        self._status_label = QLabel("Extrayendo texto...")
        self._status_label.setFont(QFont("Segoe UI", 11, QFont.Medium))
        self._status_label.setStyleSheet("color: #ffffff;")
        row_layout.addWidget(self._status_label)
        row_layout.addStretch()
        self._layout.addWidget(row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(3)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: #333333;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 2px;
            }
        """)
        self._layout.addWidget(self._progress)

        hint = QLabel("Esto puede tardar unos segundos")
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet("color: #b0b0b0;")
        hint.setAlignment(Qt.AlignLeft)
        self._layout.addWidget(hint)

    # ── Helpers de color ────────────────────────────────────
    @staticmethod
    def _dominant_text_color(image: Image.Image, bx1, by1, bx2, by2) -> QColor:
        """Color dominante del texto en una subregión, adaptativo al fondo."""
        img_w, img_h = image.size
        x1 = max(0, min(bx1, bx2))
        y1 = max(0, min(by1, by2))
        x2 = min(img_w, max(bx1, bx2))
        y2 = min(img_h, max(by1, by2))

        if x2 <= x1 or y2 <= y1:
            return QColor(255, 255, 255)

        region = np.array(image.crop((x1, y1, x2, y2)).convert("RGB"))
        gray = np.mean(region, axis=2)
        median_brightness = np.median(gray)

        if median_brightness < 128:
            # Fondo oscuro → texto brillante
            threshold = np.percentile(gray, 85)
            mask = gray >= threshold
        else:
            # Fondo claro → texto oscuro
            threshold = np.percentile(gray, 15)
            mask = gray <= threshold

        pixels = region[mask]
        if len(pixels) == 0:
            pixels = region.reshape(-1, 3)

        avg = np.mean(pixels, axis=0).astype(int)
        return QColor(int(avg[0]), int(avg[1]), int(avg[2]))

    # ── Construcción del pixmap traducido ───────────────────
    def _build_translated_pixmap(
        self,
        image: Image.Image,
        blocks: list,
        translated_lines: list[str],
        disp_w: int,
        disp_h: int,
        scale_factor: float,
    ) -> QPixmap:
        """Genera el pixmap con fondo difuminado y texto traducido superpuesto."""
        img_w, img_h = image.size

        # Difuminar fondo en todos los bloques
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

        blurred = blurred.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        blurred.save(buf, format='PNG')
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())

        painter = QPainter(pixmap)
        line_idx = 0

        for block in blocks:
            if line_idx >= len(translated_lines):
                break

            bx1, by1, bx2, by2 = block["box"]
            rx1 = int(bx1 * scale_factor)
            ry1 = int(by1 * scale_factor)
            rx2 = int(bx2 * scale_factor)
            ry2 = int(by2 * scale_factor)

            text_color = self._dominant_text_color(image, bx1, by1, bx2, by2)

            box_w = rx2 - rx1
            box_h = ry2 - ry1
            text = translated_lines[line_idx]
            line_idx += 1

            font_size = max(8, int(box_h * 0.8))
            font = QF(get_result_font_family(), font_size)
            painter.setFont(font)
            fm = painter.fontMetrics()

            while font_size > 6 and fm.horizontalAdvance(text) > box_w - 4:
                font_size -= 1
                font = QF(get_result_font_family(), font_size)
                painter.setFont(font)
                fm = painter.fontMetrics()

            painter.setPen(QPen(text_color))
            painter.drawText(
                QRect(rx1 + 2, ry1, box_w - 4, box_h),
                Qt.AlignVCenter | Qt.AlignLeft,
                text,
            )

        painter.end()
        return pixmap

    # ── Construcción del pixmap "antes" (imagen original) ───
    @staticmethod
    def _build_original_pixmap(image: Image.Image, disp_w: int, disp_h: int) -> QPixmap:
        resized = image.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format='PNG')
        buf.seek(0)
        px = QPixmap()
        px.loadFromData(buf.read())
        return px

    # ── Toggle antes/después ─────────────────────────────────
    def _toggle_view(self):
        self._showing_after = not self._showing_after
        if self._showing_after:
            self._zoom_label.setSourcePixmap(self._pixmap_after)
            self._toggle_btn.setText("Ver original")
            self._toggle_btn.setToolTip("Muestra la captura sin traducción")
        else:
            self._zoom_label.setSourcePixmap(self._pixmap_before)
            self._toggle_btn.setText("Ver traducción")
            self._toggle_btn.setToolTip("Muestra el texto traducido superpuesto")

    # ── Resultado principal ──────────────────────────────────
    def _show_result_content(self, translated_text, image=None, blocks=None):
        if image and blocks:
            img_w, img_h = image.size

            # Escala de display
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

            # Altura extra: barra de controles (toggle + zoom hint + cerrar)
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

            # Construir ambos pixmaps
            self._pixmap_after  = self._build_translated_pixmap(
                image, blocks, translated_lines, disp_w, disp_h, scale_factor
            )
            self._pixmap_before = self._build_original_pixmap(image, disp_w, disp_h)

            # Widget zoomable
            self._zoom_label = ZoomableImageLabel()
            self._zoom_label.setFixedSize(disp_w, disp_h)
            self._zoom_label.setSourcePixmap(self._pixmap_after)   # empieza en traducción
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

        # ── Barra de controles inferior ──────────────────────
        btn_style_secondary = """
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 0 12px;
            }
            QPushButton:hover   { background-color: #4a4a4a; }
            QPushButton:pressed { background-color: #2a2a2a; }
        """
        btn_style_primary = """
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 16px;
            }
            QPushButton:hover   { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
        """

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 8, 10, 10)
        btn_bar.setSpacing(8)

        if image and blocks:
            # Botón antes/después
            self._toggle_btn = QPushButton("Ver original")
            self._toggle_btn.setToolTip("Muestra la captura sin traducción")
            self._toggle_btn.setFont(QFont("Segoe UI", 9))
            self._toggle_btn.setFixedHeight(32)
            self._toggle_btn.setStyleSheet(btn_style_secondary)
            self._toggle_btn.clicked.connect(self._toggle_view)
            btn_bar.addWidget(self._toggle_btn)

            # Botón resetear zoom
            btn_reset = QPushButton("Reset zoom")
            btn_reset.setFont(QFont("Segoe UI", 9))
            btn_reset.setFixedHeight(32)
            btn_reset.setToolTip("Restaura el zoom y posición originales")
            btn_reset.setStyleSheet(btn_style_secondary)
            btn_reset.clicked.connect(lambda: self._zoom_label.resetView())
            btn_bar.addWidget(btn_reset)

            # Hint scroll
            hint = QLabel("Scroll: zoom  •  Arrastrar: mover")
            hint.setFont(QFont("Segoe UI", 8))
            hint.setStyleSheet("color: #888888;")
            btn_bar.addWidget(hint)

        btn_bar.addStretch()

        btn_close = QPushButton("Cerrar")
        btn_close.setFont(QFont("Segoe UI", 9))
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet(btn_style_primary)
        btn_close.clicked.connect(self.close)
        btn_bar.addWidget(btn_close)

        self._layout.addLayout(btn_bar)

    def _on_close_event(self, event):
        self.is_closed = True
        event.accept()
