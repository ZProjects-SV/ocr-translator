from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QStackedWidget, QFormLayout, QLineEdit, QCheckBox,
    QPushButton, QColorDialog, QFontComboBox, QFrame, QDialog,
    QAbstractButton, QComboBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QEvent
from PySide6.QtGui import QCloseEvent, QColor, QFont, QKeySequence

from preferences import (
    get_translation_source, set_translation_source,
    get_translation_target, set_translation_target,
    get_translation_cache_enabled, set_translation_cache_enabled,
    get_capture_hotkeys, set_capture_hotkeys,
    get_capture_secondary_1, set_capture_secondary_1,
    get_capture_secondary_2, set_capture_secondary_2,
    get_selection_color, set_selection_color,
    get_result_font_family, set_result_font_family,
    get_selection_border_width, set_selection_border_width,
)
from config import (
    APP_NAME, SELECTION_BORDER_WIDTH,
    TRANSLATION_SOURCE, TRANSLATION_TARGET, TRANSLATION_CACHE_ENABLED,
    CAPTURE_HOTKEYS, CAPTURE_SECONDARY_1, CAPTURE_SECONDARY_2,
    SELECTION_COLOR, RESULT_FONT_FAMILY,
    TRANSLATION_LANG_CHOICES, TRANSLATION_LANG_DISPLAY,
)
from core.ocr_engine import OCREngine

# ==========================================================
# BLOQUE: Estilos Visuales Reutilizables (CSS/Qt StyleSheets)
# ==========================================================
_STYLE_LABEL   = "color: #ffffff;"
_STYLE_SUBLABEL = "color: #c0c0c0; font-size: 11px;"
_STYLE_TITLE   = "color: #ffffff; font-size: 14px; font-weight: 600;"
_STYLE_INPUT   = """
    QLineEdit, QSpinBox, QFontComboBox {
        background-color: #3a3a3a;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 4px 6px;
    }
    QLineEdit:focus, QSpinBox:focus, QFontComboBox:focus {
        border: 1px solid #0078d4;
    }
"""
_STYLE_BTN_COLOR = """
    QPushButton {
        border: 2px solid #555555;
        border-radius: 4px;
        min-width: 64px;
        min-height: 26px;
    }
    QPushButton:hover { border-color: #0078d4; }
"""
_STYLE_SIDEBAR = """
    QListWidget {
        background-color: #202020;
        color: #ffffff;
        border: 1px solid #444444;
    }
    QListWidget::item { padding: 8px 6px; }
    QListWidget::item:selected {
        background-color: #0078d4;
        color: #ffffff;
    }
"""
_STYLE_SEPARATOR = "background-color: #444444;"
_STYLE_BTN_SAVE = """
    QPushButton {
        background-color: #0078d4;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 6px 18px;
        font-weight: 600;
        margin-left: 12px;
    }
    QPushButton:hover { background-color: #1084d8; }
    QPushButton:pressed { background-color: #005fa3; }
"""
_STYLE_BTN_CANCEL = """
    QPushButton {
        background-color: #3a3a3a;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 6px 18px;
    }
    QPushButton:hover { background-color: #484848; }
"""
_STYLE_BTN_RESET = """
    QPushButton {
        background-color: #3a3a3a;
        color: #888888;
        border: 1px solid #444444;
        border-radius: 4px;
        padding: 6px 18px;
    }
    QPushButton:enabled {
        background-color: #7a6010;
        color: #ffd700;
        border: 1px solid #d4a800;
    }
    QPushButton:enabled:hover {
        background-color: #9a7a14;
        border-color: #ffd700;
    }
    QPushButton:enabled:pressed {
        background-color: #4a3a08;
    }
    QPushButton:disabled {
        color: #555555;
    }
"""
_STYLE_FONTCOMBO = """
    QFontComboBox {
        background-color: #3a3a3a;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 4px 6px;
    }
    QFontComboBox:focus { border: 1px solid #0078d4; }
    QFontComboBox:hover { border-color: #0078d4; }
    QFontComboBox::drop-down { width: 0px; border: none; }
    QFontComboBox QAbstractItemView {
        background-color: #3a3a3a;
        color: #ffffff;
        selection-background-color: #0078d4;
        border: 1px solid #555555;
    }
"""
_STYLE_LANG_COMBO = """
    QComboBox {
        background-color: #3a3a3a;
        color: #ffffff;
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 4px 24px 4px 8px;
        min-width: 180px;
    }
    QComboBox:hover, QComboBox:focus { border-color: #0078d4; }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: right center;
        width: 20px;
        border-left: 1px solid #555555;
    }
    QComboBox::down-arrow {
        image: none;
        width: 0; height: 0;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid #aaaaaa;
        margin-right: 4px;
    }
    QComboBox QAbstractItemView {
        background-color: #2e2e2e;
        color: #ffffff;
        selection-background-color: #0078d4;
        selection-color: #ffffff;
        border: 1px solid #555555;
        outline: none;
    }
    QComboBox QAbstractItemView::item {
        padding: 6px 10px;
        min-height: 24px;
    }
"""
# (Dependencias/Interacciones: Bloque pasivo. Solo provee de hojas de estilo a los widgets que se construyen en los siguientes bloques.)


