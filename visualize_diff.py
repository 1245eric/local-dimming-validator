import sys
import subprocess

try:
    import cv2
    import numpy as np
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python", "numpy"])
    import cv2
    import numpy as np

import re
import os

def parse_dump(file_path):
    dump_data = np.zeros(3200, dtype=np.int32)
    # The file format is e.g.: [80]    125    0x2000'0060    UCHAR
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(r'\[(\d+)\]\s+(\d+)', line)
            if match:
                idx = int(match.group(1))
                val = int(match.group(2))
                if 0 <= idx < 3200:
                    dump_data[idx] = val
    # Returns a 40x80 numpy array
    return dump_data.reshape((40, 80))

def get_output_sim(file_path):
    img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("Warning: Could not read output sim file, returning zeros.")
        return np.zeros((40, 80), dtype=np.int32)
    # Downsample by taking top-left pixel of each 16x16 block
    sim_data = img[::16, ::16].astype(np.int32)
    return sim_data

def visualize_diff(dump_path, output_path, result_path):
    dump_arr = parse_dump(dump_path)
    sim_arr = get_output_sim(output_path)
    
    vis_img = np.zeros((40, 80, 3), dtype=np.uint8)
    
    # Comparison Logic:
    # 判斷重疊: 只要雙方都大於 0 就是重疊 (White)
    # 只有 Dump 有 (>0), Output 沒有 (==0) -> Red
    # 只有 Output 有 (>0), Dump 沒有 (==0) -> Blue
    # 雙方皆黑 (== 0) -> Black
    
    diff_count = 0
    for y in range(40):
        for x in range(80):
            d_val = dump_arr[y, x]
            s_val = sim_arr[y, x]
            
            if d_val > 0 and s_val > 0:
                vis_img[y, x] = (255, 255, 255) # White: 重疊
            elif d_val > 0 and s_val == 0:
                vis_img[y, x] = (0, 0, 255) # Red: Dump 有, Output 沒有
                diff_count += 1
            elif d_val == 0 and s_val > 0:
                vis_img[y, x] = (255, 0, 0) # Blue: Output 有, Dump 沒有
                diff_count += 1
            else:
                vis_img[y, x] = (0, 0, 0) # Black: 皆沒
                
    # Resize to 1280x640 using nearest neighbor to keep hard pixel edges
    vis_img_large = cv2.resize(vis_img, (1280, 640), interpolation=cv2.INTER_NEAREST)
    
    # Add a legend
    cv2.putText(vis_img_large, "Legend:", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(vis_img_large, "Red: Only Dump > 0 (Dump extra)", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(vis_img_large, "Blue: Only Output > 0 (Missing in Dump)", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    cv2.putText(vis_img_large, "White: Both > 0 (Overlap)", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    cv2.imwrite(result_path, vis_img_large)
    return diff_count

if __name__ == "__main__":
    dp = r"c:\Users\erichsu\.gemini\antigravity\playground\0.txt"
    op = r"c:\Users\erichsu\.gemini\antigravity\playground\dummy_output.png"
    rp = r"c:\Users\erichsu\.gemini\antigravity\playground\diff_result.png"
    
    diffs = visualize_diff(dp, op, rp)
    print(f"Visualization generated: {rp}")
    print(f"Total disparate blocks: {diffs}")
