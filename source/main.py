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
import os
os.environ["PYSTRAY_BACKEND"] = "win32"
import sys
import re
import threading

if sys.platform == "win32":
    import subprocess
    _real_Popen_init = subprocess.Popen.__init__

    def _silent_popen_init(self, args, **kwargs):
        # Si ya viene con startupinfo propio, no tocarlo|
        if kwargs.get("startupinfo") is None:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            kwargs["startupinfo"] = si
        _real_Popen_init(self, args, **kwargs)

    subprocess.Popen.__init__ = _silent_popen_init
    
    
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
from ui.selection_window import SelectionWindow
from ui.preferences_window import PreferencesWindow

from PIL import Image
import pystray
import keyboard
import ctypes
import tempfile
import msvcrt

# Variables globales para texto de hotkeys (usado en tooltips y menús)
hotkeys = get_capture_hotkeys()
hotkey_text = ", ".join(hotkeys)


# ==========================================================
# BLOQUE: Interceptación de Progreso (PaddleOCR -> Splash)
# ==========================================================
class ProgressCapture:
    """Intercepta la salida de tqdm de PaddleOCR y la redirige a la splash."""

    def __init__(self, splash, status_text: str, prog_start: float, prog_end: float):
        self.splash      = splash
        self.status_text = status_text
        self.prog_start  = prog_start
        self.prog_end    = prog_end
        self._original   = sys.stderr

    def write(self, text):
        self._original.write(text)
        try:
            match = re.search(r'(\d+)%\|', text)
            if match:
                pct        = int(match.group(1)) / 100.0
                mapped     = self.prog_start + (self.prog_end - self.prog_start) * pct
                name_match = re.search(r'(\w+\.tar|\w+\.zip|\w+_infer)', text)
                filename   = f" — {name_match.group(1)}" if name_match else ""
                self.splash.set_status(
                    f"{self.status_text}{filename} ({int(pct*100)}%)", mapped
                )
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
    area_selected           = Signal(int, int, int, int, object)
    start_capture_s         = Signal()
    open_preferences        = Signal()
    open_about              = Signal()
    model_download_finished = Signal(str)
    model_download_failed   = Signal(str)

    def __init__(self):
        super().__init__()
        print("[PREF] _Signals inicializado (area_selected, start_capture_s, open_preferences creadas)")

_LOCK_FILE_PATH = os.path.join(tempfile.gettempdir(), "ocr_translator_instance.lock")
_lock_file_handle = None

