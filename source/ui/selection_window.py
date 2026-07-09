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

import gc
from PySide6.QtWidgets import QWidget, QApplication, QLabel
from PySide6.QtCore import Qt, QRect, QEventLoop, QPropertyAnimation, QEasingCurve, QCoreApplication
from PySide6.QtGui import QPainter, QColor, QPen, QCursor, QPixmap, QPixmapCache
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
# BLOQUE: Ephemeral Engine -- unica interfaz publica
# ==========================================================
def capture_selection(on_select_callback):
    """
    Instancia SelectionWindow, ejecuta el ciclo, destruye el objeto
    y retorna. Al finalizar no quedan referencias al widget ni a sus
    recursos internos -- la proxima llamada empieza desde cero.

    Uso:
        capture_selection(lambda x1, y1, x2, y2, img: procesar(img))
    """
    app = QApplication.instance() or QApplication([])
    win = _SelectionWindow(app, on_select_callback)
    try:
        win.run()
    finally:
        win._hard_destroy()
        gc.collect()


# ==========================================================
# BLOQUE: Implementacion interna (no instanciar directamente)
# ==========================================================
class _SelectionWindow(QWidget):
    """
    Widget de seleccion de area. No instanciar directamente:
    usar capture_selection() para garantizar el patron ephemeral.
    """

    def __init__(self, app: QApplication, on_select_callback):
        self._app = app
        self.on_select = on_select_callback
        super().__init__()

        self.start_point = None
        self.end_point = None
        self.selecting = False

        # Recursos pesados -- siempre se liberan en _hard_destroy()
        self._screenshot: Image.Image | None = None  # PIL fullscreen
        self._pixmap: QPixmap | None = None          # Qt fullscreen

        self._toast = None
        self._toast_anim = None
        self._loop: QEventLoop | None = None

        self._result = None  # (x1, y1, x2, y2, cropped_pil)

    # ==========================================================
    # BLOQUE: Ciclo principal (ephemeral engine)
    # ==========================================================
    def run(self):
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

        if self._result and self.on_select:
            self.on_select(*self._result)

    def _finish(self):
        self.releaseMouse()
        if self._loop and self._loop.isRunning():
            self._loop.quit()

    def _hard_destroy(self):
        """
        Destruccion determinista de TODOS los recursos:
        - PIL Image (screenshot fullscreen)
        - QPixmap fullscreen + entradas del QPixmapCache global
        - Cursor personalizado (su QPixmap interno)
        - Widget Qt y sus hijos
        """
        # 1. Liberar recursos PIL
        if self._screenshot is not None:
            try:
                self._screenshot.close()
            except Exception:
                pass
            self._screenshot = None

        # 2. Liberar QPixmap fullscreen y limpiar el cache global de Qt.
        #    QPixmapCache mantiene un pool interno propio que NO se libera
        #    solo por perder la referencia de Python al QPixmap; hay que
        #    vaciarlo explicitamente para que la memoria grafica se suelte.
        self._pixmap = None
        QPixmapCache.clear()

        # 3. Liberar el cursor personalizado (su QPixmap de 24x24 tambien
        #    vive en el widget hasta que se resetea el cursor).
        try:
            self.unsetCursor()
        except Exception:
            pass

        # 4. Destruir resultado intermedio ya entregado al caller
        self._result = None

        # 5. Detener/limpiar cualquier animacion de toast pendiente
        if self._toast_anim is not None:
            try:
                self._toast_anim.stop()
            except Exception:
                pass
            self._toast_anim = None
        if self._toast is not None:
            try:
                self._toast.deleteLater()
            except Exception:
                pass
            self._toast = None

        # 6. Destruir widget Qt y todos sus hijos
        self.hide()
        self.deleteLater()

    # ==========================================================
    # BLOQUE: Captura de pantalla
    # ==========================================================
    def _capture_screenshot(self):
        from PySide6.QtGui import QImage

        screen = QApplication.primaryScreen()
        self._pixmap = screen.grabWindow(0)

        q_img = self._pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)

        width = q_img.width()
        height = q_img.height()
        ptr = q_img.bits()

        self._screenshot = Image.frombytes(
            "RGBA", (width, height), ptr, "raw", "RGBA"
        ).convert("RGB")

        # Liberar explicitamente el QImage intermedio: su buffer es del
        # mismo tamano que el screenshot completo (ptr referencia estos
        # bytes hasta que q_img se destruye).
        del ptr
        del q_img
        gc.collect()

        print(f"[*] Screenshot capturado: {width}x{height}")

    # ==========================================================
    # BLOQUE: Forzar primer plano
    # ==========================================================
    def _force_foreground(self):
        import ctypes
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            fg_hwnd = user32.GetForegroundWindow()
            cur_tid = kernel32.GetCurrentThreadId()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)

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

    # ==========================================================
    # BLOQUE: Utilidades visuales (Toast y Cursor)
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
        label.move(pos.x() - label.width() // 2, pos.y() - label.height() - 10)
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
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        center = size // 2
        length = 11
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
        cursor = QCursor(pixmap, center, center)
        # El QPixmap fuente del cursor queda referenciado internamente por
        # QCursor; liberamos nuestra copia local explicitamente.
        del pixmap
        return cursor

    # ==========================================================
    # BLOQUE: Eventos de Mouse
    # ==========================================================
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.selecting = True
            self.update()
        elif event.button() == Qt.RightButton:
            self._finish()

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.selecting:
            return

        self.selecting = False
        self.end_point = event.pos()
        sel = QRect(self.start_point, self.end_point).normalized()

        x1, y1 = sel.left(), sel.top()
        x2, y2 = sel.right(), sel.bottom()

        if (x2 - x1) < SELECTION_MIN_WIDTH or (y2 - y1) < SELECTION_MIN_HEIGHT:
            print("[WARN] Seleccion muy pequena")
            self._show_toast(QCoreApplication.translate('Selection', 'Area too small'), self.end_point)
            self.start_point = None
            self.end_point = None
            self.update()
            return

        new_x1 = max(0, x1 - 1)
        new_y1 = max(0, y1 - 1)
        new_x2 = x2 + 6
        new_y2 = y2 + 6

        cropped = self._screenshot.crop((new_x1, new_y1, new_x2, new_y2))

        self._result = (new_x1, new_y1, new_x2, new_y2, cropped)

        self._finish()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._finish()

    # ==========================================================
    # BLOQUE: Renderizado (sin cambios funcionales)
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

            left, top = sel.left(), sel.top()
            right, bottom = sel.right() + 1, sel.bottom() + 1

            painter.fillRect(QRect(0, 0, W, top), overlay_color)
            painter.fillRect(QRect(0, bottom, W, H - bottom), overlay_color)
            painter.fillRect(QRect(0, top, left, bottom - top), overlay_color)
            painter.fillRect(QRect(right, top, W - right, bottom - top), overlay_color)

            raw_color = get_selection_color()
            width = get_selection_border_width()
            inset = max(1, int(width) // 2)
            border_rect = QRect(
                sel.left() + inset,
                sel.top() + inset,
                sel.width() - inset * 2,
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
        import colorsys

        x0, y0 = rect.left(), rect.top()
        x1, y1 = rect.right(), rect.bottom()
        perimeter = 2 * (rect.width() + rect.height())
        if perimeter == 0:
            return

        pen = QPen()
        pen.setWidth(width)
        pen.setCosmetic(False)
        painter.setBrush(Qt.NoBrush)

        idx = 0

        def _set_color(i):
            hue = (hue_offset + (i / perimeter) * 360) % 360
            r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)
            pen.setColor(QColor(int(r * 255), int(g * 255), int(b * 255)))
            painter.setPen(pen)

        for x in range(x0, x1):
            _set_color(idx); painter.drawLine(x, y0, x + 1, y0); idx += 1
        for y in range(y0, y1):
            _set_color(idx); painter.drawLine(x1, y, x1, y + 1); idx += 1
        for x in range(x1, x0, -1):
            _set_color(idx); painter.drawLine(x, y1, x - 1, y1); idx += 1
        for y in range(y1, y0, -1):
            _set_color(idx); painter.drawLine(x0, y, x0, y - 1); idx += 1
