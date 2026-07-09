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
import os
import gc
import time
import logging
from collections import OrderedDict


import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageFilter


from config import (
    PADDLE_MIN_CONFIDENCE,
    PADDLE_MIN_CONFIDENCE_PIXEL,
)
from preferences import (
    get_ocr_restart_enabled,
    get_ocr_restart_char_threshold,
)

# ==========================================================
# Logger del módulo OCR
# ==========================================================
logger = logging.getLogger("ocr_engine")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] OCR Engine: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ==========================================================
# Detección de tipo de fuente y calidad de imagen
# ==========================================================
def _is_pixel_font_from_gray(gray: np.ndarray) -> bool:
    dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    dy = np.abs(np.diff(gray.astype(np.int16), axis=0))
    hard_edges = np.sum(dx > 200) + np.sum(dy > 200)
    soft_edges = np.sum((dx > 30) & (dx <= 200)) + np.sum((dy > 30) & (dy <= 200))
    total = hard_edges + soft_edges
    del dx, dy
    if total == 0:
        return False
    return (hard_edges / total) > 0.55


def is_pixel_font(image: Image.Image) -> bool:
    gray = np.array(image.convert("L"))
    return _is_pixel_font_from_gray(gray)


def _analyze_image_quality(gray: np.ndarray) -> dict:
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    contrast = float(gray.std())
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    noise = float(np.mean(cv2.absdiff(gray, blurred)))
    del blurred
    return {
        "sharpness": sharpness,
        "contrast": contrast,
        "noise": noise,
        "needs_denoise": noise > 4.0,
        "needs_contrast": contrast < 55.0,
        "needs_sharpen": sharpness < 300.0,
    }


# ==========================================================
# Helper -- normaliza resultado de .predict() a lista de bloques
# ==========================================================
def _parse_predict_result(result, min_conf: float):
    if not result:
        return []
    res = result[0]
    texts = res.get("rec_texts", [])
    scores = res.get("rec_scores", [])
    polys = res.get("rec_polys", res.get("rec_boxes", [None] * len(texts)))
    blocks = []
    for text, score, poly in zip(texts, scores, polys):
        if not text or score is None or score < min_conf:
            continue
        blocks.append({"text": text, "score": float(score), "poly": poly})
    return blocks


def _reading_order_key(b):
    poly = b["poly"]
    if poly is None:
        return (float("inf"), float("inf"))
    y = poly[0][1]
    x = poly[0][0]
    row = round(y / 20) * 20
    return (row, x)


# ==========================================================
# Cache LRU de engines (Simplificado ya que no hay múltiples idiomas)
# ==========================================================
class _EngineCache:
    def __init__(self, max_size: int = 1):
        self.max_size = max_size
        self._cache: "OrderedDict[tuple, object]" = OrderedDict()

    def get(self, key: tuple):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: tuple, engine) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = engine
            return
        self._cache[key] = engine
        while len(self._cache) > self.max_size:
            old_key, old_engine = self._cache.popitem(last=False)
            del old_engine
            gc.collect()

    def clear(self) -> None:
        for engine in self._cache.values():
            del engine
        self._cache.clear()
        gc.collect()

    def __contains__(self, key: tuple) -> bool:
        return key in self._cache