# ==========================================================
# BLOQUE: Widgets Utilitarios Personalizados
# ==========================================================
class _Signals(QObject):
    closed = Signal()

    def __init__(self):
        super().__init__()


class _StepSpinBox(QWidget):
    """Reemplazo de QSpinBox con botones + (arriba) y − (abajo) apilados a la derecha."""
    valueChanged = Signal(int)

    def __init__(self, min_val=0, max_val=99, suffix="", parent=None):
        super().__init__(parent)
        self._value  = min_val
        self._min    = min_val
        self._max    = max_val
        self._suffix = suffix

        self._btn_inc = QPushButton("＋")
        self._btn_dec = QPushButton("－")
        self._label   = QLabel()

        for btn in (self._btn_dec, self._btn_inc):
            btn.setFixedSize(16, 12)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #484848;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 2px;
                    font-weight: 700;
                    font-size: 8px;
                    padding: 0px;
                }
                QPushButton:hover   { background-color: #0078d4; border-color: #0078d4; }
                QPushButton:pressed { background-color: #005fa3; }
            """)

        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumWidth(38)
        self._label.setStyleSheet("""
            color: #ffffff;
            background-color: #3a3a3a;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 2px 4px;
        """)

        btn_col = QVBoxLayout()
        btn_col.setContentsMargins(0, 0, 0, 0)
        btn_col.setSpacing(1)
        btn_col.addWidget(self._btn_inc)
        btn_col.addWidget(self._btn_dec)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)
        row.addWidget(self._label)
        row.addLayout(btn_col)

        self._btn_dec.clicked.connect(lambda: self.setValue(self._value - 1))
        self._btn_inc.clicked.connect(lambda: self.setValue(self._value + 1))
        self._refresh()

    def _refresh(self):
        self._label.setText(f"{self._value}{self._suffix}")
        self._btn_dec.setEnabled(self._value > self._min)
        self._btn_inc.setEnabled(self._value < self._max)

    def setValue(self, v: int):
        v = max(self._min, min(self._max, v))
        if v != self._value:
            self._value = v
            self._refresh()
            self.valueChanged.emit(self._value)

    def value(self) -> int:
        return self._value

    def setRange(self, mn: int, mx: int):
        self._min, self._max = mn, mx
        self.setValue(self._value)

    def setFixedWidth(self, w: int):
        pass


class _HotkeyDialog(QDialog):
    """Dialogo modal para asignar un hotkey."""
    _MODIFIER_KEYS = {
        Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt,
        Qt.Key_Meta, Qt.Key_AltGr,
    }

    def __init__(self, current: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Asignar atajo")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setFixedSize(360, 220)
        self.setStyleSheet("background-color: #2a2a2a; color: #ffffff;")
        self.setModal(True)

        self._result: str = current
        self._base_key: str = ""
        self._waiting: bool = False

        parts = [p.strip().lower() for p in current.split("+")] if current else []
        self._init_ctrl  = "ctrl"  in parts
        self._init_shift = "shift" in parts
        self._init_alt   = "alt"   in parts
        mod_names = {"ctrl", "shift", "alt", "meta"}
        base_parts = [p for p in parts if p not in mod_names]
        self._base_key = base_parts[-1] if base_parts else ""

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(12)

        lbl_mods = QLabel("Modificadores:")
        lbl_mods.setStyleSheet("color: #c0c0c0; font-size: 11px;")

        self._chk_ctrl  = self._make_mod_btn("Ctrl",  self._init_ctrl)
        self._chk_shift = self._make_mod_btn("Shift", self._init_shift)
        self._chk_alt   = self._make_mod_btn("Alt",   self._init_alt)

        mod_row = QHBoxLayout()
        mod_row.setSpacing(8)
        mod_row.addWidget(self._chk_ctrl)
        mod_row.addWidget(self._chk_shift)
        mod_row.addWidget(self._chk_alt)
        mod_row.addStretch(1)

        lbl_key = QLabel("Tecla base (haz clic en el campo y presiona una tecla):")
        lbl_key.setStyleSheet("color: #c0c0c0; font-size: 11px;")
        lbl_key.setWordWrap(True)

        self._edit = QLineEdit()
        self._edit.setText(self._base_key)
        self._edit.setReadOnly(True)
        self._edit.setAlignment(Qt.AlignCenter)
        self._edit.setPlaceholderText("Haz clic aqui para capturar...")
        self._edit.setCursor(Qt.PointingHandCursor)
        self._edit.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QLineEdit[waiting="true"] { border: 1px solid #0078d4; }
        """)
        self._edit.setFocusPolicy(Qt.NoFocus)
        self._edit.installEventFilter(self)

        lbl_sub = QLabel("Los clics del mouse no se registran como atajo.")
        lbl_sub.setStyleSheet("color: #555555; font-size: 10px;")
        lbl_sub.setAlignment(Qt.AlignCenter)

        btn_ok     = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.setStyleSheet(_STYLE_BTN_SAVE)
        btn_cancel.setStyleSheet(_STYLE_BTN_CANCEL)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_cancel.setCursor(Qt.PointingHandCursor)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)

        layout.addWidget(lbl_mods)
        layout.addLayout(mod_row)
        layout.addWidget(lbl_key)
        layout.addWidget(self._edit)
        layout.addWidget(lbl_sub)
        layout.addLayout(btn_row)

        btn_ok.clicked.connect(self._on_accept)
        btn_cancel.clicked.connect(self.reject)

    def _make_mod_btn(self, label: str, checked: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(28)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #aaaaaa;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 14px;
                font-weight: 600;
            }
            QPushButton:checked {
                background-color: #0078d4;
                color: #ffffff;
                border: 1px solid #0078d4;
            }
            QPushButton:hover { border-color: #0078d4; }
        """)
        return btn

    def eventFilter(self, obj, event) -> bool:
        if obj is self._edit and event.type() == QEvent.MouseButtonPress:
            self._set_waiting(True)
            return True
        return super().eventFilter(obj, event)

    def _set_waiting(self, waiting: bool) -> None:
        self._waiting = waiting
        self._edit.setProperty("waiting", "true" if waiting else "false")
        self._edit.style().unpolish(self._edit)
        self._edit.style().polish(self._edit)
        if waiting:
            self._edit.setPlaceholderText("Presiona una tecla...")
            self._edit.setText("")
        else:
            self._edit.setPlaceholderText("Haz clic aqui para capturar...")

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key_Escape:
            if self._waiting:
                self._set_waiting(False)
                self._edit.setText(self._base_key)
            else:
                self.reject()
            return

        if not self._waiting:
            return
        if key in self._MODIFIER_KEYS:
            return

        key_name = QKeySequence(key).toString().lower().strip()
        for mod in ("ctrl+", "shift+", "alt+", "meta+"):
            key_name = key_name.replace(mod, "")
        key_name = key_name.strip()

        if key_name:
            self._base_key = key_name
            self._edit.setText(key_name)
            self._set_waiting(False)

    def _on_accept(self) -> None:
        parts = []
        if self._chk_ctrl.isChecked():  parts.append("ctrl")
        if self._chk_shift.isChecked(): parts.append("shift")
        if self._chk_alt.isChecked():   parts.append("alt")
        if self._base_key:
            parts.append(self._base_key)
        self._result = "+".join(parts)
        self.accept()

    def get_result(self) -> str:
        return self._result
# (Dependencias/Interacciones: Son componentes auxiliares que se incrustan dentro de PreferencesWindow para manejar el SpinBox personalizado y la captura de teclas.)


# ==========================================================
# BLOQUE: Ventana Principal de Preferencias (UI y Estructura)
# ==========================================================
class PreferencesWindow(QWidget):
    download_model_requested = Signal(str)
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} – Preferencias")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setWindowFlags(Qt.Window)
        self.setMinimumSize(620, 420)
        self.setStyleSheet("background-color: #2a2a2a;")

        self._selection_color: str = get_selection_color()
        self._rainbow_active: bool = self._selection_color == "rainbow"
        self._rainbow_hue: int     = 0
        self._rainbow_timer        = QTimer(self)
        self._rainbow_timer.setInterval(30)
        self._rainbow_timer.timeout.connect(self._tick_rainbow)

        self._sig = _Signals()
        self.closed = self._sig.closed

        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        self.sections = QListWidget()
        self.sections.setFixedWidth(150)
        self.sections.setSpacing(2)
        self.sections.setSelectionMode(QListWidget.SingleSelection)
        self.sections.setFocusPolicy(Qt.NoFocus)
        self.sections.setStyleSheet(_STYLE_SIDEBAR)

        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: #2a2a2a;")
        self.pages.addWidget(self._create_translation_page())  # 0
        self.pages.addWidget(self._create_capture_page())      # 1
        self.pages.addWidget(self._create_appearance_page())   # 2

        self._add_section("Traducción", 0)
        self._add_section("Captura",    1)
        self._add_section("Apariencia", 2)
        self.sections.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sections.setCurrentRow(0)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(_STYLE_SEPARATOR)

        btn_save   = QPushButton("Guardar")
        btn_cancel = QPushButton("Cancelar")
        btn_save.setStyleSheet(_STYLE_BTN_SAVE)
        btn_cancel.setStyleSheet(_STYLE_BTN_CANCEL)
        btn_save.clicked.connect(self._on_save)
        btn_cancel.clicked.connect(self._do_close)

        self.btn_reset = QPushButton("Restablecer")
        self.btn_reset.setStyleSheet(_STYLE_BTN_RESET)
        self.btn_reset.clicked.connect(self._on_reset)
        self.btn_reset.setEnabled(False)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(12, 8, 12, 10)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)

        content = QHBoxLayout()
        content.setContentsMargins(12, 12, 12, 8)
        content.setSpacing(8)
        content.addWidget(self.sections)
        content.addWidget(self.pages, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(content, 1)
        outer.addWidget(sep)
        outer.addLayout(btn_row)

    def _add_section(self, title: str, index: int) -> None:
        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, index)
        self.sections.addItem(item)

    @staticmethod
    def _base_page():
        page   = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        return page, layout

    @staticmethod
    def _make_header(title_text: str, subtitle_text: str):
        title = QLabel(title_text)
        title.setStyleSheet(_STYLE_TITLE)
        subtitle = QLabel(subtitle_text)
        subtitle.setStyleSheet(_STYLE_SUBLABEL)
        subtitle.setWordWrap(True)
        return title, subtitle

    @staticmethod
    def _make_form() -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        form.setSpacing(10)
        form.setHorizontalSpacing(14)
        return form
# (Dependencias/Interacciones: Construye la estructura base. Depende de los bloques de estilo y de los métodos de creación de páginas.)


# ==========================================================
# BLOQUE: Construcción de Páginas (Traducción, Captura, Apariencia)
# ==========================================================
    def _create_translation_page(self) -> QWidget:
        page, layout = self._base_page()
        title, subtitle = self._make_header("Traducción", "Configura los idiomas y el comportamiento del traductor.")
        form = self._make_form()

        self._combo_source = QComboBox()
        self._combo_source.setStyleSheet(_STYLE_LANG_COMBO)
        self._combo_source.setFixedWidth(220)
        for code in TRANSLATION_LANG_CHOICES:
            self._combo_source.addItem(TRANSLATION_LANG_DISPLAY[code], code)

        self._combo_target = QComboBox()
        self._combo_target.setStyleSheet(_STYLE_LANG_COMBO)
        self._combo_target.setFixedWidth(220)
        for code in TRANSLATION_LANG_CHOICES:
            self._combo_target.addItem(TRANSLATION_LANG_DISPLAY[code], code)

        self._chk_cache = QCheckBox("Habilitar caché de traducciones en memoria")
        self._chk_cache.setStyleSheet(_STYLE_LABEL)

        self._prev_source_index = 0
        self._pending_download_code  = None
        self._pending_download_index = None

        def _on_source_changed(new_index: int):
            new_code = self._combo_source.itemData(new_index)
            cur_code = self._combo_source.itemData(self._prev_source_index)

            if new_code == cur_code:
                return

            if OCREngine.is_model_downloaded(new_code):
                self._prev_source_index = new_index
                self._update_reset_btn()
                return

            lang_name = TRANSLATION_LANG_DISPLAY.get(new_code, new_code)
            msg = QMessageBox(self)
            msg.setWindowTitle("Descargar recursos de idioma")
            msg.setText(
                f"El idioma <b>{lang_name}</b> requiere descargar "
                f"un modelo OCR adicional (~10–15 MB).<br><br>"
                f"¿Deseas descargarlo ahora?"
            )
            msg.setIcon(QMessageBox.Question)
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)

            if msg.exec() == QMessageBox.Yes:
                self._pending_download_code  = new_code
                self._pending_download_index = new_index
                self._combo_source.blockSignals(True)
                self._combo_source.setCurrentIndex(self._prev_source_index)
                self._combo_source.blockSignals(False)
                self.download_model_requested.emit(new_code)
            else:
                self._combo_source.blockSignals(True)
                self._combo_source.setCurrentIndex(self._prev_source_index)
                self._combo_source.blockSignals(False)

        self._combo_source.currentIndexChanged.connect(_on_source_changed)

        form.addRow(_lbl("Idioma origen"),  self._combo_source)
        form.addRow(_lbl("Idioma destino"), self._combo_target)
        form.addRow("",                     self._chk_cache)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _create_capture_page(self) -> QWidget:
        page, layout = self._base_page()
        title, subtitle = self._make_header("Captura", "Atajos de teclado para iniciar la captura y traducción.")
        form = self._make_form()

        self.edit_hotkey_main = self._make_hotkey_field()
        self.edit_hotkey_sec1 = self._make_hotkey_field(clearable=True)
        self.edit_hotkey_sec2 = self._make_hotkey_field(clearable=True)

        form.addRow(_lbl("Atajo de captura:"),            self._hotkey_row(self.edit_hotkey_main))
        form.addRow(_lbl("Atajo de captura adicional:"),  self._hotkey_row(self.edit_hotkey_sec1, clearable=True))
        form.addRow(_lbl("Atajo de captura adicional:"),  self._hotkey_row(self.edit_hotkey_sec2, clearable=True))

        hint = QLabel("Haz clic en el campo para asignar una tecla o combinación. Los clics del mouse no se aceptan como atajo.")
        hint.setStyleSheet(_STYLE_SUBLABEL)
        hint.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _make_hotkey_field(self, clearable: bool = False) -> QLineEdit:
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setFixedWidth(200)
        edit.setPlaceholderText("Sin asignar")
        edit.setCursor(Qt.PointingHandCursor)
        edit.setAlignment(Qt.AlignCenter)
        edit.setStyleSheet("""
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 6px;
            }
            QLineEdit:hover { border-color: #0078d4; }
        """)
        edit.installEventFilter(self)
        return edit

    def _hotkey_row(self, edit: QLineEdit, clearable: bool = False) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(edit)

        if clearable:
            btn_clear = QPushButton("✕")
            btn_clear.setFixedSize(24, 24)
            btn_clear.setCursor(Qt.PointingHandCursor)
            btn_clear.setToolTip("Limpiar atajo")
            btn_clear.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a; color: #888888;
                    border: 1px solid #444444; border-radius: 4px; font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #5a2020; color: #ff6666; border-color: #883333;
                }
            """)
            btn_clear.clicked.connect(lambda: (edit.setText(""), self._update_reset_btn()))
            row.addWidget(btn_clear)

        row.addStretch(1)
        return container

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.MouseButtonPress
            and obj in (self.edit_hotkey_main, self.edit_hotkey_sec1, self.edit_hotkey_sec2)
        ):
            self._open_hotkey_dialog(obj)
            return True
        return super().eventFilter(obj, event)

    def _open_hotkey_dialog(self, field: QLineEdit) -> None:
        dlg = _HotkeyDialog(current=field.text(), parent=self)
        if dlg.exec() == QDialog.Accepted:
            field.setText(dlg.get_result())
            self._update_reset_btn()

    def _create_appearance_page(self) -> QWidget:
        page, layout = self._base_page()
        title, subtitle = self._make_header("Apariencia", "Color del área de selección y fuente del texto traducido.")
        form = self._make_form()

        self._btn_color = QPushButton()
        self._btn_color.setStyleSheet(_STYLE_BTN_COLOR)
        self._btn_color.setFixedSize(80, 28)
        self._btn_color.setCursor(Qt.PointingHandCursor)
        self._btn_color.setToolTip("")
        self._btn_color.clicked.connect(self._pick_color)
        self._update_color_btn(self._selection_color)

        color_row = QHBoxLayout()
        color_row.setSpacing(8)
        color_row.addWidget(self._btn_color)
        color_row.addWidget(_lbl_small("color del borde al seleccionar"))

        self.font_combo = QFontComboBox()
        self.font_combo.setFixedWidth(220)
        self.font_combo.setEditable(False)
        self.font_combo.setCursor(Qt.PointingHandCursor)
        self.font_combo.setStyleSheet(_STYLE_FONTCOMBO)
        self.font_combo.blockSignals(True)
        self.font_combo.setCurrentIndex(0)
        self.font_combo.blockSignals(False)

        font_row = QHBoxLayout()
        font_row.setSpacing(8)
        font_row.addWidget(self.font_combo)
        font_row.addStretch(1)

        self.spin_border_width = _StepSpinBox(min_val=1, max_val=10, suffix=" px")
        self.spin_border_width.setRange(1, 10)
        self.spin_border_width.setFixedWidth(82)
        self.spin_border_width.setValue(SELECTION_BORDER_WIDTH)
        self.spin_border_width.setFocusPolicy(Qt.NoFocus)
        self.spin_border_width.valueChanged.connect(self._update_preview)

        color_row.addWidget(self.spin_border_width)
        color_row.addWidget(_lbl_small("grosor del borde"))
        color_row.addStretch(1)

        form.addRow(_lbl("Color de selección:"), color_row)
        form.addRow(_lbl("Fuente del resultado:"), font_row)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addLayout(form)
        layout.addSpacing(12)
        layout.addWidget(self._build_preview())
        layout.addStretch(1)
        return page

    def _build_preview(self) -> QWidget:
        container = QWidget()
        container.setStyleSheet(
            "QWidget#preview_container {"
            "  background-color: #1e1e1e;"
            "  border: 1px solid #444444;"
            "  border-radius: 6px;"
            "}"
        )
        container.setObjectName("preview_container")
        container.setFixedHeight(90)

        v = QVBoxLayout(container)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(6)

        lbl_title = QLabel("Vista previa")
        lbl_title.setStyleSheet("color: #888888; font-size: 14px;")

        self._preview_frame = QFrame()
        self._preview_frame.setFrameShape(QFrame.Box)
        self._preview_frame.setFixedHeight(44)

        self._preview_label = QLabel("Texto traducido de ejemplo — Translation Preview")
        self._preview_label.setAlignment(Qt.AlignCenter)

        inner = QVBoxLayout(self._preview_frame)
        inner.setContentsMargins(6, 2, 6, 2)
        inner.addWidget(self._preview_label)

        v.addWidget(lbl_title)
        v.addWidget(self._preview_frame)

        self.font_combo.currentFontChanged.connect(self._update_preview)
        self._update_preview()
        return container

    def _update_preview(self, *_) -> None:
        family = self.font_combo.currentFont().family()
        size   = 14
        color  = self._selection_color if self._selection_color != "rainbow" else "#00aaff"
        width  = self.spin_border_width.value()

        self._preview_frame.setStyleSheet(
            f"QFrame {{ border: {width}px solid {color}; border-radius: 4px; background-color: #2a2a2a; }}"
        )
        self._preview_label.setStyleSheet(
            f"color: #ffffff; font-family: '{family}'; font-size: {size}pt; border: none;"
        )
