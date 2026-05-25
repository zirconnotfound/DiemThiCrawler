import os
import re
import cv2
import numpy as np
import ddddocr

OCR = ddddocr.DdddOcr(show_ad=False)

def _save_debug_image(image: np.ndarray, filename: str, debug_dir: str) -> None:
    os.makedirs(debug_dir, exist_ok=True)
    debug_path = os.path.join(debug_dir, filename)
    cv2.imwrite(debug_path, image)

def _preprocess_for_captcha(image_path: str) -> np.ndarray:
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    # 1. Upscale FIRST. This gives us higher resolution to work with
    # so we don't accidentally erase entire letters.
    upscaled = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # 2. Binarize
    _, binary = cv2.threshold(upscaled, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 3. Gentle Opening on the high-res image to break thin noise
    kernel = np.ones((3, 3), np.uint8) 
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # 4. Area Filter (Adjusted for the 3x upscale: 30 * 9 = ~270)
    # This safely removes the floating noise chunks without border checks.
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    clean_mask = np.zeros_like(opened)
    
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] >= 250: 
            clean_mask[labels == i] = 255

    # 5. VERY gentle horizontal erosion to pry kissing letters apart.
    # Because the image is 3x larger, a (1, 3) erosion won't destroy the text now.
    horizontal_kernel = np.ones((1, 3), np.uint8)
    separated = cv2.erode(clean_mask, horizontal_kernel, iterations=1)

    # 6. Invert to black text on white background
    final_image = 255 - separated

    return final_image

def read_captcha(image_path: str = "image.png", debug: bool = False, debug_dir: str = "debug_preprocess") -> str:
    prepared_image = _preprocess_for_captcha(image_path)
    
    if debug:
        _save_debug_image(prepared_image, "final_cleaned_image.png", debug_dir)
        
    # Execute OCR on the single, clean image
    text = OCR.classification(prepared_image)
    return re.sub(r"[^A-Za-z0-9]", "", text)

if __name__ == "__main__":
    captcha_text = read_captcha("image.png", debug=True)
    print(f"Result: {captcha_text}")