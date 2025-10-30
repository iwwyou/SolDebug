#!/usr/bin/env python3
"""
Full RQ2 experiments with actual operator mutations
Runs all 480 experiments from experiment_index.json
"""
import sys
import json
import csv
import time
import re
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_rq2_simple import simulate_inputs, extract_intervals

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
EXPERIMENT_INDEX = SCRIPT_DIR / "RQ2_Extended_v2/experiment_index.json"
ANNOTATION_DIR = PROJECT_ROOT / "dataset/json/annotation"
CONTRACT_DIR = PROJECT_ROOT / "dataset/contraction"
RESULTS_DIR = SCRIPT_DIR / "RQ2_Results_Full"
OUTPUT_CSV = RESULTS_DIR / "rq2_full_480_results.csv"

def load_experiment_index():
    """Load experiment index"""
    with open(EXPERIMENT_INDEX, 'r', encoding='utf-8') as f:
        return json.load(f)

def apply_mutation_to_line(line: str, mutation_type: str) -> str:
    """
    Apply operator mutation to a single line of code
    """
    if mutation_type == 'sub_to_add':
        # Change - to + (but not --)
        result = re.sub(r'(\w+)\s*-\s*(\w+)', r'\1 + \2', line)
        return result
    elif mutation_type == 'add_to_sub':
        # Change + to - (but not ++)
        result = re.sub(r'(\w+)\s*\+\s*(\w+)', r'\1 - \2', line)
        return result
    elif mutation_type == 'swap_add_sub':
        # Swap all + and -
        # First mark + as @PLUS@ and - as @MINUS@
        temp = line.replace('++', '@PLUSPLUS@').replace('--', '@MINUSMINUS@')
        temp = temp.replace('+', '@PLUS@').replace('-', '@MINUS@')
        # Now swap
        temp = temp.replace('@PLUS@', '-').replace('@MINUS@', '+')
        # Restore ++ and --
        temp = temp.replace('@PLUSPLUS@', '++').replace('@MINUSMINUS@', '--')
        return temp
    elif mutation_type == 'swap_mul_div':
        # Swap * and /
        temp = line.replace('*', '@MUL@').replace('/', '@DIV@')
        temp = temp.replace('@MUL@', '/').replace('@DIV@', '*')
        return temp
    elif mutation_type == 'has_division':
        # No mutation for division test
        return line
    else:
        return line

def create_mutated_annotation(
    base_annot_file: Path,
    mutation_type: str,
    delta: int,
    pattern: str,
    target_function: str
) -> List[Dict]:
    """
    Load base annotation and apply mutation + interval modification
    """
    with open(base_annot_file, 'r', encoding='utf-8') as f:
        base_annot = json.load(f)

    modified = []
    in_target_function = False
    var_count = 0

    for rec in base_annot:
        code = rec["code"]
        stripped = code.lstrip()

        # Track if we're in target function
        if 'function ' + target_function in code:
            in_target_function = True
        elif stripped.startswith('function ') and target_function not in code:
            in_target_function = False

        # Apply mutation to function body (not annotations)
        if in_target_function and not stripped.startswith('//'):
            # Check if this line has operators
            if any(op in code for op in ['+', '-', '*', '/']):
                mutated_code = apply_mutation_to_line(code, mutation_type)
                modified.append({**rec, "code": mutated_code})
                continue

        # Modify annotation intervals
        if stripped.startswith("// @StateVar") or stripped.startswith("// @LocalVar") or stripped.startswith("// @GlobalVar"):
            match = re.match(r'(// @\w+Var\s+[\w.\[\]]+\s*=\s*)\[(\d+),(\d+)\]', code)
            if match:
                prefix = match.group(1)

                # Generate new range based on pattern
                if pattern == "overlap":
                    new_low, new_high = 100, 100 + delta
                else:  # diff
                    new_low = 100 + var_count * (delta + 20)
                    new_high = new_low + delta

                new_code = f"{prefix}[{new_low},{new_high}];"
                modified.append({**rec, "code": new_code})
                var_count += 1
                continue

        # Keep other records as-is
        modified.append(rec)

    return modified

