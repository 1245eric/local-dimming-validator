import sys
import subprocess

try:
    import cv2
    import numpy as np
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python", "numpy"])
    import cv2
    import numpy as np

import os

def create_dummy_input(filepath):
    # Create 1280x640 black image
    img = np.zeros((640, 1280), dtype=np.uint8)
    
    # Draw a white polygon to simulate the user's input
    # Points roughly matching the user's image: top-left area, somewhat tilted
    pts = np.array([[20, 50], [150, 40], [160, 140], [25, 150]], np.int32)
    pts = pts.reshape((-1, 1, 2))
    cv2.fillPoly(img, [pts], 255)
    
    # Add some random pixels and gradients to test max pooling more thoroughly
    # A smaller gray spot
    cv2.circle(img, (300, 300), 20, 128, -1)
    
    cv2.imwrite(filepath, img)
    return img

def process_image(img, output_filepath):
    h, w = img.shape
    block_h, block_w = 16, 16
    
    out_img = np.zeros((h, w), dtype=np.uint8)
    
    for y in range(0, h, block_h):
        for x in range(0, w, block_w):
            block = img[y:y+block_h, x:x+block_w]
            max_val = np.max(block)
            if max_val > 0:
                out_img[y:y+block_h, x:x+block_w] = max_val
                
    cv2.imwrite(output_filepath, out_img)
    return out_img

if __name__ == "__main__":
    base_dir = r"c:\Users\erichsu\.gemini\antigravity\playground"
    os.makedirs(base_dir, exist_ok=True)
    
    input_path = os.path.join(base_dir, "dummy_input.png")
    output_path = os.path.join(base_dir, "dummy_output.png")
    
    img = create_dummy_input(input_path)
    process_image(img, output_path)
    print(f"Generated:\n{input_path}\n{output_path}")
