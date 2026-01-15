#!/usr/bin/env python3
"""
Parse ANALYSIS sections from batch log to extract actual interval results
"""
import re
import csv
from pathlib import Path
from typing import Dict, List

LOG_FILE = Path("Evaluation/rq2_batch_full_log.txt")
OUTPUT_CSV = Path("Evaluation/RQ2_Results/rq2_detailed_intervals.csv")

def parse_interval(interval_str):
    """Parse interval string like '[0,3]' or '[None,None]'"""
    match = re.match(r'\[([^,]+),([^]]+)\]', interval_str)
    if not match:
        return None, None

    low_str, high_str = match.groups()

    # Handle None
    if low_str.strip() == 'None':
        low = None
    else:
        try:
            low = int(low_str.strip())
        except:
            low = float(low_str.strip()) if low_str.strip() not in ['inf', '-inf'] else None

    if high_str.strip() == 'None':
        high = None
    else:
        try:
            high = int(high_str.strip())
        except:
            high = float(high_str.strip()) if high_str.strip() not in ['inf', '-inf'] else None

    return low, high

def main():
    if not LOG_FILE.exists():
        print(f"[ERROR] Log file not found: {LOG_FILE}")
        return

    print(f"Parsing {LOG_FILE}...")

    with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()

    # Find all experiment blocks
    # Pattern: [N/90] Contract_dD_Pattern... followed by ANALYSIS section
    exp_pattern = re.compile(
        r'\[(\d+)/90\]\s+(\w+)_d(\d+)_(overlap|diff)\.\.\.\s+.*?'
        r'=======\s+ANALYSIS\s+=======\s+(.*?)'
        r'==========================',
        re.DOTALL
    )

    results = []

    for match in exp_pattern.finditer(log_content):
        exp_num = match.group(1)
        contract = match.group(2)
        delta = int(match.group(3))
        pattern = match.group(4)
        analysis_text = match.group(5)

        # Parse variable intervals from analysis
        # Pattern: varName': '[low,high]'
        var_pattern = re.compile(r"'(\w+)':\s*'(\[[^\]]+\])'")

        intervals = {}
        for var_match in var_pattern.finditer(analysis_text):
            var_name = var_match.group(1)
            interval_str = var_match.group(2)
            low, high = parse_interval(interval_str)

            if low is not None and high is not None:
                width = high - low if high != None and low != None else float('inf')
                finite = width != float('inf') and width < 1e10  # Reasonable threshold

                intervals[var_name] = {
                    'low': low,
                    'high': high,
                    'width': width,
                    'finite': finite
                }

        # Compute metrics
        finite_count = sum(1 for v in intervals.values() if v['finite'])
        total_vars = len(intervals)

        widths = [v['width'] for v in intervals.values() if v['finite']]
        if widths:
            avg_width = sum(widths) / len(widths)
            max_width = max(widths)
            widths_sorted = sorted(widths)
            f90_idx = int(len(widths_sorted) * 0.9)
            f90 = widths_sorted[f90_idx] if f90_idx < len(widths_sorted) else widths_sorted[-1]
        else:
            avg_width = float('inf')
            max_width = float('inf')
            f90 = float('inf')

        results.append({
            'exp_num': exp_num,
            'contract': contract,
            'delta': delta,
            'pattern': pattern,
            'total_vars': total_vars,
            'finite_count': finite_count,
            'avg_width': avg_width,
            'max_width': max_width,
            'f90': f90,
            'variables': ';'.join([f"{k}:{v['width']:.1f}" for k, v in intervals.items() if v['finite']])
        })

    # Save results
    if results:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            fieldnames = list(results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"\n[+] Parsed {len(results)} experiments")
        print(f"[+] Saved to {OUTPUT_CSV}")

        # Quick summary
        print("\n" + "=" * 70)
        print("PARSED RESULTS SUMMARY")
        print("=" * 70)

        overlap_results = [r for r in results if r['pattern'] == 'overlap']
        diff_results = [r for r in results if r['pattern'] == 'diff']

        overlap_finite = [r for r in overlap_results if r['f90'] != float('inf')]
        diff_finite = [r for r in diff_results if r['f90'] != float('inf')]

        print(f"\nOverlap: {len(overlap_finite)}/{len(overlap_results)} with finite F90")
        print(f"Diff: {len(diff_finite)}/{len(diff_results)} with finite F90")

        if overlap_finite:
            avg_overlap_f90 = sum(r['f90'] for r in overlap_finite) / len(overlap_finite)
            print(f"\nOverlap F90 (avg): {avg_overlap_f90:.2f}")

        if diff_finite:
            avg_diff_f90 = sum(r['f90'] for r in diff_finite) / len(diff_finite)
            print(f"Diff F90 (avg): {avg_diff_f90:.2f}")

        if overlap_finite and diff_finite:
            ratio = avg_diff_f90 / avg_overlap_f90
            print(f"\nRatio (diff/overlap): {ratio:.2f}x")
            print(f"=> Overlap is {ratio:.2f}x more precise than Diff")

    else:
        print("[WARNING] No results parsed")

if __name__ == "__main__":
    main()
