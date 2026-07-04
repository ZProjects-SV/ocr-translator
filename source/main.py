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
# OCR Translator
# Copyright (C) 2026 ZProjects
import os
os.environ["PYSTRAY_BACKEND"] = "win32"
import sys
import re
import threading
import gc

if sys.platform == "win32":
    import subprocess
    _real_Popen_init = subprocess.Popen.__init__

    def _silent_popen_init(self, args, **kwargs):
        if kwargs.get("startupinfo") is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0
            kwargs["startupinfo"] = si
        _real_Popen_init(self, args, **kwargs)

    subprocess.Popen.__init__ = _silent_popen_init

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel
from PySide6.QtGui import QIcon
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from ui.splash_screen import SplashScreen

from config import (
    APP_NAME,
    APP_VERSION,
    ABOUT_TEXT,
    APP_USER_MODEL_ID,
    ABOUT_TITLE,
    TRAY_NAME,
    TRAY_MENU_PREFERENCES,
    TRAY_MENU_ABOUT,
    TRAY_MENU_QUIT,
)
from preferences import get_capture_hotkeys, get_capture_secondary_1, get_capture_secondary_2

from core.ocr_engine import OCREngine
from core.translator import Translator
from core.screen_capture import ScreenCapture
from core.loading_window import UnifiedResultWindow
from ui.selection_window import capture_selection
from ui.preferences_window import PreferencesWindow

from concurrent.futures import ThreadPoolExecutor

from PIL import Image
import pystray
import keyboard
import ctypes
import tempfile
import msvcrt

hotkeys = get_capture_hotkeys()
hotkey_text = ", ".join(hotkeys)


# ==========================================================
# BLOQUE: Interceptación de Progreso (PaddleOCR -> Splash)
# ==========================================================
class ProgressCapture:
    def __init__(self, splash, status_text, prog_start, prog_end):
        self.splash = splash
        self.status_text = status_text
        self.prog_start = prog_start
        self.prog_end = prog_end
        self._original = sys.stderr

    def write(self, text):
        self._original.write(text)
        try:
            match = re.search(r'(\d+)%\|', text)
            if match:
                pct = int(match.group(1)) / 100.0
                mapped = self.prog_start + (self.prog_end - self.prog_start) * pct
                name_match = re.search(r'(\w+\.tar|\w+\.zip|\w+_infer)', text)
                filename = f" — {name_match.group(1)}" if name_match else ""
                self.splash.set_status(f"{self.status_text}{filename} ({int(pct*100)}%)", mapped)
        except Exception:
            pass

    def flush(self):
        self._original.flush()

    def __enter__(self):
        sys.stderr = self
        return self

    def __exit__(self, *args):
        sys.stderr = self._original


class _Signals(QObject):
    area_selected = Signal(int, int, int, int, object)
    start_capture_s = Signal()
    open_preferences = Signal()
    open_about = Signal()
    model_download_finished = Signal(str)
    model_download_failed = Signal(str)

    def __init__(self):
        super().__init__()


_LOCK_FILE_PATH = os.path.join(tempfile.gettempdir(), "ocr_translator_instance.lock")
_lock_file_handle = None


def acquire_single_instance_lock():
    global _lock_file_handle
    try:
        _lock_file_handle = open(_LOCK_FILE_PATH, "w")
        msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        _lock_file_handle.write(str(os.getpid()))
        _lock_file_handle.flush()
        return True
    except (IOError, OSError):
        if _lock_file_handle:
            _lock_file_handle.close()
            _lock_file_handle = None
        return False


def release_single_instance_lock():
    global _lock_file_handle
    if _lock_file_handle:
        try:
            msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
            _lock_file_handle.close()
        except Exception:
            pass
        _lock_file_handle = None
    try:
        os.remove(_LOCK_FILE_PATH)
    except Exception:
        pass