def acquire_single_instance_lock() -> bool:
    """
    Intenta adquirir un file lock exclusivo.
    Retorna True si esta es la primera instancia, False si ya hay otra corriendo.
    """
    global _lock_file_handle
    try:
        _lock_file_handle = open(_LOCK_FILE_PATH, "w")
        msvcrt.locking(_lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
        _lock_file_handle.write(str(os.getpid()))
        _lock_file_handle.flush()
        return True
    except (IOError, OSError):
        # Ya existe una instancia con el lock
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

# ==========================================================
# BLOQUE: Aplicación Principal (Inicialización y Ejecución)
# ==========================================================
class OCRTranslatorApp:
    """Aplicación principal de OCR + Traductor con System Tray"""

    def __init__(self):
        # Asignar App User Model ID para icono correcto en barra de tareas
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass

        # Crear / obtener QApplication ANTES de usarla
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

        self.ocr_engine     = None
        self.translator     = None
        self.screen_capture = None
        self.icon           = None
        self.running        = True
        self.capturing      = False
        self._active_result = None
        self._prefs_window  = None
        self._about_window  = None

    def run(self):
        # Mostrar splash PRIMERO, antes de cualquier otra cosa
        splash = SplashScreen()
        splash.show()
        self.qt_app.processEvents()
        self.qt_app.processEvents()

        # Ahora sí el resto
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

        models_dir   = os.path.join(os.path.expanduser("~"), ".paddleocr")
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
        self.translator     = Translator()
        self.screen_capture = ScreenCapture(self.ocr_engine, self.translator)

        self.setup_tray_icon()
        splash.set_status("¡Listo!", APP_VERSION)

        print("=" * 60)
        print("OCR + TRADUCTOR INICIADO")
        print("=" * 60)
        print("[*] Presiona ", hotkey_text, " para capturar y traducir")
        print("=" * 60)

        threading.Thread(target=self._run_tray, daemon=False).start()
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
            print("[INFO] Modelo OCR calentado")
        except Exception:
            pass

    # ==========================================================
    # BLOQUE: Atajos de Teclado (Hooks Globales)
    # ==========================================================
    def _install_keyboard_hook(self):
        self._register_hotkeys()  # directo, sin tkinter ni hilo extra

    def _register_hotkeys(self):
        """Limpia los hotkeys anteriores y registra los actuales desde preferences."""
        try:
            keyboard.unhook_all_hotkeys()
        except Exception as e:
            print(f"[WARN] No se pudieron limpiar hotkeys anteriores: {e}")

        hotkeys_list = []
        try:
            hotkeys_list.extend(get_capture_hotkeys())
        except Exception as e:
            print(f"[WARN] No se pudo leer hotkey principal: {e}")

        for getter in (get_capture_secondary_1, get_capture_secondary_2):
            try:
                val = getter()
                if val and val.strip():
                    hotkeys_list.append(val.strip())
            except Exception as e:
                print(f"[WARN] No se pudo leer hotkey secundario: {e}")

        registered = []
        for hotkey in hotkeys_list:
            try:
                keyboard.add_hotkey(hotkey, self.start_capture)
                registered.append(hotkey)
            except Exception as e:
                print(f"[WARN] No se pudo registrar hotkey '{hotkey}': {e}")

        print("[OK] Hotkeys registrados:", ", ".join(registered) if registered else "ninguno")

    # ==========================================================
    # BLOQUE: Flujo de Captura y Procesamiento de Resultados
    # ==========================================================
    def start_capture(self):
        if not self.running:
            return
        if self.capturing:
            print("[WARN] Ya hay una captura en proceso, ignorando...")
            return

        self.capturing = True
        print("[*] Iniciando captura...")
        self._signals.start_capture_s.emit()

    def _run_selection_window(self):
        try:
            win = SelectionWindow(self.on_area_selected)
            win.show()  # bloquea si tiene QEventLoop interno
        except Exception as e:
            print(f"[ERROR SelectionWindow] {type(e).__name__}: {e}")
        finally:
            self.capturing = False

    def on_area_selected(self, x1, y1, x2, y2, cropped_image):
        if cropped_image.width < 10 or cropped_image.height < 10:
            print("[WARN] Área muy pequeña")
            return

        print(f"[*] Área seleccionada: ({x1},{y1}) -> ({x2},{y2})")
        QTimer.singleShot(
            50,
            lambda: self._signals.area_selected.emit(x1, y1, x2, y2, cropped_image),
        )

    def _run_result_window(self, x1, y1, x2, y2, cropped_image):
        # Si ya hay una ventana activa, cerrarla antes de abrir nueva
        if self._active_result and not self._active_result.is_closed:
            self._active_result.close()

        # MARGEN_EXTERNO: El que le sumamos en SelectionWindow para no cortar el borde
        MARGEN_EXTERNO = 1 
        result_window = UnifiedResultWindow(x1, y1, x2, y2, margin=MARGEN_EXTERNO)  
        self._active_result = result_window
        result_window.show_loading()

        def process():
            try:
                result_window.update_status("Extrayendo texto...")
                original_text, blocks = self.ocr_engine.extract_text_with_boxes(cropped_image)

                if not original_text:
                    print("[DEBUG] No hay texto, cerrando...")
                    result_window.update_status("No se detectó texto")
                    result_window.close_after(2000)
                    return

                original_text = '\n'.join(
                    line for line in original_text.split('\n') if line.strip()
                )
                result_window.update_status(
                    f"Traduciendo ({len(original_text)} caracteres)..."
                )
                translated_text = self.translator.translate(original_text)
                try:
                    print("[OK] Traducción completada")
                except UnicodeEncodeError:
                    print("[OK] Traduccion completada")
                
                result_window.show_result(translated_text, cropped_image, blocks)

            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {e}")
                result_window.close_after(3000)

        self.capturing = False
        threading.Thread(target=process, daemon=True).start()
        result_window.run()

    # ==========================================================
    # BLOQUE: System Tray (Bandeja del Sistema)
    # ==========================================================
    def on_quit(self, icon, item):
        print("[PREF] on_quit llamado desde tray")
        self.running = False
        
        # Primero forzar salida en hilo separado por si icon.stop() bloquea
        def _force_exit():
            import time
            time.sleep(1)
            os._exit(0)
        
        threading.Thread(target=_force_exit, daemon=True).start()
        
        try:
            keyboard.unhook_all_hotkeys()
        except:
            pass
        
        try:
            if hasattr(self, '_hook_root') and self._hook_root:
                self._hook_root.destroy()
        except:
            pass
        
        try:
            icon.stop()
        except:
            pass
        
        # Si icon.stop() retorna normalmente, esto lo cierra limpiamente
        QTimer.singleShot(100, lambda: os._exit(0))
        
    def on_capture(self, icon, item):
        self.start_capture()

    def on_about(self, icon, item):
        self._signals.open_about.emit()

    def on_preferences(self, icon, item):
        print("[PREF] on_preferences llamado desde tray")
        if self.capturing:
            print("[PREF] Estábamos en estado capturando=True, cancelando para abrir Preferencias")
            self.capturing = False
        if not self.running:
            print("[PREF][WARN] on_preferences llamado pero self.running=False")
        self._signals.open_preferences.emit()

    def setup_tray_icon(self):
        image = self._create_tray_image()
        TRAY_MENU_CAPTURE = f"Capturar y Traducir {hotkey_text}"
        menu  = pystray.Menu(
            pystray.MenuItem(TRAY_MENU_CAPTURE, self.on_capture, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(TRAY_MENU_PREFERENCES, self.on_preferences),
            pystray.MenuItem(TRAY_MENU_ABOUT, self.on_about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(TRAY_MENU_QUIT, self.on_quit),
        )
        tooltip = f"OCR Translator - Presiona {hotkey_text} para capturar"

        self.icon = pystray.Icon(
            TRAY_NAME,
            image,
            tooltip,
            menu,
        )

    def _create_tray_image(self):
        icon_path = self.get_resource_path('resources/icon.ico')
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                return img.resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                pass
        from PIL import ImageDraw
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(image)
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
        dlg.setAttribute(Qt.WA_DeleteOnClose, False)
        dlg.setWindowFlags(Qt.Window)
        dlg.setMinimumWidth(320)

        layout = QVBoxLayout(dlg)
        label = QLabel(ABOUT_TEXT)
        label.setWordWrap(True)
        layout.addWidget(label)

        def _do_close():
            dlg.hide()
            self._about_window = None

        def _on_close_event_patch(event):
            event.ignore()
            QTimer.singleShot(0, _do_close)

        dlg.closeEvent = _on_close_event_patch

        self._about_window = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _run_preferences_window(self):
        print("[PREF] _run_preferences_window invocado en hilo principal Qt")

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
            print("[PREF] PreferencesWindow cerrada, limpiando referencia")
            self._prefs_window = None
            try:
                self._register_hotkeys()
            except Exception as e:
                print(f"[WARN] No se pudieron recargar hotkeys tras cerrar preferencias: {e}")

        win.closed.connect(_on_closed)
        win.download_model_requested.connect(self._download_model_with_splash)
        self._signals.model_download_finished.connect(win.on_model_download_finished)
        self._signals.model_download_failed.connect(win.on_model_download_failed)

        win.show()
        win.raise_()
        win.activateWindow()

        self._prefs_window = win
        
    def _download_model_with_splash(self, new_lang: str):
        """Abre el splash, descarga el modelo en un thread y recarga el engine en el hilo principal."""
        splash = SplashScreen()
        splash.show()
        self.qt_app.processEvents()
        self.qt_app.processEvents()

        def _worker():
            try:
                splash.set_download_mode()
                splash.set_status(f"Descargando modelo '{new_lang}'...", 0.10)
                with ProgressCapture(splash, "Descargando", 0.10, 0.90):
                    paddle_lang = self.ocr_engine._get_paddle_lang(new_lang)
                    from paddleocr import PaddleOCR as _POCR
                    _tmp = _POCR(
                        use_angle_cls=True,
                        lang=paddle_lang,
                        use_gpu=False,
                        show_log=False,
                    )
                    del _tmp
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
        print(f"[OCR] Modelo '{lang}' descargado correctamente.")
        try:
            self.ocr_engine._init_engine(lang)
        except Exception as e:
            print(f"[ERROR] No se pudo recargar OCR engine: {e}")

    def _on_model_download_failed(self, lang: str):
        QMessageBox.warning(
            None,
            "Error de descarga",
            f"No se pudo descargar el modelo para '{lang}'.\nVerifica tu conexión e inténtalo de nuevo.",
        )

    def _show_error_message(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle(APP_NAME)
        msg.setText(message)
        msg.exec()

    # ==========================================================
    # BLOQUE: Helpers de Utilidades
    # ==========================================================
    def get_resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    # Verificar instancia única ANTES de inicializar Qt
    if not acquire_single_instance_lock():
        sys.exit(0) 

    try:
        app = OCRTranslatorApp()
        app.run()
    finally:
        release_single_instance_lock()