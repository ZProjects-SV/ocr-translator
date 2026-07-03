
import os
import sys
import gc
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from PIL import ImageGrab, Image, ImageFilter, ImageEnhance

from config import (
    PADDLE_LANG,
    PADDLE_MIN_CONFIDENCE,
    PADDLE_MIN_CONFIDENCE_PIXEL,
    TRANSLATION_TO_PADDLE_LANG,
)
from preferences import get_translation_source, get_downloaded_langs, add_downloaded_lang


# ==========================================================
# BLOQUE: Detección de capacidades de hardware (una sola vez)
# ==========================================================
_HW_CACHE = {"mkldnn_ok": None, "cpu_threads": None}


def _detect_cpu_threads() -> int:
    if _HW_CACHE["cpu_threads"] is not None:
        return _HW_CACHE["cpu_threads"]
    count = os.cpu_count() or 4
    # Dejamos 1-2 núcleos libres para UI/captura, con techo razonable.
    threads = max(2, min(count - 1, 8))
    _HW_CACHE["cpu_threads"] = threads
    return threads


def _supports_fast_mkldnn() -> bool:
    """
    Heurística: MKL-DNN acelera mucho en CPUs con AVX-512, pero en algunas
    CPUs (notablemente AMD sin AVX-512) puede ser 10-60x MAS LENTO.
    Si py-cpuinfo esta disponible, revisamos el flag directamente.
    Si no, asumimos False (seguro) y dejamos que el warm-up decida.
    """
    if _HW_CACHE["mkldnn_ok"] is not None:
        return _HW_CACHE["mkldnn_ok"]
    try:
        import cpuinfo
        flags = cpuinfo.get_cpu_info().get("flags", [])
        result = "avx512f" in flags
    except Exception:
        result = False
    _HW_CACHE["mkldnn_ok"] = result
    return result


# ==========================================================
# BLOQUE: Detección de tipo de fuente y calidad de imagen
# ==========================================================
def _is_pixel_font(image: Image.Image) -> bool:
    gray = np.array(image.convert("L"))
    dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
    dy = np.abs(np.diff(gray.astype(np.int16), axis=0))
    hard_edges = np.sum(dx > 200) + np.sum(dy > 200)
    soft_edges = np.sum((dx > 30) & (dx <= 200)) + np.sum((dy > 30) & (dy <= 200))
    total = hard_edges + soft_edges
    if total == 0:
        return False
    return (hard_edges / total) > 0.60


def _analyze_image_quality(gray: np.ndarray) -> dict:
    """
    Analiza UNA sola vez (reutilizando el gray ya calculado) para decidir
    que pasos de preprocesamiento son realmente necesarios.
    - sharpness: varianza del Laplaciano (bajo = borroso/necesita nitidez)
    - contrast: desviacion estandar de intensidades (bajo = necesita CLAHE)
    - noise: estimado rapido via diferencia con blur gaussiano (alto = necesita denoise)
    """
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    contrast = float(gray.std())

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    noise = float(np.mean(cv2.absdiff(gray, blurred)))

    return {
        "sharpness": sharpness,
        "contrast": contrast,
        "noise": noise,
        "needs_denoise": noise > 6.0,
        "needs_contrast": contrast < 40.0,
        "needs_sharpen": sharpness < 150.0,
    }


# ==========================================================
# BLOQUE: Helper — normaliza resultado de .predict() a lista de bloques
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


def _dynamic_det_limit(width: int, height: int) -> int:
    """
    Ajusta el limite de resize del detector segun el tamano real de la
    captura, para no penalizar capturas pequenas ni recortar precision
    en capturas de pantalla completa.
    """
    longest = max(width, height)
    if longest <= 480:
        return 640
    if longest <= 960:
        return 960
    if longest <= 1600:
        return 1280
    return 1600  # techo para full-screen / 4K, evita procesar sin limite