class OCRTranslatorApp:

    def __init__(self):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass

        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self._signals = _Signals()
        self._signals.area_selected.connect(self._run_result_window)
        self._signals.start_capture_s.connect(self._run_selection_window)
        self._signals.open_preferences.connect(self._run_preferences_window)
        self._signals.open_about.connect(self._run_about_window)
        self._signals.model_download_finished.connect(self._on_model_download_finished)
        self._signals.model_download_failed.connect(self._on_model_download_failed)

        icon_path = self.get_resource_path("resources/icon.ico")
        if os.path.exists(icon_path):
            self.qt_app.setWindowIcon(QIcon(icon_path))

        self.ocr_engine = None
        self.translator = None
        self.screen_capture = None
        self.icon = None
        self.running = True
        self.capturing = False
        self._active_result = None
        self._prefs_window = None
        self._about_window = None
        self._ocr_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr_worker")

    def run(self):
        splash = SplashScreen()
        splash.show()
        self.qt_app.processEvents()
        self._install_keyboard_hook()

        def _worker():
            try:
                self._load_with_splash(splash)
            except Exception as e:
                print(f"[ERROR] {e}")
                splash.close()

        threading.Thread(target=_worker, daemon=True).start()
        self.qt_app.exec()

    # ==========================================================
    # BLOQUE: Carga Asíncrona y Calentamiento de Motores
    # ==========================================================
    def _load_with_splash(self, splash: SplashScreen):
        frames_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "resources", "splash_frames"
        )
        if not os.path.isdir(frames_dir):
            splash.set_status("Preparando recursos...", 0.05)
            icon_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "resources", "icon.ico"
            )
            if os.path.exists(icon_path):
                SplashScreen.prebuild_frames(icon_path, frames_dir)

        models_dir = os.path.join(os.path.expanduser("~"), ".paddleocr")
        models_exist = os.path.isdir(models_dir) and len(os.listdir(models_dir)) > 0

        if not models_exist:
            splash.set_download_mode()
            splash.set_status("Descargando modelos... (primera vez)", 0.10)
            with ProgressCapture(splash, "Descargando", 0.10, 0.70):
                self.ocr_engine = OCREngine()
        else:
            splash.set_status("Cargando motor OCR...", 0.20)
            with ProgressCapture(splash, "Cargando", 0.20, 0.60):
                self.ocr_engine = OCREngine()

        splash.set_status("Calentando modelo...", 0.75)
        self._warmup_ocr()

        splash.set_status("Iniciando traductor...", 0.85)
        self.translator = Translator()
        self.screen_capture = ScreenCapture(self.ocr_engine, self.translator)

        self.setup_tray_icon()
        splash.set_status("¡Listo!", APP_VERSION)

        print("[*] Presiona", hotkey_text, "para capturar y traducir")

        threading.Thread(target=self._run_tray, daemon=True).start()
        splash.close()

    def _run_tray(self):
        try:
            self.icon.run()
        except Exception as e:
            print(f"[ERROR TRAY] {e}")

    def _warmup_ocr(self):
        try:
            dummy = Image.new("RGB", (100, 30), color=(255, 255, 255))
            self.ocr_engine.extract_text(dummy)
            del dummy
        except Exception:
            pass

    # ==========================================================
    # BLOQUE: Atajos de Teclado (Hooks Globales)
    # ==========================================================
    def _install_keyboard_hook(self):
        self._register_hotkeys()

    def _register_hotkeys(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        hotkeys_list = []
        try:
            hotkeys_list.extend(get_capture_hotkeys())
        except Exception:
            pass

        for getter in (get_capture_secondary_1, get_capture_secondary_2):
            try:
                val = getter()
                if val and val.strip():
                    hotkeys_list.append(val.strip())
            except Exception:
                pass

        registered = []
        for hotkey in hotkeys_list:
            try:
                keyboard.add_hotkey(hotkey, self.start_capture)
                registered.append(hotkey)
            except Exception:
                pass

        print("[OK] Hotkeys registrados:", ", ".join(registered) if registered else "ninguno")

    # ==========================================================
    # BLOQUE: Flujo de Captura y Procesamiento de Resultados
    # ==========================================================
    def start_capture(self):
        if not self.running or self.capturing or self._prefs_window is not None:
            return
        self.capturing = True
        self._signals.start_capture_s.emit()

    def _run_selection_window(self):
        try:
            capture_selection(self.on_area_selected)
        except Exception as e:
            print(f"[ERROR SelectionWindow] {type(e).__name__}: {e}")
        finally:
            self.capturing = False

    def on_area_selected(self, x1, y1, x2, y2, cropped_image):
        if cropped_image.width < 10 or cropped_image.height < 10:
            try:
                cropped_image.close()
            except Exception:
                pass
            return
        self._signals.area_selected.emit(x1, y1, x2, y2, cropped_image)

    def _run_result_window(self, x1, y1, x2, y2, cropped_image):
        if self._active_result and not self._active_result.is_closed:
            self._active_result.close()
            self._active_result = None

        result_window = UnifiedResultWindow(x1, y1, x2, y2, margin=1)
        self._active_result = result_window
        result_window.show_loading()

        def process():
            try:
                result_window.update_status("Extrayendo texto...")
                original_text, blocks = self.ocr_engine.extract_text_with_boxes(cropped_image, save_debug=False)

                if not original_text:
                    result_window.update_status("No se detectó texto")
                    result_window.close_after(2000)
                    return

                original_text = '\n'.join(
                    line for line in original_text.split('\n') if line.strip()
                )
                result_window.update_status(f"Traduciendo ({len(original_text)} caracteres)...")
                translated_text = self.translator.translate(original_text)
                result_window.show_result(translated_text, cropped_image, blocks)

            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {e}")
                try:
                    cropped_image.close()
                except Exception:
                    pass
                result_window.close_after(3000)
            finally:
                gc.collect()

        self.capturing = False
        self._ocr_executor.submit(process)
        result_window.run()

    def on_quit(self, icon, item):
        self.running = False
        try:
            if self.ocr_engine:
                self.ocr_engine.release_engine()
        except Exception:
            pass

        def _force_exit():
            import time
            time.sleep(1)
            os._exit(0)

        threading.Thread(target=_force_exit, daemon=True).start()
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        try:
            icon.stop()
        except Exception:
            pass
        QTimer.singleShot(100, lambda: os._exit(0))

    def on_capture(self, icon, item):
        self.start_capture()

    def on_about(self, icon, item):
        self._signals.open_about.emit()

    def on_preferences(self, icon, item):
        if self.capturing:
            self.capturing = False
        self._signals.open_preferences.emit()

    def setup_tray_icon(self):
        image = self._create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem(f"Capturar y Traducir {hotkey_text}", self.on_capture, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(TRAY_MENU_PREFERENCES, self.on_preferences),
            pystray.MenuItem(TRAY_MENU_ABOUT, self.on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(TRAY_MENU_QUIT, self.on_quit),
        )
        self.icon = pystray.Icon(TRAY_NAME, image, f"OCR Translator - {hotkey_text}", menu)

    def _create_tray_image(self):
        icon_path = self.get_resource_path('resources/icon.ico')
        if os.path.exists(icon_path):
            try:
                return Image.open(icon_path).resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        from PIL import ImageDraw
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([4, 4, 60, 60], fill=(0, 120, 212, 255))
        draw.text((22, 18), "T", fill=(255, 255, 255, 255))
        return image

    # ==========================================================
    # BLOQUE: Diálogos (Preferencias, Acerca de, y Descarga de Modelos)
    # ==========================================================
    def _run_about_window(self):
        if self._about_window is not None:
            try:
                if self._about_window.isVisible():
                    self._about_window.raise_()
                    self._about_window.activateWindow()
                    return
            except Exception:
                self._about_window = None

        dlg = QDialog()
        dlg.setWindowTitle(ABOUT_TITLE)
        dlg.setAttribute(Qt.WA_DeleteOnClose, True)
        dlg.setAttribute(Qt.WA_QuitOnClose, False)
        dlg.setWindowFlags(Qt.Window)
        dlg.setMinimumWidth(320)

        layout = QVBoxLayout(dlg)
        label = QLabel(ABOUT_TEXT)
        label.setWordWrap(True)
        layout.addWidget(label)

        dlg.destroyed.connect(lambda: setattr(self, '_about_window', None))
        self._about_window = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _run_preferences_window(self):
        if self._prefs_window is not None:
            try:
                if self._prefs_window.isVisible():
                    self._prefs_window.raise_()
                    self._prefs_window.activateWindow()
                    return
            except Exception:
                self._prefs_window = None

        win = PreferencesWindow()

        def _on_closed():
            self._prefs_window = None
            try:
                self._signals.model_download_finished.disconnect(win.on_model_download_finished)
                self._signals.model_download_failed.disconnect(win.on_model_download_failed)
            except RuntimeError:
                pass
            try:
                self._register_hotkeys()
            except Exception:
                pass

        win.closed.connect(_on_closed)
        win.download_model_requested.connect(self._download_model_with_splash)
        self._signals.model_download_finished.connect(win.on_model_download_finished)
        self._signals.model_download_failed.connect(win.on_model_download_failed)

        win.show()
        win.raise_()
        win.activateWindow()
        self._prefs_window = win

    def _download_model_with_splash(self, new_lang: str):
        splash = SplashScreen()
        splash.show()
        self.qt_app.processEvents()

        def _worker():
            try:
                splash.set_download_mode()
                splash.set_status(f"Descargando modelo '{new_lang}'...", 0.10)
                with ProgressCapture(splash, "Descargando", 0.10, 0.90):
                    self.ocr_engine._init_engine(new_lang)
                splash.set_status("¡Modelo listo!", 1.0)
                import time
                time.sleep(0.6)
                self._signals.model_download_finished.emit(new_lang)
            except Exception as e:
                print(f"[ERROR] Descarga de modelo fallida: {e}")
                self._signals.model_download_failed.emit(new_lang)
            finally:
                splash.close()

        threading.Thread(target=_worker, daemon=True).start()

    def _on_model_download_finished(self, lang: str):
        try:
            self._warmup_ocr()
        except Exception as e:
            print(f"[ERROR] No se pudo calentar el OCR engine: {e}")

    def _on_model_download_failed(self, lang: str):
        QMessageBox.warning(None, "Error de descarga",
            f"No se pudo descargar el modelo para '{lang}'.\nVerifica tu conexión e inténtalo de nuevo.")

    def get_resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    if not acquire_single_instance_lock():
        sys.exit(0)
    try:
        app = OCRTranslatorApp()
        app.run()
    finally:
        release_single_instance_lock()