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
import gc

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore    import Qt, QTimer, QPoint, Signal, QObject, QRect
from PySide6.QtGui     import (
    QPainter, QColor, QLinearGradient, QFont,
    QPixmap, QImage, QPen, QBrush
)
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==========================================================
# BLOQUE: Señales
# ==========================================================
class _Signals(QObject):
    set_status_signal   = Signal(str, float)
    set_download_signal = Signal()
    close_signal        = Signal()


# ==========================================================
# BLOQUE: Ventana de Animación de Cierre
# ==========================================================
class _AnimationWindow(QWidget):
    """Ventana pequeña que anima el icono hacia el tray."""

    def __init__(self, icon_size: int, frames_pil: list):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 🆕 Destruir al cerrar para no quedar en memoria
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setFixedSize(icon_size, icon_size)

        self._icon_size      = icon_size
        self._current_pixmap = None
        self._frames: list[QPixmap] = []

        for pil_img in frames_pil:
            try:
                w, h = pil_img.size
                data = pil_img.tobytes("raw", "RGBA")
                qi   = QImage(data, w, h, QImage.Format_RGBA8888).copy()
                self._frames.append(QPixmap.fromImage(qi))
                del data, qi
                pil_img.close()
            except Exception as e:
                print(f"[ERROR Splash] Frame inválido: {e}")
                self._frames.append(QPixmap())  # placeholder vacío

        if self._frames:
            self._current_pixmap = self._frames[0]

    def update_frame(self, idx: int, sz: int, nx: int, ny: int, alpha: float):
        if idx < len(self._frames) and not self._frames[idx].isNull():
            self._current_pixmap = self._frames[idx].scaled(
                sz, sz, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        self.setFixedSize(sz, sz)
        self.move(nx, ny)
        self.setWindowOpacity(alpha)
        self.update()

    def paintEvent(self, event):
        if not self._current_pixmap or self._current_pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self._current_pixmap)
        painter.end()

    def cleanup(self):
        """Libera todos los QPixmaps internos antes de cerrar."""
        self._current_pixmap = None
        # Reemplazar cada entrada con pixmap vacío para que Qt libere el buffer
        for i in range(len(self._frames)):
            self._frames[i] = QPixmap()
        self._frames.clear()
        gc.collect()


