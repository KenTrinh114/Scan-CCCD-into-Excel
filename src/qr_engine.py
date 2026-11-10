"""3-Pass Low-CPU QR Decoder with Zalo/Messenger Auto-Rescue Mechanics."""

import os
import sys
import threading
from pathlib import Path
import cv2
import numpy as np
import zxingcpp

from src.failed_handler import load_heif_image, to_long_path

# 3x3 sharpening kernel
SHARPEN_KERNEL = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)

_thread_local = threading.local()


def _downscale_if_large(img: np.ndarray, max_side: int = 1600) -> np.ndarray:
    """Downscale oversized images if maximum dimension exceeds max_side."""
    h, w = img.shape[:2]
    max_dim = max(h, w)
    if max_dim > max_side:
        scale = max_side / float(max_dim)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img


def get_asset_path(relative_path: str | Path) -> Path:
    """Resolve asset paths supporting both normal python execution and PyInstaller frozen execution."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        # Parent of src/ is the project root
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir / relative_path


def get_thread_wechat_detector() -> cv2.wechat_qrcode_WeChatQRCode | None:
    """
    Worker-level singleton: instantiates WeChatQRCode once per thread using thread-local storage.
    Ensures safe concurrent execution without cross-thread C++ state races, while avoiding
    redundant model file loads from disk.
    """
    if not hasattr(_thread_local, "detector"):
        try:
            models_dir = get_asset_path(Path("assets") / "wechat_models")
            detect_proto = str(models_dir / "detect.prototxt")
            detect_model = str(models_dir / "detect.caffemodel")
            sr_proto = str(models_dir / "sr.prototxt")
            sr_model = str(models_dir / "sr.caffemodel")

            if (
                os.path.isfile(detect_proto)
                and os.path.isfile(detect_model)
                and os.path.isfile(sr_proto)
                and os.path.isfile(sr_model)
            ):
                _thread_local.detector = cv2.wechat_qrcode_WeChatQRCode(
                    detect_proto, detect_model, sr_proto, sr_model
                )
            else:
                _thread_local.detector = None
        except Exception as e:
            # Degrade gracefully to zxingcpp
            print(f"Notice: WeChatQRCode model initialization failed, using zxing-cpp fallback. ({e})")
            _thread_local.detector = None
    return _thread_local.detector


class CCCDQRScanner:
    """Low-CPU, high-accuracy QR code decoder optimized for Vietnamese CCCD cards."""

    # Maximum dimension after upscaling (prevents oversized intermediary arrays)
    MAX_UPSCALE_DIM = 1500

    def __init__(self) -> None:
        # Enforce single-thread mode in OpenCV so worker threads never cause N×M thread explosion
        cv2.setNumThreads(1)

        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        self._last_path: Path | None = None
        self._last_gray: np.ndarray | None = None

    @property
    def wechat_detector(self) -> cv2.wechat_qrcode_WeChatQRCode | None:
        """Worker thread-local WeChatQRCode detector."""
        return get_thread_wechat_detector()

    def _load_grayscale(self, file_path: Path) -> np.ndarray | None:
        """
        Safely load an image as grayscale. Supports JPG, PNG, WEBP, BMP, and Apple HEIC/HEIF.
        Uses numpy fromfile to prevent breakage on Windows paths with Vietnamese diacritics.
        Uses libjpeg reduced decoding for huge files to save 75% memory bandwidth and CPU time.
        Downscales oversized images if > 1600px.
        """
        try:
            suffix = file_path.suffix.lower()
            if suffix in {".heic", ".heif"}:
                image = load_heif_image(file_path)
                gray = np.array(image.convert("L")) if image is not None else None
            else:
                raw_bytes = np.fromfile(to_long_path(file_path), dtype=np.uint8)
                if raw_bytes.size == 0:
                    return None

                gray = None
                # Huge file optimization: use libjpeg-turbo reduced decoding directly from DCT coefficients
                if raw_bytes.size > 2_000_000 and hasattr(cv2, "IMREAD_REDUCED_GRAYSCALE_2"):
                    try:
                        gray_reduced = cv2.imdecode(raw_bytes, cv2.IMREAD_REDUCED_GRAYSCALE_2)
                        if gray_reduced is not None and max(gray_reduced.shape[:2]) >= 1200:
                            gray = gray_reduced
                    except Exception:
                        gray = None

                if gray is None:
                    gray = cv2.imdecode(raw_bytes, cv2.IMREAD_GRAYSCALE)

            if gray is None:
                return None

            return _downscale_if_large(gray, 1600)
        except Exception:
            return None

    def _load_color(self, file_path: Path) -> np.ndarray | None:
        """
        Safely load an image as BGR color array, supporting JPG, PNG, WEBP, BMP, and Apple HEIC/HEIF.
        Uses numpy fromfile to prevent breakage on Windows paths with Vietnamese diacritics.
        Downscales oversized images if > 1600px.
        """
        try:
            suffix = file_path.suffix.lower()
            if suffix in {".heic", ".heif"}:
                image = load_heif_image(file_path)
                if image is not None:
                    rgb = np.array(image.convert("RGB"))
                    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                else:
                    bgr = None
            else:
                raw_bytes = np.fromfile(to_long_path(file_path), dtype=np.uint8)
                if raw_bytes.size == 0:
                    return None

                bgr = None
                if raw_bytes.size > 2_000_000 and hasattr(cv2, "IMREAD_REDUCED_COLOR_2"):
                    try:
                        bgr_reduced = cv2.imdecode(raw_bytes, cv2.IMREAD_REDUCED_COLOR_2)
                        if bgr_reduced is not None and max(bgr_reduced.shape[:2]) >= 1200:
                            bgr = bgr_reduced
                    except Exception:
                        bgr = None

                if bgr is None:
                    bgr = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)

            if bgr is None:
                return None

            return _downscale_if_large(bgr, 1600)
        except Exception:
            return None

    def _try_zxing_only(self, image: np.ndarray, check_fn) -> str | None:
        """Fast path: try only zxing-cpp without the heavier WeChat fallback."""
        if image is None or image.size == 0:
            return None
        try:
            results = zxingcpp.read_barcodes(
                image,
                formats=zxingcpp.BarcodeFormat.QRCode,
                try_rotate=True,
                try_downscale=True,
            )
            return check_fn([r.text for r in results])
        except Exception:
            return None

    def _try_wechat_only(self, image: np.ndarray, check_fn) -> str | None:
        """Helper to safely run WeChatQRCode on a preprocessed candidate crop."""
        detector = self.wechat_detector
        if detector is None or image is None or image.size == 0:
            return None
        try:
            texts, _ = detector.detectAndDecode(image)
            return check_fn(texts)
        except Exception:
            return None

    def _capped_upscale(
        self, image: np.ndarray, factor: float, interpolation: int = cv2.INTER_CUBIC
    ) -> np.ndarray:
        """Upscale image by *factor*, capping the result at MAX_UPSCALE_DIM to avoid oversized arrays."""
        h, w = image.shape[:2]
        max_dim = max(h, w)
        effective_factor = min(factor, self.MAX_UPSCALE_DIM / max(1, max_dim))
        if effective_factor <= 1.05:
            return image
        return cv2.resize(
            image, (0, 0), fx=effective_factor, fy=effective_factor, interpolation=interpolation
        )

    @staticmethod
    def _pad_quiet_zone(image: np.ndarray, pad: int = 24) -> np.ndarray:
        """Add white border padding around the image to guarantee standard QR quiet zone."""
        if image is None or image.size == 0:
            return image
        return cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)

    def scan_fast(self, file_path: Path) -> tuple[str | None, str | None]:
        """
        Stage 1 Fast Pass (~2ms):
        Quickly scans the image using native C++ zxing-cpp.
        Caches the decoded grayscale image in-memory for immediate Stage 2 reuse without re-reading disk.
        Returns:
            (qr_text, "OK") if decoded successfully immediately.
            (None, "UNREADABLE") if the file is corrupted/missing.
            (None, None) if image was read but Pass 1 did not find a valid CCCD QR (needs Stage 2 Rescue).
        """
        gray = self._load_grayscale(file_path)
        if gray is None:
            self._last_path = None
            self._last_gray = None
            return None, "UNREADABLE"

        # Cache decoded grayscale array for Stage 2 reuse without redundant disk I/O
        self._last_path = file_path
        self._last_gray = gray

        try:
            results = zxingcpp.read_barcodes(
                gray,
                formats=zxingcpp.BarcodeFormat.QRCode,
                try_rotate=True,
                try_downscale=True,
            )
            for r in results:
                if r.text:
                    cleaned = r.text.strip()
                    if cleaned.count("|") >= 5:
                        return cleaned, "OK"
        except Exception:
            pass

        return None, None

    def scan_rescue(self, file_path: Path, gray: np.ndarray | None = None) -> tuple[str | None, str]:
        """
        Stage 2 Deep Rescue Passes (Passes 2 through 5):
        Deep neural network and advanced image filters for cards that didn't pass Stage 1.
        Reuses cached gray array if available to avoid redundant disk reading and decoding.
        Returns (decoded_text, scan_note).
        """
        try:
            return self._scan_rescue_impl(file_path, gray)
        finally:
            self._last_gray = None
            self._last_path = None

    def _scan_rescue_impl(self, file_path: Path, gray: np.ndarray | None = None) -> tuple[str | None, str]:
        if gray is None:
            if self._last_gray is not None and self._last_path == file_path:
                gray = self._last_gray
            else:
                gray = self._load_grayscale(file_path)

        if gray is None:
            return None, "UNREADABLE"

        found_non_cccd_qr = False

        def check_candidates(texts: list[str]) -> str | None:
            nonlocal found_non_cccd_qr
            for t in texts:
                if not t:
                    continue
                cleaned = t.strip()
                if cleaned.count("|") >= 5:
                    return cleaned
                # Non-empty QR without sufficient pipes (likely VNeID QR token)
                found_non_cccd_qr = True
            return None

        # -------------------------------------------------------------
        # Pass 2: WeChat Super-Resolution C++ on full frame
        # -------------------------------------------------------------
        detector = self.wechat_detector
        if detector is not None:
            try:
                texts, _ = detector.detectAndDecode(gray)
                candidate = check_candidates(texts)
                if candidate:
                    return candidate, "OK"
            except Exception:
                pass

        # -------------------------------------------------------------
        # Pass 3: CLAHE glare recovery, quadrant cropping, fast rotations
        # (zxing-cpp on crops & rotations; WeChat fallback ONLY on top-right crop)
        # -------------------------------------------------------------
        try:
            enhanced = self.clahe.apply(gray)

            candidate = self._try_zxing_only(enhanced, check_candidates)
            if candidate:
                return candidate, "OK"

            h, w = enhanced.shape[:2]
            # Primary CCCD QR target: top-right quadrant
            tr_quad = enhanced[0 : int(h * 0.55), int(w * 0.45) : w]
            if tr_quad.shape[0] >= 20 and tr_quad.shape[1] >= 20:
                upscaled = self._capped_upscale(tr_quad, 2.0, cv2.INTER_CUBIC)
                sharpened = cv2.filter2D(upscaled, -1, SHARPEN_KERNEL)
                padded = self._pad_quiet_zone(sharpened)

                candidate = self._try_zxing_only(padded, check_candidates)
                if candidate:
                    return candidate, "OK"

                # WeChat fallback on cropped & upscaled top-right quadrant for small corner QRs
                candidate = self._try_wechat_only(padded, check_candidates)
                if candidate:
                    return candidate, "OK"

            # Fast 90°, 180°, 270° rotations using native C++ zxing (<5ms total)
            for rot_flag in (
                cv2.ROTATE_90_CLOCKWISE,
                cv2.ROTATE_180,
                cv2.ROTATE_90_COUNTERCLOCKWISE,
            ):
                rotated = cv2.rotate(enhanced, rot_flag)
                candidate = self._try_zxing_only(rotated, check_candidates)
                if candidate:
                    return candidate, "OK"
        except Exception:
            pass

        # -------------------------------------------------------------
        # Pass 4: Auto-Rescue for Heavily Compressed Images (Zalo / Messenger)
        # Fast C++ module reconstruction (avoids expensive DNN proposals on binary noise)
        # -------------------------------------------------------------
        try:
            # 4.1 Unsharp masking: restores sharp QR edges smeared by JPEG compression
            gaussian = cv2.GaussianBlur(gray, (0, 0), 2.0)
            unsharp = cv2.addWeighted(gray, 2.0, gaussian, -1.0, 0)
            candidate = self._try_zxing_only(unsharp, check_candidates)
            if candidate:
                return candidate, "OK"

            # 4.2 Denoise JPEG mosquito noise + Otsu Binarization
            denoised = cv2.medianBlur(gray, 3)
            _, otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            candidate = self._try_zxing_only(otsu, check_candidates)
            if candidate:
                return candidate, "OK"

            # 4.3 High-contrast CLAHE + dynamic range stretching
            norm_gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
            rescue_clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(6, 6))
            enhanced_rescue = rescue_clahe.apply(norm_gray)
            candidate = self._try_zxing_only(enhanced_rescue, check_candidates)
            if candidate:
                return candidate, "OK"

            # 4.4 Capped Lanczos Super-Upscale on top quadrants with quiet zone padding
            h, w = enhanced_rescue.shape[:2]
            rescue_quads = [
                enhanced_rescue[0 : int(h * 0.58), int(w * 0.40) : w],  # Top-right
                enhanced_rescue[0 : int(h * 0.58), 0 : int(w * 0.58)],  # Top-left
            ]

            close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))

            for q in rescue_quads:
                if q.shape[0] < 15 or q.shape[1] < 15:
                    continue
                # Capped 2.5x Lanczos interpolation preserves distinct pixel module transitions
                up25 = self._capped_upscale(q, 2.5, cv2.INTER_LANCZOS4)
                sharp25 = cv2.filter2D(up25, -1, SHARPEN_KERNEL)
                padded25 = self._pad_quiet_zone(sharp25)

                candidate = self._try_zxing_only(padded25, check_candidates)
                if candidate:
                    return candidate, "OK"

                # Adaptive threshold on upscaled crop + morphological closing to reconnect broken finder squares
                ad_crop = cv2.adaptiveThreshold(
                    up25, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5
                )
                closed_crop = cv2.morphologyEx(ad_crop, cv2.MORPH_CLOSE, close_kernel)
                padded_closed = self._pad_quiet_zone(closed_crop)
                candidate = self._try_zxing_only(padded_closed, check_candidates)
                if candidate:
                    return candidate, "OK"
        except Exception:
            pass

        # -------------------------------------------------------------
        # Pass 5: Color-Channel Rescue (Specialized for Vietnamese CCCD cards)
        # CCCD cards use cyan and light-green security guilloche patterns.
        # Blue channel cancels the cyan/green security background and
        # isolates the dark QR code modules.
        # -------------------------------------------------------------
        try:
            bgr = self._load_color(file_path)
            if bgr is not None and len(bgr.shape) == 3 and bgr.shape[2] == 3:
                bh, bw = bgr.shape[:2]
                # Extract top-right corner in Blue channel
                tr_bgr = bgr[0 : int(bh * 0.58), int(bw * 0.40) : bw]
                if tr_bgr.shape[0] >= 20 and tr_bgr.shape[1] >= 20:
                    b_chan = tr_bgr[:, :, 0]
                    ch_clahe = self.clahe.apply(b_chan)
                    up_ch = self._capped_upscale(ch_clahe, 2.5, cv2.INTER_LANCZOS4)
                    sharp_ch = cv2.filter2D(up_ch, -1, SHARPEN_KERNEL)
                    padded_ch = self._pad_quiet_zone(sharp_ch)
                    candidate = self._try_zxing_only(padded_ch, check_candidates)
                    if candidate:
                        return candidate, "OK"
                    candidate = self._try_wechat_only(padded_ch, check_candidates)
                    if candidate:
                        return candidate, "OK"
        except Exception:
            pass

        # If non-CCCD QR was detected (e.g. VNeID encrypted token)
        if found_non_cccd_qr:
            return None, "WRONG_QR_TYPE"

        return None, "UNREADABLE"

    def scan_image(self, file_path: Path) -> tuple[str | None, str]:
        """
        Multi-Pass QR extraction pipeline:
        Stage 1 Fast Pass: zxing-cpp (~2ms)
        Stage 2 Deep Rescue: WeChat + CLAHE + Quadrants + Compression Auto-Rescue + Blue Channel (~150ms)
        Returns (decoded_text, scan_note).
        """
        fast_result, fast_note = self.scan_fast(file_path)
        if fast_result is not None:
            return fast_result, fast_note or "OK"
        if fast_note == "UNREADABLE":
            return None, "UNREADABLE"
        return self.scan_rescue(file_path)
