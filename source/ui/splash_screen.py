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
from __future__ import annotations
import os
import sys
import threading

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore    import Qt, QTimer, QPoint, Signal, QObject, QRect
from PySide6.QtGui     import QPainter, QColor, QLinearGradient, QFont, QPen, QBrush

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==========================================================
# BLOQUE: Señales
# ==========================================================
class _Signals(QObject):
    set_status_signal   = Signal(str, float)
    set_download_signal = Signal()
    close_signal        = Signal()


# ==========================================================
# BLOQUE: Ventana de Animación Simulada
# ==========================================================
class _AnimationWindow(QWidget):
    """Ventana simulada: se muestra y se cierra inmediatamente."""

    def __init__(self, icon_size: int, frames_pil: list):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedSize(icon_size, icon_size)

        # Cerrar cualquier PIL Image que se haya pasado para no dejar memoria colgada
        for pil_img in frames_pil:
            try:
                pil_img.close()
            except Exception:
                pass

        # Auto-cierre casi inmediato para desbloquear el hilo principal
        QTimer.singleShot(50, self._auto_close)

    def _auto_close(self):
        try:
            self.close()
            self.deleteLater()
        except Exception:
            pass

    def update_frame(self, idx: int, sz: int, nx: int, ny: int, alpha: float):
        pass  # No-op

    def paintEvent(self, event):
        pass  # No pinta nada

    def cleanup(self):
        pass  # No-op


# ==========================================================
# BLOQUE: SplashScreen Simulado
# ==========================================================
class SplashScreen(QWidget):
    WIDTH  = 480
    HEIGHT = 280

    @staticmethod
    def prebuild_frames(icon_path: str, output_dir: str,
                        icon_size: int = 72, steps: int = 20):
        """Simulación: no genera ni guarda nada en disco."""
        print(f"[Splash-MOCK] prebuild_frames omitido ({output_dir})")

    def __init__(self):
        self._app = QApplication.instance() or QApplication([])
        super().__init__()

        self._closed   = False
        self._progress = 0.0
        self._status   = "Iniciando..."
        self._title    = "OCR Translator"
        self._subtitle = "Captura  .  Reconoce  .  Traduce"
        self._drag_pos = QPoint()

        self._anim_win:   _AnimationWindow | None = None
        self._anim_timer: QTimer | None           = None

        self._sig = _Signals()
        self._sig.set_status_signal.connect(self._do_set_status)
        self._sig.set_download_signal.connect(self._do_set_download)
        self._sig.close_signal.connect(self._do_close)

        self._icon_pixmap = None  # Simulado: sin carga de icono

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        screen = self._app.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.WIDTH)  // 2,
            (screen.height() - self.HEIGHT) // 2
        )


    # ── API pública ──────────────────────────────────────────
    def set_status(self, text: str, progress: float = None):
        if self._closed:
            return
        p = progress if progress is not None else self._progress
        self._sig.set_status_signal.emit(text, p)

    def set_download_mode(self):
        if self._closed:
            return
        self._sig.set_download_signal.emit()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._sig.close_signal.emit()

    def run_async(self, callback):
        def _worker():
            try:
                callback(self)
            except Exception as e:
                print(f"[ERROR] Splash-MOCK: {e}")
                self.close()
        threading.Thread(target=_worker, daemon=True).start()


    # ── Slots Qt (hilo principal) ────────────────────────────
    def _do_set_status(self, text: str, progress: float):
        self._status   = text
        self._progress = progress
        self.update()

    def _do_set_download(self):
        self._title    = "Descargando modelos OCR"
        self._subtitle = "Primera ejecución  -  Esto solo ocurre una vez"
        self.update()

    def _do_close(self):
        self.hide()

        # Cerrar inmediatamente sin animación
        try:
            self.close()
            self.deleteLater()
        except Exception:
            pass


    # ── Pintado (mantiene la UI visual para que no crashee si se muestra) ──
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, self.WIDTH, self.HEIGHT)
        grad.setColorAt(0.0, QColor(5,  51,  222))
        grad.setColorAt(0.5, QColor(13, 124, 242))
        grad.setColorAt(1.0, QColor(21, 226, 243))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.WIDTH, self.HEIGHT, 12, 12)

        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 22, QFont.Bold))
        painter.drawText(QRect(0, 96, self.WIDTH, 30), Qt.AlignCenter, self._title)

        painter.setPen(QColor("#cce8ff"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(QRect(0, 124, self.WIDTH, 20), Qt.AlignCenter, self._subtitle)

        painter.setPen(QPen(QColor("#4a7fc1"), 1))
        painter.drawLine(60, 148, self.WIDTH - 60, 148)

        painter.setPen(QColor("#cce8ff"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRect(0, 162, self.WIDTH, 20), Qt.AlignCenter, self._status)

        bx, by, bw, bh, br = 60, 187, self.WIDTH - 120, 12, 6
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1a5cb8"))
        painter.drawRoundedRect(bx, by, bw, bh, br, br)
        fill_w = max(br * 2, int(bw * self._progress))
        painter.setBrush(QColor("#0daaf7"))
        painter.drawRoundedRect(bx, by, fill_w, bh, br, br)

        painter.setPen(QColor("#7ab3e0"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRect(0, self.HEIGHT - 22, self.WIDTH, 16),
            Qt.AlignCenter,
            "v1.1.0  -  MOCK MODE"
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)


    # ── Helpers Simulados ────────────────────────────────────
    def _load_icon_pixmap(self, size: int) -> None:
        return None  # Sin carga de archivos

    def _load_animation_frames(self, icon_size: int, steps: int) -> list:
        return []  # Sin carga de archivos