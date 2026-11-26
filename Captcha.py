"""
CAPTCHA solver (ddddocr) — đọc trực tiếp response từ API.

Hỗ trợ đầu vào:
  - bytes ảnh thô (JPEG/PNG/GIF/BMP), vd: response.content khi API trả ảnh
  - text hex "FF D8 FF E0 ..." (có/không dấu cách, xuống dòng) — dạng API hiện tại
  - text base64 hoặc data URI "data:image/jpeg;base64,..."
  - đường dẫn file ảnh hoặc file .txt chứa một trong các dạng trên
  - np.ndarray

Cách dùng:
    python Captcha.py response.txt              # giải 1 response / ảnh
    python Captcha.py --bench samples/          # đo accuracy + thời gian
                                                # (tên file = nhãn, vd: v843p.txt, v843p_2.png)
Trong code:
    import requests
    from Captcha import read_captcha
    r = requests.get(CAPTCHA_URL)
    print(read_captcha(r.content))
"""
import base64
import binascii
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable, Optional, Union

import cv2
import numpy as np
import ddddocr
from PIL import Image

CHARSET: Optional[str] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
EXPECTED_LEN: Optional[int] = None # vd: 5
UPSCALE = 3
BLUR_K = 11                        # Gaussian blur (trên ảnh đã upscale): trung hòa nhiễu hạt
THRESH_FACTOR = 0.75               # ngưỡng = 0.75 x Otsu -> chỉ giữ vùng thật sự tối (nét chữ)
OPEN_K = 5                         # mở hình thái học để cắt cầu nối nhiễu; 7 sạch hơn nhưng có thể ăn nét mảnh
MIN_AREA_RATIO = 0.004             # bỏ thành phần < 0.4% diện tích ảnh

OCR = ddddocr.DdddOcr(show_ad=False)
if CHARSET:
    OCR.set_ranges(CHARSET)

_OPEN_KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (OPEN_K, OPEN_K))
_IMG_MAGIC = (b"\xff\xd8\xff", b"\x89PNG", b"GIF8", b"BM")
_HEX_RE = re.compile(rb"^[0-9A-Fa-f\s]+$")
ImageInput = Union[str, os.PathLike, bytes, bytearray, np.ndarray]


# ----------------------------------------------------------------------------
# Giải mã response
# ----------------------------------------------------------------------------
def decode_payload(data: Union[bytes, bytearray, str]) -> bytes:
    """Chuyển response (ảnh thô / hex / base64 / data URI) thành bytes ảnh."""
    if isinstance(data, str):
        data = data.encode("ascii", errors="ignore")
    data = bytes(data)
    if data.startswith(_IMG_MAGIC):
        return data                                        # đã là ảnh thô

    text = data.strip()
    if text.startswith(b"data:"):
        text = text.split(b",", 1)[1]                      # data URI -> base64
    elif _HEX_RE.match(text):
        try:
            img = binascii.unhexlify(re.sub(rb"\s+", b"", text))
            if img.startswith(_IMG_MAGIC):
                return img
        except binascii.Error:
            pass                                           # lẻ ký tự -> thử base64
    try:
        img = base64.b64decode(text, validate=False)
    except binascii.Error as e:
        raise ValueError("Response không phải ảnh / hex / base64 hợp lệ") from e
    if not img.startswith(_IMG_MAGIC):
        raise ValueError("Giải mã xong nhưng không phải định dạng ảnh được hỗ trợ")
    return img


def _load_gray(src: ImageInput) -> np.ndarray:
    if isinstance(src, np.ndarray):
        return src if src.ndim == 2 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
    if isinstance(src, (str, os.PathLike)) and os.path.isfile(src):
        src = Path(src).read_bytes()                       # file ảnh hoặc .txt đều đi qua decode_payload
    buf = decode_payload(src)
    img = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("cv2 không decode được ảnh")
    return img