# ==========================================================
# BLOQUE: Clase Principal — OCREngine (instancia persistente)
# ==========================================================
class OCREngine:
    """
    Motor OCR con instancia persistente de PaddleOCR 3.x.
    Se carga una vez al iniciar y se reutiliza en cada captura.
    """

    _downloaded_langs: set = set()

    @classmethod
    def mark_lang_downloaded(cls, source_lang: str) -> None:
        cls._downloaded_langs.add(source_lang)
        add_downloaded_lang(source_lang)

    @classmethod
    def is_model_downloaded(cls, source_lang: str) -> bool:
        return source_lang in cls._downloaded_langs

    def __init__(self):
        print("[OCR] OCREngine.__init__: iniciando...")
        OCREngine._downloaded_langs.update(get_downloaded_langs())
        self._engine = None
        self._current_lang = None
        self._mkldnn_enabled = None

        source_lang = get_translation_source() or "en"
        self._load_engine(source_lang)
        print(f"[OCR] Engine listo (lang='{source_lang}')")

    # ----------------------------------------------------------
    # Helpers de idioma
    # ----------------------------------------------------------
    def _get_paddle_lang(self, source_lang: str) -> str:
        return TRANSLATION_TO_PADDLE_LANG.get(source_lang, PADDLE_LANG)

    # ----------------------------------------------------------
    # Carga/recarga del engine (con auto-deteccion de hardware)
    # ----------------------------------------------------------
    def _build_engine(self, paddle_lang: str, use_mkldnn: bool):
        from paddleocr import PaddleOCR
        threads = _detect_cpu_threads()
        return PaddleOCR(
            lang=paddle_lang,
            device="cpu",
            enable_mkldnn=use_mkldnn,
            cpu_threads=threads,
            ocr_version="PP-OCRv4",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=960,
            text_det_limit_type="max",
        )

    def _load_engine(self, source_lang: str) -> None:
        """Carga (o recarga si el idioma cambio) la instancia de PaddleOCR 3.x."""
        paddle_lang = self._get_paddle_lang(source_lang)

        if self._engine is not None and self._current_lang == source_lang:
            return

        if self._engine is not None:
            print(f"[OCR] Recargando engine: '{self._current_lang}' -> '{source_lang}'")
            del self._engine
            self._engine = None
            gc.collect()

        use_mkldnn = _supports_fast_mkldnn()
        print(f"[OCR] Cargando PaddleOCR 3.x: lang='{source_lang}' "
              f"(paddle='{paddle_lang}', mkldnn={use_mkldnn})...")

        try:
            engine = self._build_engine(paddle_lang, use_mkldnn)
            if use_mkldnn:
                # Warm-up: si el "acelerador" resulta contraproducente en
                # este hardware, lo detectamos aqui y recargamos sin el.
                dummy = np.full((64, 256, 3), 255, dtype=np.uint8)
                t0 = time.perf_counter()
                engine.predict(dummy)
                elapsed = time.perf_counter() - t0
                if elapsed > 2.0:  # umbral de seguridad para deteccion de CPU lenta con mkldnn
                    print(f"[OCR] MKL-DNN parece lento en este hardware ({elapsed:.2f}s), "
                          f"recargando sin el...")
                    del engine
                    gc.collect()
                    engine = self._build_engine(paddle_lang, False)
                    use_mkldnn = False
                del dummy
        except Exception as e:
            print(f"[OCR] Error cargando con mkldnn={use_mkldnn}: {e}. Reintentando sin mkldnn...")
            engine = self._build_engine(paddle_lang, False)
            use_mkldnn = False

        self._engine = engine
        self._mkldnn_enabled = use_mkldnn
        _HW_CACHE["mkldnn_ok"] = use_mkldnn  # persistir decision para futuras recargas
        self._current_lang = source_lang
        OCREngine.mark_lang_downloaded(source_lang)
        print(f"[OCR] Engine cargado correctamente (lang='{source_lang}', mkldnn={use_mkldnn})")

    def _init_engine(self, source_lang: str = None) -> None:
        source_lang = source_lang or get_translation_source() or "en"
        print(f"[OCR] _init_engine (descarga/verificacion): lang='{source_lang}'")
        self._load_engine(source_lang)
        print(f"[OCR] _init_engine: modelo '{source_lang}' verificado")

    def release_engine(self) -> None:
        if self._engine is not None:
            print("[OCR] release_engine: liberando engine...")
            del self._engine
            self._engine = None
            self._current_lang = None
            gc.collect()
            print("[OCR] release_engine: engine liberado")
        else:
            print("[OCR] release_engine: no hay engine activo")

    # ==========================================================
    # BLOQUE: Captura
    # ==========================================================
    def capture_area(self, x1, y1, x2, y2) -> Image.Image:
        img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        # Aseguramos modo RGB desde el inicio para evitar conversiones repetidas
        if img.mode != "RGB":
            converted = img.convert("RGB")
            img.close()
            return converted
        return img

    # ==========================================================
    # BLOQUE: Preprocesamiento hibrido y adaptativo
    # ==========================================================
    def _preprocess(self, image: Image.Image):
        """
        Un solo paso de analisis (gray + metricas) que decide que
        transformaciones aplicar. Evita repetir conversiones/calculos.
        Devuelve (imagen_procesada, es_pixel_font, escala_aplicada)
        """
        rgb_arr = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2GRAY)

        dx = np.abs(np.diff(gray.astype(np.int16), axis=1))
        dy = np.abs(np.diff(gray.astype(np.int16), axis=0))
        hard_edges = np.sum(dx > 200) + np.sum(dy > 200)
        soft_edges = np.sum((dx > 30) & (dx <= 200)) + np.sum((dy > 30) & (dy <= 200))
        total_edges = hard_edges + soft_edges
        pixel_font = (hard_edges / total_edges > 0.60) if total_edges else False
        del dx, dy

        if pixel_font:
            out, scale = self._preprocess_pixel_font(rgb_arr, gray, image.height)
            del rgb_arr, gray
            return out, True, scale

        quality = _analyze_image_quality(gray)
        out = self._preprocess_standard(rgb_arr, gray, quality)
        del rgb_arr, gray
        return out, False, 1

    def _preprocess_pixel_font(self, rgb_arr: np.ndarray, gray: np.ndarray, height: int):
        # Escala reducida para capturas grandes: x4 solo si el texto es muy
        # pequeno (probable UI de juego en zona chica), x2 en el resto.
        scale = 4 if height < 40 else 2
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)
        h, w = img_cv.shape[:2]
        img_cv = cv2.resize(img_cv, (w * scale, h * scale), interpolation=cv2.INTER_NEAREST)
        gray_scaled = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        del img_cv

        _, binary_otsu = cv2.threshold(gray_scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        white_ratio = np.sum(binary_otsu == 255) / binary_otsu.size
        if white_ratio < 0.05 or white_ratio > 0.95:
            binary = cv2.adaptiveThreshold(gray_scaled, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 15, 2)
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
        print(f"[OCR] Pixel-font preprocesado (x{scale})")
        return out, scale

    def _preprocess_standard(self, rgb_arr: np.ndarray, gray: np.ndarray, quality: dict):
        """
        Aplica SOLO las correcciones que el analisis de calidad indica
        necesarias, evitando costo innecesario en imagenes ya nitidas.
        """
        img_cv = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

        if quality["needs_denoise"] and img_cv.shape[1] < 900:
            # fastNlMeansDenoising (gris-equivalente aplicado en color, mas
            # barato que la version Colored) solo si realmente hay ruido
            # y la imagen no es demasiado grande (costo escala con pixeles).
            denoised = cv2.fastNlMeansDenoisingColored(
                img_cv, None, h=3, hColor=3, templateWindowSize=7, searchWindowSize=15
            )
            del img_cv
            img_cv = denoised

        if quality["needs_contrast"]:
            lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
            del img_cv
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

        print(f"[OCR] Standard preprocesado (denoise={quality['needs_denoise']}, "
              f"contrast={quality['needs_contrast']}, sharpen={quality['needs_sharpen']})")
        return out

    # ==========================================================
    # BLOQUE: Utilidad de Guardado para Debug
    # ==========================================================
    def _save_debug_images(self, original_img: Image.Image, processed_img: Image.Image, prefix: str = "ocr_debug"):
        debug_dir = "debug_ocr"
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = int(time.time() * 1000)
        orig_path = os.path.join(debug_dir, f"{prefix}_1_original_{timestamp}.png")
        proc_path = os.path.join(debug_dir, f"{prefix}_2_processed_{timestamp}.png")
        try:
            original_img.save(orig_path, "PNG")
            processed_img.save(proc_path, "PNG")
            print(f"[DEBUG] Imagenes guardadas en: {debug_dir}/")
        except Exception as e:
            print(f"[DEBUG] Error al guardar imagenes: {e}")

    # ==========================================================
    # BLOQUE: Extraccion de Texto
    # ==========================================================
    def extract_text(self, image: Image.Image, lang: str = None, save_debug: bool = False) -> str:
        if image.width < 10 or image.height < 10:
            return ""

        source_lang = lang or get_translation_source() or "en"
        self._load_engine(source_lang)

        t_pre0 = time.perf_counter()
        processed, pixel_font, scale = self._preprocess(image)
        print(f"[OCR] preprocesamiento: {time.perf_counter()-t_pre0:.3f}s")

        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        if save_debug:
            self._save_debug_images(image, processed, prefix="extract_text")

        img_array = np.array(processed.convert("RGB"))
        processed.close()
        del processed

        det_limit = _dynamic_det_limit(image.width, image.height)
        t0 = time.perf_counter()
        result = self._engine.predict(img_array, text_det_limit_side_len=det_limit)
        print(f"[OCR] inference: {time.perf_counter()-t0:.2f}s (det_limit={det_limit})")
        del img_array

        blocks = _parse_predict_result(result, min_conf)
        del result

        if not blocks:
            return ""

        blocks.sort(key=lambda b: b["poly"][0][1] if b["poly"] is not None else 0)
        text = "\n".join(b["text"] for b in blocks).strip()
        del blocks
        return text

    def extract_text_with_boxes(self, image: Image.Image, save_debug: bool = False):
        if image.width < 10 or image.height < 10:
            return "", []

        source_lang = get_translation_source() or "en"
        self._load_engine(source_lang)

        t_pre0 = time.perf_counter()
        processed, pixel_font, scale = self._preprocess(image)
        print(f"[OCR] preprocesamiento: {time.perf_counter()-t_pre0:.3f}s")

        min_conf = PADDLE_MIN_CONFIDENCE_PIXEL if pixel_font else PADDLE_MIN_CONFIDENCE

        if save_debug:
            self._save_debug_images(image, processed, prefix="extract_boxes")

        img_array = np.array(processed.convert("RGB"))
        processed.close()
        del processed

        det_limit = _dynamic_det_limit(image.width, image.height)
        print(f"[OCR] extract_text_with_boxes: {image.width}x{image.height}, "
              f"lang='{source_lang}', pixel_font={pixel_font}, scale={scale}")

        t0 = time.perf_counter()
        result = self._engine.predict(img_array, text_det_limit_side_len=det_limit)
        print(f"[OCR] inference: {time.perf_counter()-t0:.2f}s (det_limit={det_limit})")
        del img_array

        raw_blocks = _parse_predict_result(result, min_conf)
        del result

        if not raw_blocks:
            return "", []

        raw_blocks.sort(key=lambda b: b["poly"][0][1] if b["poly"] is not None else 0)

        blocks = []
        for b in raw_blocks:
            poly = b["poly"]
            if poly is not None:
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                box = (int(min(xs) / scale), int(min(ys) / scale),
                       int(max(xs) / scale), int(max(ys) / scale))
            else:
                box = (0, 0, 0, 0)
            blocks.append({"text": b["text"], "box": box, "conf": b["score"]})

        full_text = "\n".join(b["text"] for b in blocks)
        del raw_blocks
        print(f"[OCR] resultado: {len(blocks)} bloques, {len(full_text)} chars")
        return full_text, blocks

    def process_area(self, x1, y1, x2, y2, lang: str = None) -> str:
        img = self.capture_area(x1, y1, x2, y2)
        try:
            return self.extract_text(img, lang)
        finally:
            img.close()
