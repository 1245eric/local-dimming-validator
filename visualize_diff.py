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

GRID_H, GRID_W = 40, 80
BLOCK_H, BLOCK_W = 16, 16


def parse_dump(file_path):
    total = GRID_H * GRID_W
    dump_data = np.zeros(total, dtype=np.int32)
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            # 新格式：[idx]  value（Tab 或空白分隔）
            match = re.search(r'\[(\d+)\]\s+(\d+)', line)
            # 舊格式：[idx]value0x...（無分隔符）
            if not match:
                match = re.search(r'\[(\d+)\](\d+)0x', line)
            if match:
                idx = int(match.group(1))
                val = int(match.group(2))
                if 0 <= idx < total:
                    dump_data[idx] = val
    return dump_data.reshape((GRID_H, GRID_W))


def get_output_sim(file_path):
    img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("Warning: Could not read output sim file, returning zeros.")
        return np.zeros((GRID_H, GRID_W), dtype=np.int32)
    # Max-Pooling：每 16×16 區塊取最大值（與主程式 process_local_dimming 一致）
    tiles = img[:GRID_H * BLOCK_H, :GRID_W * BLOCK_W].reshape(GRID_H, BLOCK_H, GRID_W, BLOCK_W)
    return tiles.max(axis=(1, 3)).astype(np.int32)


def visualize_diff(dump_path, output_path, result_path):
    dump_arr = parse_dump(dump_path)
    sim_arr = get_output_sim(output_path)

    vis_img = np.zeros((GRID_H, GRID_W, 3), dtype=np.uint8)

    # 以模擬為準與 Dump 比對（與主程式 visualize_diff 邏輯一致）
    both_on = (dump_arr > 0) & (sim_arr > 0)
    missing  = (dump_arr == 0) & (sim_arr > 0)   # 漏亮：模擬有、Dump 沒
    extra    = (dump_arr > 0) & (sim_arr == 0)   # 多亮：模擬沒、Dump 有

    vis_img[both_on] = (255, 255, 255)   # 白：兩者皆亮
    vis_img[missing] = (0, 0, 255)       # 紅：漏亮
    vis_img[extra]   = (255, 0, 0)       # 藍：多亮

    diff_count = int(np.sum(missing) + np.sum(extra))

    vis_img_large = cv2.resize(vis_img, (1280, 640), interpolation=cv2.INTER_NEAREST)

    cv2.putText(vis_img_large, "Legend:", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(vis_img_large, "Red  : 漏亮 (sim ON, dump OFF)", (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(vis_img_large, "Blue : 多亮 (sim OFF, dump ON)", (20, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    cv2.putText(vis_img_large, "White: 正常點亮 (both ON)", (20, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.imwrite(result_path, vis_img_large)
    return diff_count

if __name__ == "__main__":
    dp = r"c:\Users\erichsu\.gemini\antigravity\playground\0.txt"
    op = r"c:\Users\erichsu\.gemini\antigravity\playground\dummy_output.png"
    rp = r"c:\Users\erichsu\.gemini\antigravity\playground\diff_result.png"
    
    diffs = visualize_diff(dp, op, rp)
    print(f"Visualization generated: {rp}")
    print(f"Total disparate blocks: {diffs}")