def _ocr(gray: np.ndarray) -> str:
    text = OCR.classification(Image.fromarray(gray))
    return re.sub(r"[^A-Za-z0-9]", "", text)


# ----------------------------------------------------------------------------
# Tiền xử lý — chỉnh cho loại nhiễu hạt dày (đã thử trên mẫu "v843p")
# ----------------------------------------------------------------------------
def preprocess(gray: np.ndarray) -> np.ndarray:
    up = cv2.resize(gray, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)

    # Nét chữ là mảng đen đặc nên vẫn tối sau khi blur; nhiễu hạt đen/trắng xen kẽ
    # bị trung bình thành xám -> ngưỡng thấp hơn Otsu sẽ loại được phần lớn nhiễu.
    blurred = cv2.GaussianBlur(up, (BLUR_K, BLUR_K), 0)
    otsu, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, binary = cv2.threshold(blurred, otsu * THRESH_FACTOR, 255, cv2.THRESH_BINARY_INV)

    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, _OPEN_KERNEL)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    keep = (stats[:, cv2.CC_STAT_AREA] >= MIN_AREA_RATIO * binary.size).astype(np.uint8) * 255
    keep[0] = 0
    out = 255 - keep[labels]

    # ddddocr tự resize về cao 64 px -> làm luôn ở đây bằng INTER_AREA.
    return cv2.resize(out, (round(out.shape[1] * 64 / out.shape[0]), 64),
                      interpolation=cv2.INTER_AREA)


def _is_valid(text: str) -> bool:
    if EXPECTED_LEN is not None and len(text) != EXPECTED_LEN:
        return False
    if CHARSET and any(c not in CHARSET for c in text):
        return False
    return bool(text)


# ----------------------------------------------------------------------------
# API chính
# ----------------------------------------------------------------------------
def read_captcha(src: ImageInput, debug: bool = False,
                 debug_dir: str = "debug_preprocess") -> str:
    gray = _load_gray(src)
    prepared = preprocess(gray)
    if debug:
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, "decoded.png"), gray)
        cv2.imwrite(os.path.join(debug_dir, "final_cleaned_image.png"), prepared)

    text = _ocr(prepared)
    if _is_valid(text):
        return text
    raw_text = _ocr(gray)                      # fallback chỉ chạy khi kết quả sai định dạng
    return raw_text if _is_valid(raw_text) else text


# ----------------------------------------------------------------------------
# Benchmark
# ----------------------------------------------------------------------------
def benchmark(folder: str) -> None:
    exts = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".txt"}
    files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in exts)
    if not files:
        print("Không có file trong thư mục.")
        return
    grays = [_load_gray(p) for p in files]
    labels = [p.stem.split("_")[0] for p in files]

    variants: dict[str, Callable[[np.ndarray], str]] = {
        "raw (không tiền xử lý)":  lambda g: _ocr(g),
        "preprocess":              lambda g: _ocr(preprocess(g)),
        "read_captcha (fallback)": lambda g: read_captcha(g),
    }
    _ocr(grays[0])                             # warm-up ONNX
    print(f"{len(files)} mẫu\n{'Biến thể':<26}{'Accuracy':>10}{'ms/ảnh':>10}")
    for name, fn in variants.items():
        correct, wrong, t0 = 0, [], time.perf_counter()
        for g, y in zip(grays, labels):
            pred = fn(g)
            if pred.lower() == y.lower():
                correct += 1
            else:
                wrong.append((y, pred))
        ms = (time.perf_counter() - t0) * 1000 / len(files)
        print(f"{name:<26}{correct / len(files):>9.1%}{ms:>10.1f}")
        for y, pred in wrong[:5]:
            print(f"    sai: {y!r} -> {pred!r}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--bench":
        benchmark(sys.argv[2])
    else:
        src = sys.argv[1] if len(sys.argv) > 1 else "image.png"
        t0 = time.perf_counter()
        result = read_captcha(src, debug=True)
        print(f"Result: {result}  ({(time.perf_counter() - t0) * 1000:.1f} ms)")