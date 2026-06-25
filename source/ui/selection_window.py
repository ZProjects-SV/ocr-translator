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
from PySide6.QtWidgets import QWidget, QApplication, QLabel
from PySide6.QtCore import Qt, QRect, QEventLoop, QTimer, QPropertyAnimation, QEasingCurve, QRectF
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
    """Ventana de selección de área de pantalla con screenshot congelada"""

    def __init__(self, on_select_callback):
        self.on_select = on_select_callback
        self._app = QApplication.instance() or QApplication([])
        super().__init__()

        self.start_point = None
        self.end_point   = None
        self.selecting   = False
        self.screenshot  = None
        self._pixmap     = None
        self._toast = None
        self._toast_anim = None
# (Dependencias/Interacciones: Usa 'config' para constantes base, pero en __init__ solo estructura variables. Interactúa con quién lo instancie mediante 'on_select_callback')

# ==========================================================
# BLOQUE: Utilidades Visuales (Toast y Cursor)
# ==========================================================
    def _show_toast(self, text, pos):
        # Crear un nuevo label para el toast
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

        # Posicionarlo un poco arriba del punto donde soltó el mouse
        x = pos.x() - label.width() // 2
        y = pos.y() - label.height() - 10
        label.move(x, y)
        label.setWindowOpacity(1.0)
        label.show()

        # Guardar referencia opcional
        self._toast = label

        # Animación de fade out
        anim = QPropertyAnimation(label, b"windowOpacity", self)
        anim.setDuration(800)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.OutQuad)

        self._toast_anim = anim

        # Cuando termine la animación, destruir el label y limpiar refs
        def _cleanup():
            label.deleteLater()
            if self._toast is label:
                self._toast = None
            if self._toast_anim is anim:
                self._toast_anim = None

        anim.finished.connect(_cleanup)
        anim.start()
        
    def _create_glow_cursor(self):
        """Crea un cursor de cruz fino, tipo luz, negro con borde blanco exterior"""
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        
        center = size // 2
        length = 11 
        cap_style = Qt.FlatCap

        glow_color = QColor(255, 255, 255, 100)
        glow_pen = QPen(glow_color, 4)
        glow_pen.setCapStyle(cap_style)
        painter.setPen(glow_pen)
        painter.drawLine(center - length - 1, center, center - 1, center)
        painter.drawLine(center + 1, center, center + length + 1, center)
        painter.drawLine(center, center - length - 1, center, center - 1)
        painter.drawLine(center, center + 1, center, center + length + 1)
        
        white_color = QColor(255, 255, 255, 255)
        white_pen = QPen(white_color, 3)
        white_pen.setCapStyle(cap_style)
        painter.setPen(white_pen)

        painter.drawLine(center - length, center, center - 1, center)
        painter.drawLine(center + 1, center, center + length, center)
        painter.drawLine(center, center - length, center, center - 1)
        painter.drawLine(center, center + 1, center, center + length)
        
        black_color = QColor(0, 0, 0, 255)
        black_pen = QPen(black_color, 1)
        painter.setPen(black_pen)
        painter.drawLine(center - length, center, center + length, center)
        painter.drawLine(center, center - length, center, center + length)
        
        painter.end()
        
        cursor = QCursor(pixmap, center, center)
        return cursor
# (Dependencias/Interacciones: Funciones aisladas de utilidad visual que se invocan dentro de esta misma clase en eventos de mouse o al mostrar la ventana)

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
        
        # Usar cursor personalizado de alto contraste
        custom_cursor = self._create_glow_cursor()
        self.setCursor(custom_cursor)
        
        self.setMouseTracking(True)

        screen = self._app.primaryScreen()
        geo    = screen.geometry()
        self.setGeometry(geo)

        super().show()
        self.activateWindow()
        self.raise_()
        self.setFocus()

        print("[*] Listo para seleccionar")
        self._loop = QEventLoop()
        self._loop.exec()

    def _capture_screenshot(self):
        screen = QApplication.primaryScreen()
        q_img  = screen.grabWindow(0)

        self._pixmap = q_img

        buffer = q_img.toImage()
        buffer = buffer.convertToFormat(buffer.Format.Format_RGBA8888)
        width  = buffer.width()
        height = buffer.height()
        ptr    = buffer.bits()

        self.screenshot = Image.frombytes(
            "RGBA", (width, height), ptr, "raw", "RGBA"
        ).convert("RGB")

        print(f"[*] Screenshot capturado: {width}x{height}")

    def close(self):
        if hasattr(self, '_loop') and self._loop.isRunning():
            self._loop.quit()
        super().close()