# ==========================================================
# Clase Principal -- OCREngine (ONNX Runtime con auto-detección GPU)
# ==========================================================
class OCREngine:
    _FIXED_DET_LIMIT = 960
    _GC_EVERY_N_CALLS = 5
    _MAX_THREADS = 4

    def __init__(self):
        self._cache = _EngineCache(max_size=1)
        self._engine = None
        self._calls_since_gc = 0
        self._use_gpu = False
        self._needs_restart = False

        # Como es multilenguaje, usamos una clave fija para la caché
        self._cache_key = ("multilang",)
        self._load_engine()

    # ==========================================================
    # Detección de soporte GPU (CUDA via ONNX Runtime)
    # ==========================================================
    def _detect_gpu_support(self) -> bool:
        """
        Detecta si el sistema tiene una GPU compatible con DirectX 12
        y si onnxruntime-directml está correctamente instalado.

        DirectML no requiere CUDA, cuDNN ni drivers adicionales.
        Solo necesita onnxruntime-directml (pip install onnxruntime-directml)
        y una GPU que soporte DirectX 12 (NVIDIA, AMD o Intel).
        """
        logger.info("=" * 60)
        logger.info("Iniciando detección de soporte GPU (DirectML)")
        logger.info("=" * 60)

        # --- Paso 1: Importar onnxruntime ---
        try:
            import onnxruntime as ort
            try:
                version = ort.__version__
            except AttributeError:
                from importlib.metadata import version as _pkg_version
                version = _pkg_version("onnxruntime-directml")
            logger.info(
                "ONNX Runtime importado correctamente. "
                f"Versión: {version}"
            )
        except ImportError:
            logger.warning(
                "No se pudo importar onnxruntime. "
                "Instálalo con: pip install onnxruntime-directml"
            )
            return False

        # --- Paso 2: Verificar providers disponibles ---
        try:
            available_providers = ort.get_available_providers()
        except Exception as e:
            logger.warning(
                f"Error al obtener providers disponibles: {e}. "
                "No se puede verificar soporte GPU."
            )
            return False

        logger.info(f"Providers disponibles: {available_providers}")

        if "DmlExecutionProvider" not in available_providers:
            logger.warning(
                "DmlExecutionProvider NO está en la lista de providers "
                "disponibles. Causas probables:\n"
                "  - onnxruntime-directml no está instalado.\n"
                "  - Se instaló onnxruntime (CPU) en lugar de "
                "onnxruntime-directml.\n"
                "  - La GPU no soporta DirectX 12.\n"
                "Solución: pip uninstall onnxruntime  &&  "
                "pip install onnxruntime-directml"
            )
            return False

        logger.info(
            "DmlExecutionProvider está disponible en los providers. "
            "Continuando verificación..."
        )

        # --- Paso 3: Test funcional creando una sesión mínima ---
        logger.info(
            "Realizando test funcional con sesión DirectML..."
        )
        try:
            from onnx import helper, TensorProto

            opset = helper.make_opsetid("", 17)

            node = helper.make_node("Identity", ["input"], ["output"])
            graph = helper.make_graph(
                [node],
                "MinimalTestGraph",
                [helper.make_tensor_value_info(
                    "input", TensorProto.FLOAT, [1, 1]
                )],
                [helper.make_tensor_value_info(
                    "output", TensorProto.FLOAT, [1, 1]
                )],
            )
            model = helper.make_model(graph, opset_imports=[opset])
            model.ir_version = 9

            sess = ort.InferenceSession(
                model.SerializeToString(),
                providers=["DmlExecutionProvider"],
            )
            actual_providers = sess.get_providers()
            del sess

            if "DmlExecutionProvider" not in actual_providers:
                logger.warning(
                    "La sesión de prueba se creó pero NO activó "
                    f"DmlExecutionProvider. Providers activos: "
                    f"{actual_providers}. El GPU puede no ser compatible "
                    "con DirectX 12."
                )
                return False

            logger.info(
                "Test funcional EXITOSO. La sesión usó "
                f"DmlExecutionProvider. Providers activos: "
                f"{actual_providers}"
            )

        except ImportError:
            logger.warning(
                "El paquete 'onnx' no está instalado. No se puede hacer "
                "test funcional. Se asume que DirectML funciona basándose "
                "en la disponibilidad del provider. Instala 'onnx' para "
                "verificación completa: pip install onnx"
            )
            logger.info(
                "Asumiendo GPU funcional basándose en "
                "DmlExecutionProvider disponible."
            )
            return True

        except Exception as e:
            logger.warning(
                f"El test funcional falló: {e}. "
                "DirectML podría no estar correctamente configurado. "
                "Cayendo a CPU."
            )
            return False

        logger.info("=" * 60)
        logger.info("GPU DirectML detectada y verificada correctamente")
        logger.info("=" * 60)
        return True

    # ==========================================================
    # Construcción del engine (GPU o CPU)
    # ==========================================================
    def _build_engine(self):
        from paddleocr import PaddleOCR

        self._use_gpu = self._detect_gpu_support()

        if self._use_gpu:
            logger.info(
                "Configurando PaddleOCR con ONNX Runtime + "
                "DmlExecutionProvider (GPU via DirectML)"
            )
            engine_config = {
                "device_type": "dml",
                "providers": [
                    "DmlExecutionProvider",
                    "CPUExecutionProvider",
                ],
                "graph_optimization_level": 99,
                "enable_mem_pattern": False,
                "execution_mode": "sequential",
                "log_severity_level": 3,
            }
        else:
            logger.info(
                "Configurando PaddleOCR con ONNX Runtime + "
                "CPUExecutionProvider (CPU)"
            )
            engine_config = {
                "device_type": "cpu",
                "providers": ["CPUExecutionProvider"],
                "graph_optimization_level": 99,
                "intra_op_num_threads": self._MAX_THREADS,
                "inter_op_num_threads": 1,
                "execution_mode": "sequential",
                "enable_cpu_mem_arena": False,
                "enable_mem_pattern": False,
                "log_severity_level": 3,
            }

        logger.info(f"engine_config: {engine_config}")

        try:
            engine = PaddleOCR(
                engine="onnxruntime",
                engine_config=engine_config,
                text_detection_model_name="PP-OCRv6_medium_det",
                text_recognition_model_name="PP-OCRv6_medium_rec",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                text_det_limit_side_len=self._FIXED_DET_LIMIT,
                text_det_limit_type="max",
            )
        except Exception as e:
            if self._use_gpu:
                logger.warning(
                    f"Error al inicializar engine con DirectML: {e}. "
                    "Reintentando con configuración CPU..."
                )
                self._use_gpu = False
                engine_config = {
                    "device_type": "cpu",
                    "providers": ["CPUExecutionProvider"],
                    "graph_optimization_level": 99,
                    "intra_op_num_threads": self._MAX_THREADS,
                    "inter_op_num_threads": 1,
                    "execution_mode": "sequential",
                    "enable_cpu_mem_arena": False,
                    "enable_mem_pattern": False,
                    "log_severity_level": 3,
                }
                logger.info(f"engine_config (fallback CPU): {engine_config}")
                engine = PaddleOCR(
                    engine="onnxruntime",
                    engine_config=engine_config,
                    text_detection_model_name="PP-OCRv6_medium_det",
                    text_recognition_model_name="PP-OCRv6_medium_rec",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    text_det_limit_side_len=self._FIXED_DET_LIMIT,
                    text_det_limit_type="max",
                )
            else:
                raise

        logger.info(
            f"PaddleOCR engine inicializado correctamente. "
            f"Dispositivo activo: {'GPU (DirectML)' if self._use_gpu else 'CPU'}"
        )
        return engine

    def _load_engine(self) -> None:
        cached = self._cache.get(self._cache_key)
        if cached is not None:
            self._engine = cached
            return

        engine = self._build_engine()

        self._cache.put(self._cache_key, engine)
        self._engine = engine

    def release_engine(self) -> None:
        self._cache.clear()
        self._engine = None
        gc.collect()

    def _ensure_engine_ready(self) -> None:
        if self._needs_restart:
            logger.info(
                "Reinicio solicitado por extracción grande anterior. "
                "Liberando memoria y recargando motor OCR..."
            )
            self.release_engine()
            self._needs_restart = False
        if self._engine is None:
            self._load_engine()

    def _maybe_collect(self) -> None:
        self._calls_since_gc += 1
        if self._calls_since_gc >= self._GC_EVERY_N_CALLS:
            gc.collect()
            if self._use_gpu:
                gc.collect()
                gc.collect()
            self._calls_since_gc = 0

    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        if img.mode != "RGB":
            converted = img.convert("RGB")
            img.close()
            return converted
        return img

    # ---------------------------------------------------------
    # Preprocesamiento
    # ---------------------------------------------------------
    def _preprocess(self, image: Image.Image):
        rgb_arr = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2GRAY)

        pixel_font = _is_pixel_font_from_gray(gray)

        if pixel_font:
            out, scale = self._preprocess_pixel_font(rgb_arr, gray, image.height)
            del rgb_arr, gray
            return out, True, scale

        quality = _analyze_image_quality(gray)
        out = self._preprocess_standard(rgb_arr, gray, quality)
        del rgb_arr, gray
        return out, False, 1

    def _preprocess_pixel_font(self, rgb_arr: np.ndarray, gray: np.ndarray, height: int):
        scale = 4 if height < 40 else 2
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
        h, w = img_cv.shape[:2]
        img_cv = cv2.resize(img_cv, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
        gray_scaled = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        del img_cv

        _, binary_otsu = cv2.threshold(gray_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_ratio = np.sum(binary_otsu == 255) / binary_otsu.size
        if white_ratio < 0.05 or white_ratio > 0.95:
            binary = cv2.adaptiveThreshold(
                gray_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 15, 2
            )
        else:
            binary = binary_otsu
        del gray_scaled, binary_otsu

        if h < 30:
            kernel = np.ones((2, 2), np.uint8)
            binary = cv2.dilate(binary, kernel, iterations=1)

        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
        del binary
        out = Image.fromarray(result)
        del result
        return out, scale

    def _preprocess_standard(self, rgb_arr: np.ndarray, gray: np.ndarray, quality: dict):
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        if quality["needs_denoise"]:
            img_cv = cv2.fastNlMeansDenoisingColored(
                img_cv, None, h=3, hColor=3,
                templateWindowSize=7, searchWindowSize=15
            )

        if quality["needs_contrast"]:
            lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            del lab
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab_merged = cv2.merge((l, a, b))
            del l, a, b
            img_cv = cv2.cvtColor(lab_merged, cv2.COLOR_LAB2BGR)
            del lab_merged

        rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        del img_cv
        out = Image.fromarray(rgb)
        del rgb

        if quality["needs_sharpen"]:
            sharpened = out.filter(ImageFilter.SHARPEN)
            out.close()
            out = sharpened

        return out

    # ---------------------------------------------------------
    # Debug
    # ---------------------------------------------------------
    def _save_debug(self, res, original_img: Image.Image, prefix: str = "ocr_debug") -> None:
        debug_dir = os.path.join("debug_ocr", prefix)
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        try:
            original_img.save(os.path.join(debug_dir, f"{timestamp}_original.png"), "PNG")
            res.save_to_img(debug_dir)
            res.save_to_json(debug_dir)
        except Exception:
            pass

    # ---------------------------------------------------------
    # Inferencia unificada
    # ---------------------------------------------------------
    def _run_inference(self, image: Image.Image, save_debug: bool = False, return_boxes: bool = False):
        if image.width < 10 or image.height < 10:
            return ("", []) if return_boxes else ""

        self._ensure_engine_ready()

        if self._engine is None:
            raise RuntimeError("OCR engine no inicializado")

        processed, pixel_font, scale = self._preprocess(image)

        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        img_array = np.array(processed.convert("RGB"))

        result = self._engine.predict(img_array)
        del img_array

        if save_debug and result:
            self._save_debug(result[0], image, prefix="extract_boxes" if return_boxes else "extract_text")

        raw_blocks = _parse_predict_result(result, min_conf)
        del result

        processed.close()
        del processed

        if self._use_gpu:
            gc.collect()

        self._maybe_collect()

        char_count = sum(len(b["text"]) for b in raw_blocks)
        logger.info(f"Caracteres extraídos: {char_count}")

        if get_ocr_restart_enabled() and char_count > get_ocr_restart_char_threshold():
            logger.warning(
                f"Extracción grande detectada ({char_count} caracteres > "
                f"{get_ocr_restart_char_threshold()}). "
                "Se activará reinicio del motor en la próxima petición."
            )
            self._needs_restart = True

        if not raw_blocks:
            return ("", []) if return_boxes else ""

        raw_blocks.sort(key=_reading_order_key)

        if not return_boxes:
            text = "\n".join(b["text"] for b in raw_blocks).strip()
            del raw_blocks
            return text

        blocks = []
        for b in raw_blocks:
            poly = b["poly"]
            if poly is not None:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                box = (
                    int(min(xs) / scale), int(min(ys) / scale),
                    int(max(xs) / scale), int(max(ys) / scale),
                )
            else:
                box = (0, 0, 0, 0)
            blocks.append({"text": b["text"], "box": box, "conf": b["score"]})

        full_text = "\n".join(b["text"] for b in blocks)
        del raw_blocks
        return full_text, blocks

    # ---------------------------------------------------------
    # API pública
    # ---------------------------------------------------------
    def extract_text(self, image: Image.Image, save_debug: bool = False) -> str:
        return self._run_inference(image, save_debug, return_boxes=False)

    def extract_text_with_boxes(self, image: Image.Image, save_debug: bool = False):
        return self._run_inference(image, save_debug, return_boxes=True)

    def process_area(self, x1, y1, x2, y2) -> str:
        img = self.capture_area(x1, y1, x2, y2)
        try:
            return self.extract_text(img)
        finally:
            img.close()
