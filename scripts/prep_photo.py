from __future__ import annotations

import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "source-prepped.png"


def prep_photo(source_path: Path) -> None:
    if not source_path.is_file():
        raise SystemExit(f"Photo not found: {source_path}")

    print(f"Loading photo from {source_path}...")
    img = Image.open(source_path).convert("RGBA")
    arr = np.array(img)
    orig_h, orig_w, _ = arr.shape
    alpha = arr[:, :, 3]

    # Crop tightly around head, collar, and upper shoulders
    # Profile coordinates: hair starts near top (~3%), shoulders extend to ~92%
    top = int(orig_h * 0.02)
    bottom = int(orig_h * 0.93)
    left = int(orig_w * 0.08)
    right = int(orig_w * 0.92)

    crop = arr[top:bottom, left:right]
    crop_rgb = crop[:, :, :3]
    crop_alpha = crop[:, :, 3]

    # Convert to grayscale
    gray = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)

    # If alpha is mostly opaque, detect background
    if np.mean(crop_alpha > 20) > 0.95:
        # Fallback boundary detection
        h, w = gray.shape
        mask = np.zeros((h + 2, w + 2), np.uint8)
        for x_seed in range(0, w, 20):
            if gray[0, x_seed] >= 240:
                cv2.floodFill(gray.copy(), mask, (x_seed, 0), 0, loDiff=3, upDiff=3)
        is_bg = (mask[1:-1, 1:-1] == 1)
        crop_alpha[is_bg] = 0

    is_subject = crop_alpha > 20

    # Boost local contrast with CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.8, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Normalize subject tones so highlights remain visible characters rather than blank space
    subj_vals = enhanced[is_subject]
    if len(subj_vals) > 0:
        min_v = float(subj_vals.min())
        max_v = float(subj_vals.max())
        norm = enhanced.astype(np.float32)
        norm[is_subject] = (norm[is_subject] - min_v) / (max_v - min_v + 1e-5) * 220.0 + 20.0
        enhanced = norm.astype(np.uint8)

    # Assemble RGBA: RGB has enhanced tone, A retains clean subject isolation
    output_rgba = np.dstack([enhanced, enhanced, enhanced, crop_alpha])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(output_rgba).save(OUT)
    print(f"Prepped image saved with alpha to {OUT}")


def main() -> None:
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    else:
        tp_profile = ROOT / "public" / "profile-transparent-bg.png"
        regular_profile = ROOT / "public" / "profile.png"
        source = tp_profile if tp_profile.exists() else regular_profile

    prep_photo(source)


if __name__ == "__main__":
    main()
