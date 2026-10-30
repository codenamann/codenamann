"""
Prepare the profile picture for clean ASCII conversion:
  1. Use transparent background (or rembg if opaque) so the subject is isolated
  2. bilateral-smooth away noise while keeping drawn lines sharp
  3. stretch tones so skin lands near white and hair/lines stay dark
  4. darken line work (difference-of-gaussians ridges) for eyes, eyebrows, smile
  5. composite onto white and crop square around the subject

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.
"""
import os
import sys
import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_INP = os.path.join(ROOT, "public", "profile-transparent-bg.png")
if not os.path.exists(DEFAULT_INP):
    DEFAULT_INP = os.path.join(ROOT, "public", "profile.png")

INP = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INP
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "source-prepped.png")

LINE_WEIGHT = 0.65     # how hard drawn lines are pushed toward black

img = Image.open(INP).convert("RGBA")
alpha = np.array(img.split()[-1])

# If alpha is mostly opaque, try rembg if installed
if (alpha < 50).sum() < 1000:
    try:
        from rembg import remove
        print("Running rembg background removal...")
        img = remove(img)
        alpha = np.array(img.split()[-1])
    except Exception as e:
        print(f"rembg not available or failed: {e}")

rgb = np.array(img.convert("RGB"))
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# 2. smooth texture, keep edges
smooth = gray
for _ in range(3):
    smooth = cv2.bilateralFilter(smooth, 9, 40, 9)

# 3. tone stretch over the subject only
subject_pixels = smooth[alpha > 128]
if len(subject_pixels) > 0:
    lo, hi = np.percentile(subject_pixels, [2, 92])
    if hi <= lo:
        hi = lo + 1
    tone = np.clip((smooth.astype(np.float32) - lo) / (hi - lo), 0, 1)
else:
    tone = smooth.astype(np.float32) / 255.0

# 4. dark-on-light ridges -> darken
fine = cv2.GaussianBlur(smooth, (0, 0), 1.5).astype(np.float32)
coarse = cv2.GaussianBlur(smooth, (0, 0), 6).astype(np.float32)
lines = np.clip((coarse - fine) / 40.0, 0, 1)
out = np.clip(tone - LINE_WEIGHT * lines, 0, 1) * 255

# 5. paste onto white (feathered a hair to avoid a halo), square crop
mask = cv2.GaussianBlur(alpha.astype(np.float32) / 255.0, (0, 0), 1.0)
out = out * mask + 255.0 * (1.0 - mask)

ys, xs = np.where(alpha > 20)
if len(xs) > 0 and len(ys) > 0:
    side = max(xs.max() - xs.min(), ys.max() - ys.min()) + 60
    cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
    canvas = np.full((side, side), 255, np.uint8)
    x0, y0 = cx - side // 2, cy - side // 2
    sx0, sy0 = max(x0, 0), max(y0, 0)
    sx1, sy1 = min(x0 + side, out.shape[1]), min(y0 + side, out.shape[0])
    canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = out[sy0:sy1, sx0:sx1].astype(np.uint8)
else:
    canvas = out.astype(np.uint8)

Image.fromarray(canvas, mode="L").save(OUT)
print("wrote", OUT, canvas.shape)
