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
import gc
from PySide6.QtWidgets import QWidget, QApplication, QLabel
from PySide6.QtCore import Qt, QRect, QEventLoop, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen, QCursor, QPixmap
from PIL import Image

from config import (
    SELECTION_OVERLAY_COLOR,
    SELECTION_MIN_WIDTH,
    SELECTION_MIN_HEIGHT,
)
from preferences import (
    get_selection_color,
    get_selection_border_width,
)


# ==========================================================
# BLOQUE: Inicialización y Configuración de la Ventana
# ==========================================================
class SelectionWindow(QWidget):
    """Ventana de selección de área con screenshot congelada."""

    def __init__(self, on_select_callback):
        self.on_select  = on_select_callback
        self._app       = QApplication.instance() or QApplication([])
        super().__init__()

        self.start_point = None
        self.end_point   = None
        self.selecting   = False
        self.screenshot  = None   # PIL Image — se libera en _cleanup_resources()
        self._pixmap     = None   # QPixmap fullscreen — se libera en _cleanup_resources()
        self._toast      = None
        self._toast_anim = None
        self._loop       = None


    # ==========================================================
    # BLOQUE: Limpieza de Recursos
    # ==========================================================
    def _cleanup_resources(self):
        """Libera la imagen PIL y el QPixmap fullscreen. Llamar siempre al cerrar."""
        # 🆕 Cerrar imagen PIL fullscreen
        if self.screenshot is not None:
            try:
                self.screenshot.close()
            except Exception:
                pass
            self.screenshot = None

        # 🆕 Liberar QPixmap fullscreen (el más pesado: ~8MB)
        if self._pixmap is not None:
            self._pixmap = None   # Qt libera el buffer interno cuando no quedan refs

        gc.collect()


    # ==========================================================
    # BLOQUE: Utilidades Visuales (Toast y Cursor)
    # ==========================================================
    def _show_toast(self, text, pos):
        label = QLabel(text, self)
        label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: white;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11pt;
            }
        """)
        label.adjustSize()
        x = pos.x() - label.width() // 2
        y = pos.y() - label.height() - 10
        label.move(x, y)
        label.show()
        self._toast = label

        anim = QPropertyAnimation(label, b"windowOpacity", self)
        anim.setDuration(800)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        self._toast_anim = anim

        def _cleanup():
            label.deleteLater()
            if self._toast is label:
                self._toast = None
            if self._toast_anim is anim:
                self._toast_anim = None

        anim.finished.connect(_cleanup)
        anim.start()

    def _create_glow_cursor(self):
        size   = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)

        center    = size // 2
        length    = 11
        cap_style = Qt.FlatCap

        glow_pen = QPen(QColor(255, 255, 255, 100), 4)
        glow_pen.setCapStyle(cap_style)
        painter.setPen(glow_pen)
        painter.drawLine(center - length - 1, center, center - 1, center)
        painter.drawLine(center + 1, center, center + length + 1, center)
        painter.drawLine(center, center - length - 1, center, center - 1)
        painter.drawLine(center, center + 1, center, center + length + 1)

        white_pen = QPen(QColor(255, 255, 255, 255), 3)
        white_pen.setCapStyle(cap_style)
        painter.setPen(white_pen)
        painter.drawLine(center - length, center, center - 1, center)
        painter.drawLine(center + 1, center, center + length, center)
        painter.drawLine(center, center - length, center, center - 1)
        painter.drawLine(center, center + 1, center, center + length)

        painter.setPen(QPen(QColor(0, 0, 0, 255), 1))
        painter.drawLine(center - length, center, center + length, center)
        painter.drawLine(center, center - length, center, center + length)

        painter.end()
        return QCursor(pixmap, center, center)


    # ==========================================================
    # BLOQUE: Lógica de Captura y Bucle de Pantalla
    # ==========================================================
    def show(self):
        print("[*] Capturando pantalla...")
        self._capture_screenshot()

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setCursor(self._create_glow_cursor())
        self.setMouseTracking(True)

        screen = self._app.primaryScreen()
        self.setGeometry(screen.geometry())

        super().show()
        self._force_foreground()

        print("[*] Listo para seleccionar")
        self._loop = QEventLoop()
        self._loop.exec()

    def _force_foreground(self):
        import ctypes
        try:
            hwnd    = int(self.winId())
            user32  = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            fg_hwnd  = user32.GetForegroundWindow()
            cur_tid  = kernel32.GetCurrentThreadId()
            fg_tid   = user32.GetWindowThreadProcessId(fg_hwnd, None)

            attached = False
            if fg_tid and fg_tid != cur_tid:
                user32.AttachThreadInput(fg_tid, cur_tid, True)
                attached = True

            user32.ShowWindow(hwnd, 9)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)

            if attached:
                user32.AttachThreadInput(fg_tid, cur_tid, False)

            self.grabMouse()
            self.activateWindow()
            self.raise_()
            self.setFocus()
        except Exception as e:
            print(f"[WARN force_foreground] {e}")
            self.activateWindow()
            self.raise_()
            self.setFocus()

    def _capture_screenshot(self):
        screen = QApplication.primaryScreen()

        # Capturar como QPixmap
        self._pixmap = screen.grabWindow(0)

        # Convertir a PIL para el crop posterior
        q_img  = self._pixmap.toImage().convertToFormat(
            QPixmap.toImage(self._pixmap).Format.Format_RGBA8888
        )
        width  = q_img.width()
        height = q_img.height()
        ptr    = q_img.bits()

        self.screenshot = Image.frombytes(
            "RGBA", (width, height), ptr, "raw", "RGBA"
        ).convert("RGB")

        # 🆕 Liberar QImage intermedio (ya no se necesita)
        del q_img
        gc.collect()

        print(f"[*] Screenshot capturado: {width}x{height}")

    def close(self):
        self.releaseMouse()
        if self._loop is not None and self._loop.isRunning():
            self._loop.quit()
        super().close()
        # 🆕 Destruir el widget Qt y liberar recursos PIL/QPixmap
        self.deleteLater()
        self._cleanup_resources()


    # ==========================================================
    # BLOQUE: Eventos de Mouse
    # ==========================================================
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point   = event.pos()
            self.selecting   = True
            self.update()
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.selecting:
            return

        self.selecting   = False
        self.end_point   = event.pos()
        sel              = QRect(self.start_point, self.end_point).normalized()

        x1, y1 = sel.left(), sel.top()
        x2, y2 = sel.right(), sel.bottom()

        if (x2 - x1) < SELECTION_MIN_WIDTH or (y2 - y1) < SELECTION_MIN_HEIGHT:
            print("[WARN] Selección muy pequeña")
            self._show_toast("El área es muy pequeña", self.end_point)
            self.start_point = None
            self.end_point   = None
            self.selecting   = False
            self.update()
            return

        new_x1 = max(0, x1 - 1)
        new_y1 = max(0, y1 - 1)
        new_x2 = x2 + 6
        new_y2 = y2 + 6

        # 🆕 Hacer el crop ANTES de limpiar recursos
        cropped = self.screenshot.crop((new_x1, new_y1, new_x2, new_y2))

        # 🆕 Cerrar e invocar callback — close() libera screenshot y _pixmap
        self.close()

        if self.on_select:
            self.on_select(new_x1, new_y1, new_x2, new_y2, cropped)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


    # ==========================================================
    # BLOQUE: Renderizado
    # ==========================================================
    def paintEvent(self, event):
        import colorsys
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        if self._pixmap is None:
            painter.end()
            return

        overlay_color = QColor(*SELECTION_OVERLAY_COLOR)
        painter.drawPixmap(0, 0, self._pixmap)

        if self.selecting and self.start_point and self.end_point:
            sel = QRect(self.start_point, self.end_point).normalized()
            W, H = self.width(), self.height()

            left, top     = sel.left(), sel.top()
            right, bottom = sel.right() + 1, sel.bottom() + 1

            painter.fillRect(QRect(0,     0,       W,         top),          overlay_color)
            painter.fillRect(QRect(0,     bottom,  W,         H - bottom),   overlay_color)
            painter.fillRect(QRect(0,     top,     left,      bottom - top), overlay_color)
            painter.fillRect(QRect(right, top,     W - right, bottom - top), overlay_color)

            raw_color = get_selection_color()
            width     = get_selection_border_width()
            inset     = max(1, int(width) // 2)
            border_rect = QRect(
                sel.left()   + inset,
                sel.top()    + inset,
                sel.width()  - inset * 2,
                sel.height() - inset * 2,
            )

            if raw_color == "rainbow":
                if not hasattr(self, '_hue'):
                    self._hue = 0.0
                self._hue = (self._hue + 2) % 360
                self._draw_rainbow_border(painter, border_rect, width, self._hue)
                self.update()
            else:
                pen = QPen(QColor(raw_color), width, Qt.SolidLine)
                pen.setCosmetic(False)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(border_rect)
        else:
            painter.fillRect(self.rect(), overlay_color)

        painter.end()

    def _draw_rainbow_border(self, painter, rect, width, hue_offset):
        """
        Dibuja el borde arcoíris sin construir una lista de segmentos.
        Itera directamente sobre los 4 lados para evitar allocar
        miles de tuplas en cada paintEvent.
        """
        import colorsys

        x0, y0 = rect.left(),  rect.top()
        x1, y1 = rect.right(), rect.bottom()
        perimeter = 2 * (rect.width() + rect.height())
        if perimeter == 0:
            return

        pen = QPen()
        pen.setWidth(width)
        pen.setCosmetic(False)
        painter.setBrush(Qt.NoBrush)

        # Índice acumulado para calcular el matiz sin lista previa
        idx = 0

        def _set_color(i):
            hue    = (hue_offset + (i / perimeter) * 360) % 360
            r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)
            pen.setColor(QColor(int(r * 255), int(g * 255), int(b * 255)))
            painter.setPen(pen)

        # Top: izquierda → derecha
        for x in range(x0, x1):
            _set_color(idx); painter.drawLine(x, y0, x + 1, y0); idx += 1
        # Right: arriba → abajo
        for y in range(y0, y1):
            _set_color(idx); painter.drawLine(x1, y, x1, y + 1); idx += 1
        # Bottom: derecha → izquierda
        for x in range(x1, x0, -1):
            _set_color(idx); painter.drawLine(x, y1, x - 1, y1); idx += 1
        # Left: abajo → arriba
        for y in range(y1, y0, -1):
            _set_color(idx); painter.drawLine(x0, y, x0, y - 1); idx += 1