# (Dependencias/Interacciones: Depende de _create_glow_cursor(). Interactúa con el módulo PIL para el screenshot inicial. El bucle QEventLoop pausa la ejecución hasta que se cierre, comunicando el resultado a 'main.py')

# ==========================================================
# BLOQUE: Eventos de Mouse y Renderizado (PaintEvent)
# ==========================================================
    def paintEvent(self, event):
        import colorsys
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        overlay_color = QColor(*SELECTION_OVERLAY_COLOR)
        painter.drawPixmap(0, 0, self._pixmap)

        if self.selecting and self.start_point and self.end_point:
            sel = QRect(self.start_point, self.end_point).normalized()
            W, H = self.width(), self.height()

            left   = sel.left()
            top    = sel.top()
            right  = sel.right() + 1
            bottom = sel.bottom() + 1

            painter.fillRect(QRect(0,      0,       W,             top),             overlay_color)
            painter.fillRect(QRect(0,      bottom,  W,             H - bottom),      overlay_color)
            painter.fillRect(QRect(0,      top,     left,          bottom - top),    overlay_color)
            painter.fillRect(QRect(right,  top,     W - right,     bottom - top),    overlay_color)

            raw_color = get_selection_color()
            width = get_selection_border_width()
            inset = max(1, int(width) // 2)

            border_rect = QRect(
                sel.left() + inset,
                sel.top() + inset,
                sel.width() - inset * 2,
                sel.height() - inset * 2
            )

            if raw_color == "rainbow":
                if not hasattr(self, '_hue'):
                    self._hue = 0.0
                self._hue = (self._hue + 2) % 360  # velocidad del flujo

                self._draw_rainbow_border(painter, border_rect, width, self._hue)
                self.update()
            else:
                border = QColor(raw_color)
                pen = QPen(border, width, Qt.SolidLine)
                pen.setCosmetic(False)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(border_rect)

        else:
            painter.fillRect(self.rect(), overlay_color)

        painter.end()

    def _draw_rainbow_border(self, painter, rect, width, hue_offset):
        import colorsys

        x0 = rect.left()
        y0 = rect.top()
        x1 = rect.right()
        y1 = rect.bottom()

        # Perímetro en sentido horario: top, right, bottom, left
        segments = []
        for x in range(x0, x1):        segments.append((x,  y0, x+1, y0))  # top
        for y in range(y0, y1):        segments.append((x1, y,  x1, y+1))  # right
        for x in range(x1, x0, -1):   segments.append((x,  y1, x-1, y1))  # bottom
        for y in range(y1, y0, -1):   segments.append((x0, y,  x0, y-1))  # left

        total = len(segments)
        if total == 0:
            return

        pen = QPen()
        pen.setWidth(width)
        pen.setCosmetic(False)
        painter.setBrush(Qt.NoBrush)

        for i, (ax, ay, bx, by) in enumerate(segments):
            hue = (hue_offset + (i / total) * 360) % 360
            r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 1.0, 1.0)
            pen.setColor(QColor(int(r * 255), int(g * 255), int(b * 255)))
            painter.setPen(pen)
            painter.drawLine(ax, ay, bx, by)


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

        self.selecting = False
        self.end_point = event.pos()

        sel = QRect(self.start_point, self.end_point).normalized()
        
        # Coordenadas visuales originales
        x1, y1 = sel.left(), sel.top()
        x2, y2 = sel.right(), sel.bottom()

        if (x2 - x1) < SELECTION_MIN_WIDTH or (y2 - y1) < SELECTION_MIN_HEIGHT:
            print(f"[WARN] Selección muy pequeña")
            self._show_toast("El área es muy pequeña", self.end_point)

            self.start_point = None
            self.end_point = None
            self.selecting = False
            self.update()
            return

        # ── AQUÍ APLICAMOS EL AUMENTO DE 5PX ──
        # 1. Restamos 5px al inicio (arriba/izquierda)
        new_x1 = max(0, x1 - 1)
        new_y1 = max(0, y1 - 1)
        
        # 2. Sumamos 5px + 1px (por la exclusión de borde de PIL) al final (abajo/derecha)
        new_x2 = x2 + 5 + 1
        new_y2 = y2 + 5 + 1
        
        # 3. Recortamos usando estos nuevos márgenes ampliados
        cropped = self.screenshot.crop((new_x1, new_y1, new_x2, new_y2))
        
        self.close()

        if self.on_select:
            self.on_select(new_x1, new_y1, new_x2, new_y2, cropped)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
# (Dependencias/Interacciones: Depende fuertemente de 'config' (constantes) y 'preferences' (color/ancho). El evento mouseReleaseEvent dispara el callback 'self.on_select' que viaja hacia 'main.py' con la imagen recortada usando PIL)