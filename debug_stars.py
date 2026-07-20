import cv2
import numpy as np
import rawpy
import os

# Load just the first raw light frame
light_path = "./OrionNebula_Dataset/lights/"
files = [os.path.join(light_path, f) for f in os.listdir(light_path) if f.lower().endswith('.cr2')]
files.sort()

with rawpy.imread(files[0]) as raw:
    rgb = raw.postprocess(half_size=True, use_camera_wb=True) # half_size makes it faster for debugging
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# Normalize and convert to 8bit
gray_8bit = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

# Detect features
orb = cv2.ORB_create(nfeatures=1000)
kp = orb.detect(gray_8bit, None)

# Draw the circles exactly where the script thinks "stars" are
debug_img = cv2.drawKeypoints(gray_8bit, kp, None, color=(0, 255, 0), flags=0)

cv2.imwrite("detected_stars.jpg", debug_img)
print(f"Detected {len(kp)} features. Saved visualization as 'detected_stars.jpg'")