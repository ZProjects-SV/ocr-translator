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
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QProgressBar, QApplication, QHBoxLayout, QPushButton, QStyle
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont

# Se importa para no romper si algún otro archivo lo exige, pero no se usa.
try:
    from preferences import get_result_font_family
except ImportError:
    def get_result_font_family():
        return "Segoe UI"


# ==========================================================
# BLOQUE: Widget de imagen simulado
# ==========================================================
class ZoomableImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Simulación visual básica
        self.setText("🖼️ [Vista de imagen simulada]")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background-color: #2a2a2a; color: #888888; border: 1px dashed #555;")

    def setSourcePixmap(self, pixmap):
        # No hace nada con el pixmap real, solo mantiene el texto simulado
        pass

    def resetView(self):
        # No hay vista que resetear
        pass

    def clearPixmaps(self):
        # Limpieza segura simulada
        pass


# ==========================================================
# BLOQUE: Señales (Mantenidas idénticas para compatibilidad)
# ==========================================================
class _Signals(QObject):
    update_status = Signal(str)
    show_result   = Signal(str)
    close_window  = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)


# ==========================================================
# BLOQUE: _ResultWidget (Mantenido para controlar el cierre)
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
# BLOQUE: Ventana Unificada (Modo Simulado)
# ==========================================================
class UnifiedResultWindow:
    """Versión simulada: acepta los mismos parámetros pero muestra estados por defecto."""

    def __init__(self, x1, y1, x2, y2, margin=0):
        self.x1        = x1
        self.y1        = y1
        self.x2        = x2
        self.y2        = y2
        self.margin    = margin
        
        self.window: _ResultWidget | None = None
        self.is_closed = False
        
        # Variables simuladas (nulas para ahorrar memoria)
        self._image    = None
        self._blocks   = None
        self._signals  = None
        self._pixmap_before = None
        self._pixmap_after  = None
        self._showing_after = True
        self._zoom_label    = None
        self._toggle_btn    = None

    # ==========================================================
    # BLOQUE: Destrucción determinista (Segura y limpia)
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
        self._pixmap_after  = None
        self._image         = None
        self._blocks        = None
        self._toggle_btn    = None

        if hasattr(self, '_layout') and self._layout is not None:
            while self._layout.count():
                item = self._layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

    # ==========================================================
    # BLOQUE: API Pública
    # ==========================================================
    def show_loading(self):
        self.width = min(max(self.x2 - self.x1, 320), 500)

        self.window = _ResultWidget(owner=self)
        self._signals = _Signals(self.window)
        self._signals.update_status.connect(self._do_update_status)
        self._signals.show_result.connect(self._do_show_result)
        self._signals.close_window.connect(self._delayed_close)
        
        self.window.setWindowTitle("OCR Translator (Simulado)")

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
        # Ignoramos la imagen y los bloques reales para no procesar nada pesado
        self._image  = None
        self._blocks = None
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
    # BLOQUE: Slots Qt (Hilo principal)
    # ==========================================================
    def _do_update_status(self, message):
        if self.is_closed or not hasattr(self, '_status_label'):
            return
        self._status_label.setText(message)

    def _do_show_result(self, translated_text):
        if self.is_closed or not self.window:
            return

        self.window.setVisible(False)

        # Limpiar layout anterior
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.deleteLater()

        self.window.setStyleSheet("background-color: #1e1e1e;")
        
        # Mostrar resultado simulado (solo texto)
        self.window.setMinimumSize(0, 0)
        self.window.setMaximumSize(16777215, 16777215)
        self.window.resize(450, 200)
        
        canvas_label = QLabel(translated_text)
        canvas_label.setStyleSheet("color: white; padding: 15px;")
        canvas_label.setFont(QFont(get_result_font_family(), 11))
        canvas_label.setWordWrap(True)
        self._layout.addWidget(canvas_label)

        # Barra de botones simulada
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 8, 10, 10)
        btn_bar.addStretch()

        btn_close = QPushButton("Cerrar")
        btn_close.setFont(QFont("Segoe UI", 9))
        btn_close.setFixedHeight(32)
        btn_close.setStyleSheet("""
            QPushButton { background-color: #0078d4; color: white; border: none; border-radius: 4px; padding: 0 16px; }
            QPushButton:hover   { background-color: #106ebe; }
            QPushButton:pressed { background-color: #005a9e; }
        """)
        btn_close.clicked.connect(self.close)
        btn_bar.addWidget(btn_close)

        self._layout.addLayout(btn_bar)
        self.window.setVisible(True)

    # ==========================================================
    # BLOQUE: UI de Loading (Mantenida para dar feedback visual)
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
            QProgressBar { background-color: #333333; border: none; border-radius: 2px; }
            QProgressBar::chunk { background-color: #0078d4; border-radius: 2px; }
        """)
        self._layout.addWidget(self._progress)

        hint = QLabel("Esto puede tardar unos segundos")
        hint.setFont(QFont("Segoe UI", 8))
        hint.setStyleSheet("color: #b0b0b0;")
        hint.setAlignment(Qt.AlignLeft)
        self._layout.addWidget(hint)

    # --- Métodos originales eliminados/omitidos ---
    # (_dominant_text_color_from_array, _pil_to_pixmap, _build_original_pixmap, 
    #  _build_translated_pixmap, _toggle_view) han sido removidos porque 
    # no se procesa ninguna imagen en esta versión simulada.