# (Dependencias/Interacciones: Depende de los estilos, de 'config' para los defaults y de 'preferences' para los getters/setters. Se comunica con 'core.ocr_engine' para comprobar si un modelo ya está descargado al cambiar el idioma origen.)


# ==========================================================
# BLOQUE: Color Picker y Lógica Arcoíris
# ==========================================================
    def _pick_color(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Color de selección")
        dlg.setStyleSheet("background-color: #2a2a2a; color: #ffffff;")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        picker = QColorDialog(dlg)
        picker.setWindowFlags(Qt.Widget)
        picker.setOption(QColorDialog.NoButtons)
        initial = QColor(self._selection_color) if self._selection_color != "rainbow" else QColor("#01abff")
        picker.setCurrentColor(initial)

        class _HoverFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Enter:
                    obj.setCursor(Qt.PointingHandCursor)
                return False

        _hover_filter = _HoverFilter(dlg)

        for child in picker.findChildren(QAbstractButton):
            child.setCursor(Qt.PointingHandCursor)
            if not child.styleSheet():
                child.setStyleSheet(
                    "QAbstractButton { padding: 2px; }"
                    "QAbstractButton:hover { border: 2px solid #0078d4; padding: 0px; }"
                )

        for child in picker.findChildren(QWidget):
            if not isinstance(child, QAbstractButton):
                child.installEventFilter(_hover_filter)

        btn_rgb = QPushButton("RGB — +FPS")
        btn_rgb.setMinimumHeight(36)
        btn_rgb.setCursor(Qt.PointingHandCursor)

        _rgb_active = [self._rainbow_active]

        def _apply_rgb_style():
            btn_rgb.setStyleSheet(
                PreferencesWindow._rainbow_btn_style_active() if _rgb_active[0]
                else PreferencesWindow._rainbow_btn_style()
            )

        _apply_rgb_style()

        def _toggle_rgb():
            _rgb_active[0] = not _rgb_active[0]
            _apply_rgb_style()

        btn_rgb.pressed.connect(_toggle_rgb)

        picker_layout = picker.layout()
        inserted = False
        if picker_layout:
            for i in range(picker_layout.count()):
                item = picker_layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    if isinstance(w, QPushButton) and "screen" in w.text().lower():
                        picker_layout.insertWidget(i, btn_rgb)
                        inserted = True
                        break
        if not inserted:
            layout.addWidget(picker)
            layout.addWidget(btn_rgb)
        else:
            layout.addWidget(picker)

        _user_interacted = [False]

        def _on_color_changed(_):
            if _user_interacted[0]:
                _rgb_active[0] = False
                _apply_rgb_style()

        picker.currentColorChanged.connect(_on_color_changed)
        QTimer.singleShot(50, lambda: _user_interacted.__setitem__(0, True))

        btn_ok     = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        btn_ok.setStyleSheet(_STYLE_BTN_SAVE)
        btn_cancel.setStyleSheet(_STYLE_BTN_CANCEL)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_cancel.setCursor(Qt.PointingHandCursor)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        def _on_ok():
            if _rgb_active[0]:
                self._rainbow_active  = True
                self._selection_color = "rainbow"
                self._rainbow_timer.start()
            else:
                self._rainbow_active = False
                self._rainbow_timer.stop()
                self._rainbow_hue = 0
                color = picker.currentColor()
                if color.isValid():
                    self._selection_color = color.name()
                self._update_color_btn(self._selection_color)
            self._update_reset_btn()
            QTimer.singleShot(0, self._update_preview)
            dlg.accept()

        btn_ok.clicked.connect(_on_ok)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def _update_color_btn(self, hex_color: str) -> None:
        if hex_color == "rainbow":
            self._btn_color.setStyleSheet(
                "QPushButton {"
                "  background-color: qlineargradient("
                "    x1:0, y1:0, x2:1, y2:0,"
                "    stop:0 #ff0000, stop:0.17 #ffaa00,"
                "    stop:0.33 #ffff00, stop:0.5 #00ff00,"
                "    stop:0.67 #00aaff, stop:0.83 #8800ff,"
                "    stop:1 #ff0000);"
                "  border: 2px solid #555555; border-radius: 4px;"
                "  min-width: 64px; min-height: 26px;"
                "}"
                "QPushButton:hover { border-color: #0078d4; }"
            )
        else:
            self._btn_color.setStyleSheet(
                f"QPushButton {{ background-color: {hex_color}; border: 2px solid #555555; "
                f"border-radius: 4px; min-width: 64px; min-height: 26px; }}"
                f"QPushButton:hover {{ border-color: #0078d4; }}"
            )
        self._btn_color.setToolTip("")

    def _tick_rainbow(self) -> None:
        self._rainbow_hue = (self._rainbow_hue + 3) % 360
        color = QColor.fromHsv(self._rainbow_hue, 255, 255)
        self._selection_color = "rainbow"
        self._update_color_btn(color.name())
        if hasattr(self, "_preview_frame"):
            width = self.spin_border_width.value()
            self._preview_frame.setStyleSheet(
                f"QFrame {{ border: {width}px solid {color.name()}; border-radius: 4px; background-color: #2a2a2a; }}"
            )

    @staticmethod
    def _rainbow_btn_style() -> str:
        return (
            "QPushButton {"
            "  background-color: qlineargradient("
            "    x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 #ff0000, stop:0.17 #ffaa00,"
            "    stop:0.33 #ffff00, stop:0.5 #00ff00,"
            "    stop:0.67 #00aaff, stop:0.83 #8800ff,"
            "    stop:1 #ff0000);"
            "  color: #000000; font-weight: 700;"
            "  border: 2px solid #555555; border-radius: 4px;"
            "  min-width: 40px; min-height: 26px;"
            "}"
            "QPushButton:checked { border: 2px solid #ffffff; }"
            "QPushButton:hover   { border: 2px solid #cccccc; }"
        )
        
    @staticmethod
    def _rainbow_btn_style_active() -> str:
        return (
            "QPushButton {"
            "  background-color: qlineargradient("
            "    x1:0, y1:0, x2:1, y2:0,"
            "    stop:0 #ff0000, stop:0.17 #ffaa00,"
            "    stop:0.33 #ffff00, stop:0.5 #00ff00,"
            "    stop:0.67 #00aaff, stop:0.83 #8800ff,"
            "    stop:1 #ff0000);"
            "  color: #000000; font-weight: 700;"
            "  border: 2px solid #ffffff;"
            "  border-radius: 4px;"
            "  min-width: 40px; min-height: 26px;"
            "}"
            "QPushButton:hover { border: 2px solid #cccccc; }"
        )
# (Dependencias/Interacciones: Maneja la ventana emergente de selección de color. Se conecta con la UI de Apariencia para actualizar la vista previa dinámicamente.)


# ==========================================================
# BLOQUE: Carga, Guardado y Comunicación de Estado
# ==========================================================
    def _load_values(self) -> None:
        # Traducción
        source_code = get_translation_source()
        idx = self._combo_source.findData(source_code)
        self._combo_source.blockSignals(True)
        self._combo_source.setCurrentIndex(idx if idx >= 0 else 0)
        self._prev_source_index = self._combo_source.currentIndex()
        self._combo_source.blockSignals(False)

        target_code = get_translation_target()
        idx = self._combo_target.findData(target_code)
        self._combo_target.blockSignals(True)
        self._combo_target.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo_target.blockSignals(False)

        self._chk_cache.setChecked(get_translation_cache_enabled())

        # Captura
        hotkeys = get_capture_hotkeys()
        self.edit_hotkey_main.setText(hotkeys[0] if len(hotkeys) > 0 else CAPTURE_HOTKEYS[0])
        self.edit_hotkey_sec1.setText(get_capture_secondary_1())
        self.edit_hotkey_sec2.setText(get_capture_secondary_2())

        # Apariencia
        self._selection_color = get_selection_color()

        _family = get_result_font_family()
        self.font_combo.blockSignals(True)
        _idx = self.font_combo.findText(_family, Qt.MatchFixedString)
        if _idx >= 0:
            self.font_combo.setCurrentIndex(_idx)
        else:
            self.font_combo.setCurrentFont(QFont(_family))
        self.font_combo.blockSignals(False)

        self.spin_border_width.setValue(get_selection_border_width())

        if self._selection_color == "rainbow":
            self._rainbow_active = True
            self._update_color_btn("rainbow")
            self._rainbow_timer.start()
        else:
            self._rainbow_active = False
            self._rainbow_timer.stop()
            self._update_color_btn(self._selection_color)

        # Conectar cambios al checker DESPUÉS de cargar valores
        self._combo_source.currentIndexChanged.connect(self._update_reset_btn)
        self._combo_target.currentIndexChanged.connect(self._update_reset_btn)
        self._chk_cache.stateChanged.connect(self._update_reset_btn)
        self.font_combo.currentFontChanged.connect(self._update_reset_btn)
        self.spin_border_width.valueChanged.connect(self._update_reset_btn)

        self._update_preview()
        self._update_reset_btn()

    def _on_save(self) -> None:
        set_translation_source(self._combo_source.currentData() or TRANSLATION_SOURCE)
        set_translation_target(self._combo_target.currentData() or TRANSLATION_TARGET)
        set_translation_cache_enabled(self._chk_cache.isChecked())

        main_hk = self.edit_hotkey_main.text().strip() or CAPTURE_HOTKEYS[0]
        set_capture_hotkeys([main_hk])
        set_capture_secondary_1(self.edit_hotkey_sec1.text().strip())
        set_capture_secondary_2(self.edit_hotkey_sec2.text().strip())

        set_selection_color(self._selection_color)
        set_result_font_family(self.font_combo.currentFont().family())
        set_selection_border_width(self.spin_border_width.value())

        print("[PREF] Preferencias guardadas correctamente.")
        self._do_close()

    def _on_reset(self) -> None:
        idx = self._combo_source.findData(TRANSLATION_SOURCE)
        self._combo_source.blockSignals(True)
        self._combo_source.setCurrentIndex(idx if idx >= 0 else 0)
        self._prev_source_index = self._combo_source.currentIndex()
        self._combo_source.blockSignals(False)

        idx = self._combo_target.findData(TRANSLATION_TARGET)
        self._combo_target.blockSignals(True)
        self._combo_target.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo_target.blockSignals(False)

        self.edit_hotkey_main.setText(CAPTURE_HOTKEYS[0])
        self.edit_hotkey_sec1.setText(CAPTURE_SECONDARY_1)
        self.edit_hotkey_sec2.setText(CAPTURE_SECONDARY_2)

        self._rainbow_timer.stop()
        self._rainbow_active = False
        self._selection_color = SELECTION_COLOR
        self._update_color_btn(self._selection_color)

        self.font_combo.setCurrentFont(QFont(RESULT_FONT_FAMILY))
        self.spin_border_width.setValue(SELECTION_BORDER_WIDTH)
        self._update_reset_btn()
        self._update_preview()
        print("[PREF] Valores restablecidos a defaults (no guardado aún).")

    def _update_reset_btn(self, *_) -> None:
        changed = any([
            self._combo_source.currentData() != TRANSLATION_SOURCE,
            self._combo_target.currentData() != TRANSLATION_TARGET,
            self._chk_cache.isChecked()             != TRANSLATION_CACHE_ENABLED,
            self.edit_hotkey_main.text().strip()   != CAPTURE_HOTKEYS[0],
            self.edit_hotkey_sec1.text().strip()   != CAPTURE_SECONDARY_1,
            self.edit_hotkey_sec2.text().strip()   != CAPTURE_SECONDARY_2,
            self._selection_color.lower()          != SELECTION_COLOR.lower(),
            self.font_combo.currentFont().family() != RESULT_FONT_FAMILY,
            self.spin_border_width.value()         != SELECTION_BORDER_WIDTH,
        ])
        self.btn_reset.setEnabled(changed)

    def on_model_download_finished(self, lang_code: str) -> None:
        if lang_code != self._pending_download_code:
            return
        self._combo_source.blockSignals(True)
        self._combo_source.setCurrentIndex(self._pending_download_index)
        self._prev_source_index = self._pending_download_index
        self._combo_source.blockSignals(False)
        self._pending_download_code  = None
        self._pending_download_index = None
        self._update_reset_btn()

    def on_model_download_failed(self, lang_code: str) -> None:
        self._pending_download_code  = None
        self._pending_download_index = None
        QMessageBox.warning(
            self, "Error de descarga",
            f"No se pudo descargar el modelo para '{lang_code}'.\nVerifica tu conexión e inténtalo de nuevo.",
        )

    def _do_close(self) -> None:
        self.hide()
        self._sig.closed.emit()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        QTimer.singleShot(0, self._do_close)


# ==========================================================
# BLOQUE: Helpers de Etiquetas
# ==========================================================
def _lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_STYLE_LABEL)
    return lbl

def _lbl_small(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_STYLE_SUBLABEL)
    return lbl
# (Dependencias/Interacciones: Depende fuertemente de 'preferences' y 'config'. Se comunica con 'main.py' mediante la señal 'download_model_requested' y 'closed' para avisar que debe recargar hotkeys.)