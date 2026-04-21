import sys
import subprocess
import os
import re
import argparse
import logging
from datetime import datetime

try:
    import cv2
    import numpy as np
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python", "numpy"])
    import cv2
    import numpy as np

GRID_H, GRID_W = 40, 80
BLOCK_H, BLOCK_W = 16, 16


def setup_logging(log_dir):
    """設定日誌系統，同時輸出至終端機與帶時間戳的日誌檔。"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"local_dimming_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    logger = logging.getLogger("local_dimming")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info(f"Log file: {log_file}")
    return logger


def process_local_dimming(img):
    """
    將 1280x640 灰階影像轉換為 40x80 的 Max-Pooling 網格。
    每個格子儲存對應 16x16 區塊內的最大像素值。
    """
    h, w = img.shape
    sim_data = np.zeros((GRID_H, GRID_W), dtype=np.int32)
    for y in range(0, h, BLOCK_H):
        for x in range(0, w, BLOCK_W):
            block = img[y:y + BLOCK_H, x:x + BLOCK_W]
            max_val = np.max(block)
            if max_val > 0:
                sim_data[y // BLOCK_H, x // BLOCK_W] = int(max_val)
    return sim_data


def parse_dump(file_path, logger):
    """
    解析含有 3200 筆索引資料的硬體 Dump txt 檔。
    成功時回傳 (40, 80) int32 陣列，失敗時回傳 None。
    """
    dump_data = np.zeros(3200, dtype=np.int32)
    entries_found = 0
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(r'\[(\d+)\]\s+(\d+)', line)
            if match:
                idx = int(match.group(1))
                val = int(match.group(2))
                if 0 <= idx < 3200:
                    dump_data[idx] = val
                    entries_found += 1
                else:
                    logger.warning(f"  Dump 索引 {idx} 超出範圍 [0, 3200)：{file_path}")

    if entries_found == 0:
        logger.error(f"  Dump 檔中找不到有效資料：{file_path}")
        return None
    if entries_found != 3200:
        logger.warning(f"  Dump 預期 3200 筆，實際讀取 {entries_found} 筆：{file_path}")

    return dump_data.reshape((GRID_H, GRID_W))


def parse_zones(file_path, logger):
    """
    解析 zone.txt，回傳 {case_id: (j_start, j_end, i_start, i_end)} 字典。
    驗證所有座標是否在網格範圍內。
    檔案不存在時回傳 None。
    """
    if not os.path.exists(file_path):
        logger.error(f"找不到 zone.txt：{file_path}")
        return None

    zones = {}
    current_case = -1
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            case_match = re.search(r'case\s+(\d+):', line)
            if case_match:
                current_case = int(case_match.group(1))

            params_match = re.search(
                r'j_start\s*=\s*(\d+).*?j_end\s*=\s*(\d+).*?i_start\s*=\s*(\d+).*?i_end\s*=\s*(\d+)', line
            )
            if params_match and current_case != -1:
                j_s, j_e, i_s, i_e = map(int, params_match.groups())

                # 驗證座標邊界
                if j_s < 0 or j_e > GRID_H or i_s < 0 or i_e > GRID_W:
                    logger.warning(
                        f"  Zone case {current_case} 座標 ({j_s},{j_e},{i_s},{i_e}) "
                        f"超出網格 {GRID_H}x{GRID_W}，評估時將自動截斷"
                    )
                if j_s >= j_e or i_s >= i_e:
                    logger.warning(
                        f"  Zone case {current_case} 面積為零或負值 "
                        f"(j:{j_s}-{j_e}, i:{i_s}-{i_e})，跳過此燈區"
                    )
                    continue

                zones[current_case] = (j_s, j_e, i_s, i_e)

    logger.debug(f"  已從 {file_path} 解析 {len(zones)} 個燈區")
    return zones


def parse_led_dump(file_path, num_cases, logger):
    """
    解析 LED 控制 txt 檔，回傳長度為 num_cases 的 int32 陣列，失敗時回傳 None。
    """
    led_data = np.zeros(num_cases, dtype=np.int32)
    if not os.path.exists(file_path):
        logger.warning(f"  找不到 LED 檔案：{file_path}")
        return None

    entries_found = 0
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(r'\[(\d+)\]\s+(\d+)', line)
            if match:
                idx = int(match.group(1))
                val = int(match.group(2))
                if 0 <= idx < num_cases:
                    led_data[idx] = val
                    entries_found += 1
                else:
                    logger.warning(f"  LED 索引 {idx} 超出範圍 [0, {num_cases})：{file_path}")

    if entries_found == 0:
        logger.error(f"  LED 檔中找不到有效資料：{file_path}")
        return None
    if entries_found != num_cases:
        logger.warning(f"  LED 預期 {num_cases} 筆，實際讀取 {entries_found} 筆：{file_path}")

    return led_data


def visualize_diff(dump_arr, sim_arr, result_path, logger):
    """
    產生 1280x640 色彩差異比對圖，比較 Dump 與模擬結果：
      白色 = 兩者皆有訊號（正確）
      紅色 = 僅 Dump 有訊號（模擬漏判）
      藍色 = 僅模擬有訊號（模擬多判）
      黑色 = 兩者皆無訊號（正確）
    回傳不一致的區塊數量。
    """
    vis_img = np.zeros((GRID_H, GRID_W, 3), dtype=np.uint8)
    diff_count = 0

    for y in range(GRID_H):
        for x in range(GRID_W):
            d_val = dump_arr[y, x]
            s_val = sim_arr[y, x]
            if d_val > 0 and s_val > 0:
                vis_img[y, x] = (255, 255, 255)
            elif d_val > 0 and s_val == 0:
                vis_img[y, x] = (0, 0, 255)   # 紅：僅 Dump 有
                diff_count += 1
            elif d_val == 0 and s_val > 0:
                vis_img[y, x] = (255, 0, 0)   # 藍：僅模擬有
                diff_count += 1
            # 否則保持黑色（預設值）

    vis_img_large = cv2.resize(vis_img, (1280, 640), interpolation=cv2.INTER_NEAREST)
    os.makedirs(os.path.dirname(result_path), exist_ok=True)
    cv2.imwrite(result_path, vis_img_large)
    logger.debug(f"  差異圖已儲存：{result_path}")
    return diff_count


def evaluate_zones(sim_data, zones, led_data, case_idx_prefix, logger):
    """
    比較模擬圖預期點亮狀態（sim_data）與實際 LED 狀態（led_data）。
    回傳 (errors, per_zone_results)，其中 per_zone_results 為
    {zone_id, expected_on, actual_on, error_type} 字典的清單，供彙整報告使用。
    """
    logger.info(f"\n[{case_idx_prefix}] --- 燈區 (Zone) 點亮比對報告 ---")
    expected_on_list = []
    actual_on_list = []
    errors = 0
    per_zone_results = []

    for case_id in sorted(zones.keys()):
        j_s, j_e, i_s, i_e = zones[case_id]

        zone_block = sim_data[max(0, j_s):min(GRID_H, j_e), max(0, i_s):min(GRID_W, i_e)]
        expected_on = bool(np.any(zone_block > 0))
        actual_on = bool(led_data[case_id] > 0)

        if expected_on:
            expected_on_list.append(case_id)
        if actual_on:
            actual_on_list.append(case_id)

        error_type = None
        if expected_on and not actual_on:
            status_msg = "[ERROR] [漏亮] 模擬圖判定該亮，但實際未亮"
            error_type = "漏亮"
            errors += 1
        elif not expected_on and actual_on:
            status_msg = "[ERROR] [錯亮] 模擬圖判定不該亮，但實際亮了"
            error_type = "錯亮"
            errors += 1
        elif expected_on and actual_on:
            status_msg = f"[OK] 正常點亮 (Val: {led_data[case_id]})"
        else:
            status_msg = "[OK] 正常熄滅"

        per_zone_results.append({
            "zone_id": case_id,
            "expected_on": expected_on,
            "actual_on": actual_on,
            "error_type": error_type,
        })

        if expected_on or actual_on or error_type:
            exp_str = "ON " if expected_on else "OFF"
            act_str = "ON " if actual_on else "OFF"
            logger.info(f"  Case {case_id:2d}: 預期 {exp_str} | 實際 {act_str} => {status_msg}")

    logger.info(f"\n  總結 -> 各區異常數量: {errors}")
    logger.info(f"  模擬預期點亮的燈區: {expected_on_list}")
    logger.info(f"  實際真實點亮的燈區: {actual_on_list}")
    logger.info("  " + "-" * 50)
    return errors, per_zone_results


def process_single_pair(directory, x, logger):
    """
    處理單一測試組（索引 x）：執行 Block 級差異比對與燈區評估。
    模擬輸出存至 sim_output/，原始輸入影像不會被覆寫。
    回傳 (success, block_diffs, zone_errors, per_zone_results)。
    """
    txt_path  = os.path.join(directory, "dump", f"{x}.txt")
    img_path  = os.path.join(directory, "input", f"input_{x}.png")
    zone_path = os.path.join(directory, "zone.txt")
    led_path  = os.path.join(directory, "LED", f"{x}.txt")

    if not os.path.exists(txt_path):
        logger.warning(f"[{x}] 找不到 Dump 檔: {txt_path}")
        return False, 0, 0, []
    if not os.path.exists(img_path):
        logger.warning(f"[{x}] 找不到測試圖: {img_path}")
        return False, 0, 0, []

    logger.info(f"\n==========================================")
    logger.info(f"[{x}] 開始處理第 {x} 組資料...")

    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.error(f"[{x}] 影像讀取失敗: {img_path}")
        return False, 0, 0, []

    sim_data = process_local_dimming(img)

    # 將模擬輸出存至 sim_output/，絕不覆寫原始輸入影像
    sim_out_dir = os.path.join(directory, "sim_output")
    os.makedirs(sim_out_dir, exist_ok=True)
    sim_out_img = np.zeros_like(img)
    for y in range(GRID_H):
        for x_block in range(GRID_W):
            if sim_data[y, x_block] > 0:
                sim_out_img[y * BLOCK_H:(y + 1) * BLOCK_H, x_block * BLOCK_W:(x_block + 1) * BLOCK_W] = 255
    sim_out_path = os.path.join(sim_out_dir, f"sim_{x}.png")
    cv2.imwrite(sim_out_path, sim_out_img)
    logger.debug(f"[{x}] 模擬輸出已存至：sim_output/sim_{x}.png")

    # Block 級差異比對
    dump_data = parse_dump(txt_path, logger)
    if dump_data is None:
        return False, 0, 0, []

    diff_path = os.path.join(directory, "compare", f"diff_{x}.png")
    diffs = visualize_diff(dump_data, sim_data, diff_path, logger)
    logger.info(f"[{x}] Block 級比對完成 — 誤差區塊: {diffs} -> compare/diff_{x}.png")

    # 燈區評估
    zones = parse_zones(zone_path, logger)
    zone_errors = 0
    per_zone_results = []
    if zones and os.path.exists(led_path):
        led_data = parse_led_dump(led_path, num_cases=len(zones), logger=logger)
        if led_data is not None:
            zone_errors, per_zone_results = evaluate_zones(sim_data, zones, led_data, x, logger)
        else:
            logger.error(f"[{x}] LED Dump 讀取失敗。")
    else:
        logger.warning(f"[{x}] 找不到 zone.txt 或 LED 檔案 (跳過燈區比對)")

    return True, diffs, zone_errors, per_zone_results


def print_aggregate_summary(results, logger):
    """
    列印所有測試組的彙整統計報告。
    results：{case_x, success, block_diffs, zone_errors, per_zone_results} 字典的清單。
    """
    # 各測試組彙整：統計每組內的漏亮/錯亮次數
    group_error_counts: dict[int, dict] = {}
    for r in results:
        cx = r["case_x"]
        lou = sum(1 for zr in r["per_zone_results"] if zr["error_type"] == "漏亮")
        cuo = sum(1 for zr in r["per_zone_results"] if zr["error_type"] == "錯亮")
        group_error_counts[cx] = {"漏亮": lou, "錯亮": cuo, "total": lou + cuo}

    problematic = {g: c for g, c in group_error_counts.items() if c["total"] > 0}
    if problematic:
        logger.info("\n各測試組燈區錯誤次數：")
        logger.info(f"  {'zone':>6}  {'漏亮':>6}  {'錯亮':>6}  {'Total':>6}")
        logger.info("  " + "-" * 34)
        for gid in sorted(group_error_counts):
            c = group_error_counts[gid]
            logger.info(f"  {gid:>6}  {c['漏亮']:>6}  {c['錯亮']:>6}  {c['total']:>6}")
    else:
        logger.info("\n全部測試組均無燈區錯誤！")

    # Block 誤差最多的前五組
    worst_block = sorted(results, key=lambda r: r["block_diffs"], reverse=True)[:5]
    logger.info("\nTop-5 Block 誤差最多的組別：")
    for r in worst_block:
        if r["success"]:
            logger.info(f"  Case {r['case_x']:3d}: {r['block_diffs']} 誤差區塊, {r['zone_errors']} Zone 錯誤")

    logger.info("======================================================\n")


def main():
    parser = argparse.ArgumentParser(description="Local Dimming 自動對位與燈區掃描分析工具")
    parser.add_argument("data_dir", type=str, nargs='?', default=".",
                        help="要掃描對位的根資料夾路徑 (預設為當前目錄)")
    parser.add_argument("-c", "--count", type=int, default=None,
                        help="指定要處理的總組數")
    args = parser.parse_args()

    directory = os.path.abspath(args.data_dir)
    logger = setup_logging(os.path.join(directory, "logs"))

    logger.info("========== Local Dimming 批次處理工具 ==========")
    logger.info(f"工作目錄: {directory}")

    os.makedirs(os.path.join(directory, "compare"), exist_ok=True)

    num_images = args.count
    while num_images is None:
        try:                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              
            user_input = input("請輸入您有幾組圖/Dump資料 (例如輸入 5，將處理 0~4): ")
            num_images = int(user_input.strip())
            if num_images <= 0:
                print("輸入的數字必須大於 0")
                num_images = None
        except ValueError:
            print("請輸入有效的整數！")

    logger.info(f"\n即將處理 {num_images} 組檔案...")

    all_results = []
    for x in range(num_images):
        success, block_diffs, zone_errors, per_zone_results = process_single_pair(directory, x, logger)
        all_results.append({
            "case_x": x,
            "success": success,
            "block_diffs": block_diffs,
            "zone_errors": zone_errors,
            "per_zone_results": per_zone_results,
        })

    success_count = sum(1 for r in all_results if r["success"])
    logger.info(f"\n========== 批次處理結束 ==========")
    logger.info(f"成功處理 {success_count} / {num_images} 組。")

    print_aggregate_summary(all_results, logger)


if __name__ == "__main__":
    main()
