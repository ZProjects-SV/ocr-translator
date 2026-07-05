from __future__ import annotations
import os
import sys
import threading

from PySide6.QtWidgets import QWidget, QApplication, QPushButton
from PySide6.QtCore import Qt, QPoint, Signal, QObject, QRect, QTimer
from PySide6.QtGui import QPainter, QColor, QLinearGradient, QFont, QPen, QBrush, QPixmap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _Signals(QObject):
    set_status_signal = Signal(str, float)
    set_download_signal = Signal()
    close_signal = Signal()
    show_button_signal = Signal()
    set_download_anim_signal = Signal(bool)


class SplashScreen(QWidget):
    WIDTH = 480
    HEIGHT = 290

    @staticmethod
    def prebuild_frames(icon_path: str, output_dir: str, icon_size: int = 72, steps: int = 20):
        pass

    def __init__(self):
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("SplashScreen requiere una instancia existente de QApplication.")

        super().__init__()
        self._app = app

        self._closed = False
        self._progress = 0.0
        self._status = "Iniciando..."
        self._title = "OCR Translator"
        self._subtitle = "Captura  .  Reconoce  .  Traduce"
        self._drag_pos = QPoint()

        self._download_anim_base_text = "Descargando modelos"
        self._download_anim_enabled = False
        self._download_anim_dots = 0

        self._icon_pixmap = None
        self._load_icon()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        screen = self._app.primaryScreen().geometry()
        self.move(
            (screen.width() - self.WIDTH) // 2,
            (screen.height() - self.HEIGHT) // 2
        )

        self._sig = _Signals()
        self._sig.set_status_signal.connect(self._do_set_status)
        self._sig.set_download_signal.connect(self._do_set_download)
        self._sig.close_signal.connect(self._do_close)
        self._sig.show_button_signal.connect(self._do_show_button)
        self._sig.set_download_anim_signal.connect(self._set_download_animation)

        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(500)
        self._dot_timer.timeout.connect(self._advance_download_dots)

        self._btn_accept = QPushButton("Aceptar", self)
        self._btn_accept.setFixedSize(120, 34)
        self._btn_accept.setCursor(Qt.PointingHandCursor)
        self._btn_accept.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #0d7cf2;
                border: none;
                border-radius: 17px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e2f0ff;
            }
        """)
        btn_x = (self.WIDTH - self._btn_accept.width()) // 2
        btn_y = self.HEIGHT - 54
        self._btn_accept.move(btn_x, btn_y)
        self._btn_accept.hide()
        self._btn_accept.clicked.connect(self._close_safely)

    def _load_icon(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_dir, "resources", "icon.ico")
            if os.path.exists(icon_path):
                self._icon_pixmap = QPixmap(icon_path)
        except Exception:
            self._icon_pixmap = None

    def set_status(self, text: str, progress: float = None):
        if self._closed:
            return
        p = self._progress if progress is None else progress
        self._sig.set_status_signal.emit(text, p)

    def set_download_mode(self):
        if self._closed:
            return
        self._sig.set_download_signal.emit()

    def set_download_animation_enabled(self, enabled: bool):
        if self._closed:
            return
        self._sig.set_download_anim_signal.emit(enabled)

    def show_completion_button(self):
        if self._closed:
            return
        self._sig.show_button_signal.emit()

    def run_async(self, callback):
        def _worker():
            try:
                callback(self)
            except Exception as e:
                print(f"[ERROR] Splash-Worker: {e}")
                self.set_download_animation_enabled(False)
                self.set_status(f"Error: {e}", 1.0)
                self.show_completion_button()

        threading.Thread(target=_worker, daemon=True).start()

    def _do_set_status(self, text: str, progress: float):
        self._status = text
        self._progress = max(0.0, min(1.0, float(progress)))
        self.update()

    def _do_set_download(self):
        self._title = "Descargando modelos OCR"
        self._subtitle = "Primera ejecución  -  Esto solo ocurre una vez"
        self.update()

    def _set_download_animation(self, enabled: bool):
        self._download_anim_enabled = enabled
        self._download_anim_dots = 0

        if enabled:
            if not self._dot_timer.isActive():
                self._dot_timer.start()
        else:
            self._dot_timer.stop()

    def _advance_download_dots(self):
        if not self._download_anim_enabled or self._closed:
            self._dot_timer.stop()
            return

        if self._status.startswith("Descargando"):
            self._download_anim_dots = (self._download_anim_dots % 3) + 1
            animated = self._download_anim_base_text + ("." * self._download_anim_dots)
            self._status = animated
            self.update()

    def _do_show_button(self):
        self._set_download_animation(False)
        self._btn_accept.show()
        self._btn_accept.raise_()
        self.update()

    def _close_safely(self):
        if self._closed:
            return
        self._closed = True
        self._dot_timer.stop()
        self.hide()
        self.deleteLater()

    def _do_close(self):
        self._close_safely()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, self.WIDTH, self.HEIGHT)
        grad.setColorAt(0.0, QColor(5, 51, 222))
        grad.setColorAt(0.5, QColor(13, 124, 242))
        grad.setColorAt(1.0, QColor(21, 226, 243))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.WIDTH, self.HEIGHT, 12, 12)

        icon_size = 56
        icon_x = (self.WIDTH - icon_size) // 2
        icon_y = 25

        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawEllipse(icon_x, icon_y, icon_size, icon_size)

        if self._icon_pixmap and not self._icon_pixmap.isNull():
            scaled_icon = self._icon_pixmap.scaled(
                icon_size - 18,
                icon_size - 18,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            ix = icon_x + (icon_size - scaled_icon.width()) // 2
            iy = icon_y + (icon_size - scaled_icon.height()) // 2
            painter.drawPixmap(ix, iy, scaled_icon)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 17, QFont.Bold))
        painter.drawText(QRect(0, 92, self.WIDTH, 28), Qt.AlignCenter, self._title)

        painter.setPen(QColor("#cce8ff"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRect(0, 118, self.WIDTH, 20), Qt.AlignCenter, self._subtitle)

        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(60, 145, self.WIDTH - 60, 145)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRect(0, 158, self.WIDTH, 20), Qt.AlignCenter, self._status)

        bx, by, bw, bh, br = 60, 188, self.WIDTH - 120, 8, 4
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 40))
        painter.drawRoundedRect(bx, by, bw, bh, br, br)

        fill_w = int(bw * self._progress)
        if fill_w > 0:
            fill_w = max(br * 2, fill_w)
            painter.setBrush(QColor("#ffffff"))
            painter.drawRoundedRect(bx, by, fill_w, bh, br, br)

        painter.setPen(QColor("#e0e0e0"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRect(0, 200, self.WIDTH, 16),
            Qt.AlignCenter,
            f"{int(self._progress * 100)}%"
        )

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()