# ==========================================================
# BLOQUE: SplashScreen Principal
# ==========================================================
class SplashScreen(QWidget):
    WIDTH  = 480
    HEIGHT = 280

    @staticmethod
    def prebuild_frames(icon_path: str, output_dir: str,
                        icon_size: int = 72, steps: int = 20):
        """Genera los frames de animación como PNGs en disco."""
        os.makedirs(output_dir, exist_ok=True)
        img = Image.open(icon_path).convert("RGBA")
        for i in range(steps + 1):
            t  = (i / steps) ** 2
            sz = max(4, int(icon_size * (1 - t)))
            frame = img.resize((sz, sz), Image.Resampling.LANCZOS)
            frame.save(os.path.join(output_dir, f"frame_{i:03d}.png"))
            frame.close()
            del frame
        img.close()
        print(f"[Splash] {steps + 1} frames guardados en {output_dir}")

    def __init__(self):
        self._app = QApplication.instance() or QApplication([])
        super().__init__()

        self._closed   = False
        self._progress = 0.0
        self._status   = "Iniciando..."
        self._title    = "OCR Translator"
        self._subtitle = "Captura  .  Reconoce  .  Traduce"
        self._drag_pos = QPoint()

        # Referencias que se limpiarán al cerrar
        self._anim_win:   _AnimationWindow | None = None
        self._anim_timer: QTimer | None           = None

        self._sig = _Signals()
        self._sig.set_status_signal.connect(self._do_set_status)
        self._sig.set_download_signal.connect(self._do_set_download)
        self._sig.close_signal.connect(self._do_close)

        self._icon_pixmap = self._load_icon_pixmap(64)

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
                print(f"[ERROR] Splash: {e}")
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

        # 🆕 Liberar icono del splash antes de la animación
        if self._icon_pixmap is not None:
            self._icon_pixmap = None

        self._anim_step  = 0
        self._anim_steps = 20
        self._anim_delay = 15

        icon_size = 72
        cx = self.x() + self.WIDTH  // 2
        cy = self.y() + self.HEIGHT // 2

        # Cargar frames — se liberan dentro de _AnimationWindow.__init__
        frames_pil = self._load_animation_frames(icon_size, self._anim_steps)

        self._anim_win = _AnimationWindow(icon_size, frames_pil)
        # frames_pil ya fue consumida por _AnimationWindow, liberar lista
        del frames_pil
        gc.collect()

        self._anim_win.move(cx - icon_size // 2, cy - icon_size // 2)
        self._anim_win.show()

        screen = self._app.primaryScreen().geometry()
        self._anim_x0       = cx - icon_size // 2
        self._anim_y0       = cy - icon_size // 2
        self._anim_target_x = screen.width()  - 80
        self._anim_target_y = screen.height() - 18
        self._anim_size     = icon_size

        self._anim_timer = QTimer()
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start(self._anim_delay)

    def _anim_tick(self):
        i     = self._anim_step
        steps = self._anim_steps
        t     = (i / steps) ** 2
        sz    = max(4, int(self._anim_size * (1 - t)))
        nx    = int(self._anim_x0 + (self._anim_target_x - self._anim_x0) * t)
        ny    = int(self._anim_y0 + (self._anim_target_y - self._anim_y0) * t)
        alpha = max(0.0, 1.0 - t * 1.2)

        try:
            if self._anim_win:
                self._anim_win.update_frame(i, sz, nx, ny, alpha)
        except Exception as e:
            print(f"[ERROR Splash] Falló frame de animación: {e}")

        self._anim_step += 1

        if self._anim_step > steps:
            self._anim_timer.stop()

            # 🆕 Limpiar QPixmaps de la ventana de animación ANTES de cerrarla
            if self._anim_win:
                try:
                    self._anim_win.cleanup()
                    self._anim_win.close()
                    self._anim_win.deleteLater()
                except Exception:
                    pass
                self._anim_win = None

            # 🆕 Limpiar timer
            try:
                self._anim_timer.deleteLater()
            except Exception:
                pass
            self._anim_timer = None

            # 🆕 GC antes de destruir el splash
            gc.collect()
            self.deleteLater()


    # ── Pintado ──────────────────────────────────────────────
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

        if self._icon_pixmap:
            ix = (self.WIDTH - 64) // 2
            painter.drawPixmap(ix, 16, self._icon_pixmap)

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
            "v1.1.0  -  PaddleOCR  -  Google Translate"
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)


    # ── Helpers ──────────────────────────────────────────────
    def _load_icon_pixmap(self, size: int) -> QPixmap | None:
        try:
            base = sys._MEIPASS
        except AttributeError:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        path = os.path.join(base, "resources", "icon.ico")
        if not os.path.exists(path):
            return None
        try:
            img     = Image.open(path).convert("RGBA").resize(
                (size, size), Image.Resampling.LANCZOS
            )
            data    = img.tobytes("raw", "RGBA")
            q_image = QImage(data, size, size, QImage.Format_RGBA8888).copy()
            pixmap  = QPixmap.fromImage(q_image)
            del data, q_image
            img.close()
            return pixmap
        except Exception as e:
            print(f"[ERROR Splash] No se pudo cargar el icono: {e}")
            return None

    def _load_animation_frames(self, icon_size: int, steps: int) -> list:
        """
        Carga frames uno a uno y los devuelve como lista de PIL Images.
        _AnimationWindow los convierte a QPixmap y cierra cada PIL Image.
        """
        try:
            base = sys._MEIPASS
        except AttributeError:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        frames_dir = os.path.join(base, "resources", "splash_frames")
        frames_pil = []

        # Opción 1: leer desde disco (frames pre-generados)
        if os.path.isdir(frames_dir):
            try:
                for i in range(steps + 1):
                    p = os.path.join(frames_dir, f"frame_{i:03d}.png")
                    frames_pil.append(Image.open(p).convert("RGBA"))
                return frames_pil
            except Exception as e:
                print(f"[ERROR Splash] Falló lectura de frames: {e}")
                # Cerrar los que se hayan abierto antes del fallo
                for f in frames_pil:
                    try:
                        f.close()
                    except Exception:
                        pass
                frames_pil = []

        # Opción 2: generar desde el .ico en memoria
        path = os.path.join(base, "resources", "icon.ico")
        if not os.path.exists(path):
            return []
        try:
            src = Image.open(path).convert("RGBA")
            for i in range(steps + 1):
                t     = (i / steps) ** 2
                sz    = max(4, int(icon_size * (1 - t)))
                frame = src.resize((sz, sz), Image.Resampling.LANCZOS)
                frames_pil.append(frame)
                # 🆕 No cerrar frame aquí — _AnimationWindow lo cerrará
            src.close()
            del src
            return frames_pil
        except Exception as e:
            print(f"[ERROR Splash] Falló generación de frames: {e}")
            for f in frames_pil:
                try:
                    f.close()
                except Exception:
                    pass
            return []