def run_single_mutated_experiment(exp: Dict) -> Dict:
    """
    Run single experiment with mutation applied
    """
    contract = exp['contract']
    function = exp['function']
    mutation = exp['mutation']
    delta = exp['delta']
    pattern = exp['pattern']

    # Find base annotation file
    base_annot_file = ANNOTATION_DIR / f"{contract}_annot.json"

    if not base_annot_file.exists():
        return {
            **exp,
            'success': False,
            'error': f'Annotation file not found: {base_annot_file}'
        }

    try:
        # Create mutated annotation
        mutated_annot = create_mutated_annotation(
            base_annot_file,
            mutation,
            delta,
            pattern,
            function
        )

        # Run experiment
        start_time = time.time()
        results = simulate_inputs(mutated_annot)
        end_time = time.time()

        # Extract intervals
        intervals = extract_intervals(results)

        # Compute metrics
        finite_count = sum(1 for v in intervals.values() if v['finite'])
        infinite_count = len(intervals) - finite_count

        widths = [v['width'] for v in intervals.values() if v['finite']]
        avg_width = sum(widths) / len(widths) if widths else float('inf')
        max_width = max(widths) if widths else float('inf')

        # F90
        if widths:
            widths_sorted = sorted(widths)
            f90_idx = int(len(widths_sorted) * 0.9)
            f90 = widths_sorted[f90_idx] if f90_idx < len(widths_sorted) else widths_sorted[-1]
        else:
            f90 = float('inf')

        return {
            **exp,
            'execution_time': end_time - start_time,
            'num_intervals': len(intervals),
            'finite_count': finite_count,
            'infinite_count': infinite_count,
            'avg_width': avg_width,
            'max_width': max_width,
            'f90': f90,
            'success': True
        }

    except Exception as e:
        return {
            **exp,
            'success': False,
            'error': str(e),
            'execution_time': 0
        }

def main():
    print("=" * 70)
    print("RQ2 FULL EXPERIMENT RUNNER (480 experiments with mutations)")
    print("=" * 70)

    # Load experiment index
    index_data = load_experiment_index()
    experiments = index_data['experiments']

    print(f"\nTotal experiments to run: {len(experiments)}")
    print(f"This includes operator mutations!")

    RESULTS_DIR.mkdir(exist_ok=True)

    # Run experiments
    all_results = []
    success_count = 0
    fail_count = 0

    for i, exp in enumerate(experiments):
        exp_id = f"{exp['contract']}.{exp['function']}.{exp['mutation']}_d{exp['delta']}_{exp['pattern']}"

        print(f"[{i+1}/{len(experiments)}] {exp_id}...", end=" ", flush=True)

        result = run_single_mutated_experiment(exp)
        all_results.append(result)

        if result['success']:
            success_count += 1
            f90 = result['f90']
            f90_str = f"{f90:.1f}" if f90 != float('inf') else "inf"
            print(f"OK (F90={f90_str})")
        else:
            fail_count += 1
            error_msg = result.get('error', 'Unknown error')[:50]
            print(f"FAIL: {error_msg}")

        # Save intermediate results every 50 experiments
        if (i + 1) % 50 == 0:
            print(f"\n[CHECKPOINT] Saving intermediate results ({i+1}/{len(experiments)})...")
            with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
                if all_results:
                    fieldnames = list(all_results[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(all_results)

    # Final save
    print(f"\n{'='*70}")
    print(f"Saving final results to {OUTPUT_CSV}...")

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        if all_results:
            fieldnames = list(all_results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)

    print(f"[DONE] Saved {len(all_results)} results")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {len(experiments)}")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

    if success_count > 0:
        # Quick analysis
        successful = [r for r in all_results if r['success']]

        overlap_results = [r for r in successful if r['pattern'] == 'overlap']
        diff_results = [r for r in successful if r['pattern'] == 'diff']

        overlap_finite = [r for r in overlap_results if r['f90'] != float('inf')]
        diff_finite = [r for r in diff_results if r['f90'] != float('inf')]

        print(f"\nPattern comparison:")
        print(f"  Overlap: {len(overlap_finite)}/{len(overlap_results)} finite")
        print(f"  Diff: {len(diff_finite)}/{len(diff_results)} finite")

        if overlap_finite and diff_finite:
            avg_overlap = sum(r['f90'] for r in overlap_finite) / len(overlap_finite)
            avg_diff = sum(r['f90'] for r in diff_finite) / len(diff_finite)

            print(f"\nF90 averages:")
            print(f"  Overlap: {avg_overlap:.2f}")
            print(f"  Diff: {avg_diff:.2f}")
            print(f"  Ratio: {avg_diff/avg_overlap:.2f}x")

if __name__ == "__main__":
    start = time.time()
    main()
    end = time.time()
    print(f"\nTotal execution time: {end - start:.2f}s")
