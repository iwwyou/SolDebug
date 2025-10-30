#!/usr/bin/env python3
"""
Run a single RQ2 experiment
Similar structure to test.py but automated for batch execution
"""
import sys
import json
import time
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

def load_contract_json(sol_file: Path) -> List[Dict]:
    """
    Convert .sol file to JSON format expected by test.py
    Each line becomes a record
    """
    lines = sol_file.read_text(encoding='utf-8').split('\n')
    records = []

    for i, line in enumerate(lines, start=1):
        # Handle empty lines
        if not line.strip():
            records.append({
                "code": "\n",
                "startLine": i,
                "endLine": i,
                "event": "add"
            })
        else:
            # Check if it's a multi-line construct
            if line.strip().endswith('{'):
                # Add closing brace indicator
                records.append({
                    "code": line + "\n}",
                    "startLine": i,
                    "endLine": i + 1,
                    "event": "add"
                })
            else:
                records.append({
                    "code": line,
                    "startLine": i,
                    "endLine": i,
                    "event": "add"
                })

    return records

def load_annotation_json(annot_file: Path) -> List[Dict]:
    """Load annotation JSON file"""
    with open(annot_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_experiment(
    contract_records: List[Dict],
    annotation_records: List[Dict],
    verbose: bool = False
) -> Dict:
    """
    Run single experiment and collect results
    Returns analysis results
    """
    # Initialize analyzer
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)

    in_testcase = False
    results = {}

    # Combine contract and annotation records
    all_records = contract_records + annotation_records

    start_time = time.time()

    for idx, rec in enumerate(all_records):
        code = rec["code"]
        s, e = rec["startLine"], rec["endLine"]
        ev = rec["event"]

        # Update contract source
        contract_analyzer.update_code(s, e, code, ev)

        if verbose:
            print(f"[{s}] {code[:60]}...")

        stripped = code.lstrip()

        # Handle @Debugging markers
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False

            # Collect results after flush
            analysis = contract_analyzer.get_line_analysis(s, e)
            if analysis:
                results['final_analysis'] = analysis
            continue

        # Handle annotation comments
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

        # Handle regular Solidity code
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            try:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)
            except Exception as e:
                if verbose:
                    print(f"[WARNING] Parse error at line {s}: {e}")

        # Collect intermediate analysis
        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            for ln, recs in analysis.items():
                if ln not in results:
                    results[ln] = []
                results[ln].extend(recs)

    end_time = time.time()

    return {
        'results': results,
        'execution_time': end_time - start_time,
        'success': True
    }

def extract_intervals_from_results(results: Dict) -> Dict:
    """
    Extract interval information from analysis results
    Returns dict of variable -> (low, high)
    """
    intervals = {}

    for line_num, records in results.items():
        if line_num == 'final_analysis':
            continue

        for rec in records:
            vars_info = rec.get('vars', {})
            for var_name, var_data in vars_info.items():
                if isinstance(var_data, dict) and 'interval' in var_data:
                    interval = var_data['interval']
                    if isinstance(interval, (list, tuple)) and len(interval) == 2:
                        intervals[var_name] = {
                            'low': interval[0],
                            'high': interval[1],
                            'line': line_num,
                            'kind': rec.get('kind', 'unknown')
                        }

    return intervals

if __name__ == "__main__":
    # Test with Lock_c
    print("Testing single experiment execution...")

    contract_file = Path("dataset/contraction/Lock_c.sol")
    annot_file = Path("Evaluation/RQ2_Extended_v2/Lock_c_pending_sub_to_add_d3_overlap.json")

    if not contract_file.exists():
        print(f"Error: {contract_file} not found")
        sys.exit(1)

    if not annot_file.exists():
        print(f"Error: {annot_file} not found")
        sys.exit(1)

    print(f"Loading contract: {contract_file}")
    contract_records = load_contract_json(contract_file)
    print(f"  Loaded {len(contract_records)} lines")

    print(f"Loading annotation: {annot_file}")
    annotation_records = load_annotation_json(annot_file)
    print(f"  Loaded {len(annotation_records)} annotations")

    print("Running experiment...")
    result = run_experiment(contract_records, annotation_records, verbose=True)

    print(f"\n{'='*60}")
    print(f"Execution time: {result['execution_time']:.3f}s")
    print(f"Success: {result['success']}")

    intervals = extract_intervals_from_results(result['results'])
    print(f"\nExtracted intervals: {len(intervals)}")
    for var, data in intervals.items():
        print(f"  {var}: [{data['low']}, {data['high']}] at line {data['line']}")
