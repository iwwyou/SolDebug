#!/usr/bin/env python3
"""
Simple RQ2 experiment runner using existing annotation format
Directly uses dataset/json/annotation/*.json files and modifies annotations
"""
import sys
import json
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

def simulate_inputs(records):
    """From test.py - run analysis on a sequence of records"""
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)

    in_testcase = False
    results = {}

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        # BEGIN / END
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False

            # Collect analysis after flush
            analysis = contract_analyzer.get_line_analysis(s, e)
            if analysis:
                for ln, recs in analysis.items():
                    if ln not in results:
                        results[ln] = []
                    results[ln].extend(recs)
            continue

        # Debug annotations
        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            if not in_testcase:
                batch_mgr.flush()
            continue

        # Regular Solidity code
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            try:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)
            except Exception as ex:
                pass  # Ignore parse errors for incremental input

        # Collect intermediate results
        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            for ln, recs in analysis.items():
                if ln not in results:
                    results[ln] = []
                results[ln].extend(recs)

    return results

def modify_annotation_intervals(base_annot: List[Dict], delta: int, pattern: str) -> List[Dict]:
    """
    Modify interval ranges in annotation based on delta and pattern
    Finds all @StateVar/@LocalVar/@GlobalVar lines and updates ranges
    """
    modified = []

    var_count = 0
    for rec in base_annot:
        code = rec["code"]
        stripped = code.lstrip()

        # Check if it's a variable annotation
        if stripped.startswith("// @StateVar") or stripped.startswith("// @LocalVar") or stripped.startswith("// @GlobalVar"):
            # Extract pattern: // @XxxVar name = [low,high];
            import re
            match = re.match(r'(// @\w+Var\s+[\w.\[\]]+\s*=\s*)\[(\d+),(\d+)\]', code)
            if match:
                prefix = match.group(1)
                old_low, old_high = int(match.group(2)), int(match.group(3))

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

def run_single_experiment(base_annot_file: Path, delta: int, pattern: str) -> Dict:
    """
    Run single experiment with specified delta and pattern
    Returns dict with results and metrics
    """
    # Load base annotation
    with open(base_annot_file, 'r', encoding='utf-8') as f:
        base_annot = json.load(f)

    # Modify annotation intervals
    modified_annot = modify_annotation_intervals(base_annot, delta, pattern)

    # Run experiment
    start_time = time.time()
    results = simulate_inputs(modified_annot)
    end_time = time.time()

    return {
        'base_file': str(base_annot_file),
        'delta': delta,
        'pattern': pattern,
        'execution_time': end_time - start_time,
        'results': results,
        'num_variables': sum(1 for r in modified_annot if '// @' in r['code'] and 'Var ' in r['code']),
        'success': True
    }

def extract_intervals(results: Dict, debug_print=False) -> Dict:
    """Extract interval bounds from results"""
    import re
    intervals = {}
    MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935

    for line_num, records in results.items():
        for rec in records:
            # Debug: print all record information to understand structure
            if debug_print:
                print(f"  [DEBUG] Line {line_num}")
                print(f"    rec keys: {rec.keys()}")
                print(f"    type: {rec.get('type')}")
                if 'vars' in rec:
                    print(f"    vars keys: {list(rec.get('vars', {}).keys())}")

            vars_info = rec.get('vars', {})
            for var_name, var_data in vars_info.items():
                # Handle both dict format and string format
                if isinstance(var_data, dict):
                    interval = var_data.get('interval')
                    if interval and isinstance(interval, (list, tuple)) and len(interval) == 2:
                        low, high = interval
                elif isinstance(var_data, str):
                    # Parse string format like '[0,83]' or '[None,None]'
                    match = re.match(r'\[([^,]+),([^]]+)\]', var_data)
                    if match:
                        low_str, high_str = match.group(1), match.group(2)
                        try:
                            low = int(low_str) if low_str != 'None' else None
                            high = int(high_str) if high_str != 'None' else None
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    continue

                # Check if interval is finite
                if low is None or high is None:
                    width = float('inf')
                    finite = False
                elif high >= MAX_UINT256:
                    # Treat MAX_UINT256 as infinite (divergence)
                    width = float('inf')
                    finite = False
                else:
                    width = high - low
                    finite = True

                intervals[var_name] = {
                    'low': low,
                    'high': high,
                    'width': width,
                    'finite': finite,
                    'line': line_num
                }

    return intervals

# Test with Lock_c
if __name__ == "__main__":
    print("Testing simple RQ2 experiment runner...")
    print("=" * 70)

    base_annot = Path("dataset/json/annotation/Lock_c_annot.json")

    if not base_annot.exists():
        print(f"Error: {base_annot} not found")
        sys.exit(1)

    # Run experiments with different delta and pattern
    for delta in [1, 3, 6]:
        for pattern in ["overlap", "diff"]:
            print(f"\n[Experiment] Delta={delta}, Pattern={pattern}")

            try:
                result = run_single_experiment(base_annot, delta, pattern)

                print(f"  Execution time: {result['execution_time']:.3f}s")
                print(f"  Variables: {result['num_variables']}")

                intervals = extract_intervals(result['results'])
                print(f"  Output intervals: {len(intervals)}")

                for var, data in list(intervals.items())[:5]:  # Show first 5
                    if data['finite']:
                        print(f"    {var}: [{data['low']}, {data['high']}] width={data['width']}")
                    else:
                        print(f"    {var}: [{data['low']}, {data['high']}] INFINITE")

            except Exception as e:
                print(f"  [ERROR] {e}")
                import traceback
                traceback.print_exc()

    print("\n" + "=" * 70)
    print("[DONE]")
