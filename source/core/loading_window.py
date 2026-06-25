import io
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QProgressBar, QApplication, QHBoxLayout, QPushButton, QSizePolicy, QStyle
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRect
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QFont as QF, QPen
from PIL import Image, ImageFilter

from preferences import (
    get_result_font_family,
)


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

        self._signals.update_status.connect(self._do_update_status)
        self._signals.show_result.connect(self._do_show_result)
        self._signals.close_window.connect(self._delayed_close)
# (Dependencias/Interacciones: Depende de PySide6 para señales. Es instanciado por 'main.py' pasándole las coordenadas de la captura. Se comunica con 'preferences.py' implícitamente al renderizar.)


# ==========================================================
# BLOQUE: API Pública (Mostrar, Actualizar y Cerrar)
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
# (Dependencias/Interacciones: Depende de los Slots definidos más abajo. Es llamado por 'main.py' para iniciar el estado de "Cargando..." y para mostrar el resultado final mediante el paso de la imagen recortada y los bloques de texto.)


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
# (Dependencias/Interacciones: Se disparan mediante las señales de _Signals cuando 'main.py' (en un hilo secundario) extrae el texto, lo traduce y necesita mostrarlo en el hilo principal.)


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

            total_w = disp_w + (padding_x * 2)
            total_h = disp_h + 50 + fram_margin + padding_y
            
            self.window.setFixedSize(total_w, total_h)
            self._layout.setContentsMargins(padding_x, padding_y, padding_x, 0)
            self._layout.setSpacing(0)

            canvas_label = QLabel()
            canvas_label.setFixedSize(disp_w, disp_h)
            canvas_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            blurred = image.copy()
            for block in blocks:
                bx1, by1, bx2, by2 = block["box"]
                x1 = min(bx1, bx2)
                x2 = max(bx1, bx2)
                y1 = min(by1, by2)
                y2 = max(by1, by2)

                pad = 3
                crop_x1 = max(0, x1 - pad)
                crop_y1 = max(0, y1 - pad)
                crop_x2 = min(img_w, x2 + pad)
                crop_y2 = min(img_h, y2 + pad)

                if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                    continue

                region = image.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                region = region.filter(ImageFilter.GaussianBlur(radius=6))
                blurred.paste(region, (crop_x1, crop_y1))

            blurred = blurred.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            blurred.save(buf, format='PNG')
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read())

            painter = QPainter(pixmap)
            translated_lines = translated_text.split('\n')

            scale_factor = disp_w / img_w

            for i, block in enumerate(blocks):
                if i >= len(translated_lines):
                    break
                bx1, by1, bx2, by2 = block['box']
                
                rx1 = int(bx1 * scale_factor)
                ry1 = int(by1 * scale_factor)
                rx2 = int(bx2 * scale_factor)
                ry2 = int(by2 * scale_factor)
                
                # Color del texto original
                region_crop = image.crop((max(0, bx1), max(0, by1), min(img_w, bx2), min(img_h, by2)))
                region_rgb = region_crop.convert("RGB")
                pixels = list(region_rgb.getdata())
                pixels_sorted = sorted(pixels, key=lambda p: p[0]+p[1]+p[2], reverse=True)
                top_pixels = pixels_sorted[:max(1, len(pixels_sorted)//5)]
                avg_r = int(sum(p[0] for p in top_pixels) / len(top_pixels))
                avg_g = int(sum(p[1] for p in top_pixels) / len(top_pixels))
                avg_b = int(sum(p[2] for p in top_pixels) / len(top_pixels))
                text_color = QColor(avg_r, avg_g, avg_b)

                box_w = rx2 - rx1
                box_h = ry2 - ry1
                text = translated_lines[i]

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
                    text
                )

            painter.end()
            canvas_label.setPixmap(pixmap)
            
            img_layout = QHBoxLayout()
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.addWidget(canvas_label)
            img_layout.addStretch()
            self._layout.addLayout(img_layout)
            
        else:
            self.window.setFixedSize(400, 200)
            canvas_label = QLabel(translated_text)
            canvas_label.setStyleSheet("color: white; padding: 10px;")
            canvas_label.setFont(QFont(get_result_font_family(), 11))
            canvas_label.setWordWrap(True)
            self._layout.addWidget(canvas_label)

        # ── Botón cerrar ── #
        btn_close = QPushButton("Cerrar")
        btn_close.setFont(QFont("Segoe UI", 9))
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 16px;
            }
            QPushButton:hover  { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
        """)
        btn_close.clicked.connect(self.close)
        
        btn_layout = QHBoxLayout()
        # Un poco de margen para que el botón no esté pegado al borde
        btn_layout.setContentsMargins(0, 10, 10, 10)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        self._layout.addLayout(btn_layout)

    def _on_close_event(self, event):
        self.is_closed = True
        event.accept()
# (Dependencias/Interacciones: Depende fuertemente de la librería PIL para difuminar el fondo, de 'preferences.py' para obtener la fuente del texto traducido, y de los datos (image, blocks) enviados por 'main.py' provenientes de 'ocr_engine.py'.)