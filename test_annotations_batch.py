#!/usr/bin/env python3
"""
Batch test all annotation files and measure latency and analyze errors.
"""

import json
import time
import traceback
from pathlib import Path
from typing import Dict, List, Any, Tuple
import sys
import os

# Add the current directory to Python path to import modules
sys.path.append(os.getcwd())

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

def simulate_inputs(records: List[Dict]) -> Tuple[float, str, Any]:
    """
    Simulate inputs like test.py and return execution time, error info, and result.

    Returns:
        Tuple of (execution_time, error_message, analysis_result)
    """
    start_time = time.time()
    error_message = ""
    analysis_result = None

    try:
        # Initialize components
        contract_analyzer = ContractAnalyzer()
        snapman = contract_analyzer.snapman
        batch_mgr = DebugBatchManager(contract_analyzer, snapman)

        in_testcase = False
        all_analyses = []

        for rec in records:
            code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]

            # Update contract analyzer
            contract_analyzer.update_code(s, e, code, ev)

            stripped = code.lstrip()

            # Handle @Debugging BEGIN/END
            if stripped.startswith("// @Debugging BEGIN"):
                batch_mgr.reset()
                in_testcase = True
                continue

            if stripped.startswith("// @Debugging END"):
                batch_mgr.flush()
                in_testcase = False
                continue

            # Handle debug comments (@StateVar, @GlobalVar, etc.)
            if stripped.startswith("//") and ("@StateVar" in stripped or "@GlobalVar" in stripped or "@LocalVar" in stripped):
                if ev == "add":
                    batch_mgr.add_line(code, s, e)
                elif ev == "modify":
                    batch_mgr.modify_line(code, s, e)
                elif ev == "delete":
                    batch_mgr.delete_line(s)

                # If outside BEGIN-END, flush immediately
                if not in_testcase:
                    batch_mgr.flush()
                continue

            # Handle regular Solidity code
            if code.strip():
                ctx = contract_analyzer.get_current_context_type()
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)

            # Get analysis for this line
            analysis = contract_analyzer.get_line_analysis(s, e)
            if analysis:
                all_analyses.append({
                    'line_range': f"{s}-{e}",
                    'analysis': analysis
                })

        analysis_result = all_analyses

    except Exception as e:
        error_message = f"{type(e).__name__}: {str(e)}"
        # Optional: include traceback for debugging
        # error_message += f"\nTraceback: {traceback.format_exc()}"

    end_time = time.time()
    execution_time = end_time - start_time

    return execution_time, error_message, analysis_result

def test_single_annotation_file(json_file_path: str) -> Dict[str, Any]:
    """
    Test a single annotation JSON file.

    Returns:
        Dictionary with test results
    """
    filename = os.path.basename(json_file_path)

    try:
        # Load JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            test_inputs = json.load(f)

        # Run simulation
        execution_time, error_message, analysis_result = simulate_inputs(test_inputs)

        result = {
            'filename': filename,
            'status': 'SUCCESS' if not error_message else 'ERROR',
            'execution_time': execution_time,
            'error_message': error_message,
            'num_records': len(test_inputs),
            'analysis_count': len(analysis_result) if analysis_result else 0,
            'analysis_result': analysis_result
        }

    except Exception as e:
        result = {
            'filename': filename,
            'status': 'LOAD_ERROR',
            'execution_time': 0.0,
            'error_message': f"Failed to load file: {type(e).__name__}: {str(e)}",
            'num_records': 0,
            'analysis_count': 0
        }

    return result

def categorize_errors(results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Categorize errors by error type.

    Returns:
        Dictionary mapping error types to list of filenames
    """
    error_categories = {}

    for result in results:
        if result['status'] in ['ERROR', 'LOAD_ERROR']:
            error_msg = result['error_message']

            # Extract error type (first part before colon)
            if ':' in error_msg:
                error_type = error_msg.split(':')[0].strip()
            else:
                error_type = error_msg.strip()

            if error_type not in error_categories:
                error_categories[error_type] = []

            error_categories[error_type].append(result['filename'])

    return error_categories

def print_results_summary(results: List[Dict[str, Any]]):
    """Print a summary of test results."""

    total_files = len(results)
    successful = len([r for r in results if r['status'] == 'SUCCESS'])
    errors = len([r for r in results if r['status'] in ['ERROR', 'LOAD_ERROR']])

    total_time = sum(r['execution_time'] for r in results)
    avg_time = total_time / total_files if total_files > 0 else 0

    print("=" * 80)
    print("BATCH TEST RESULTS SUMMARY")
    print("=" * 80)
    print(f"Total files tested: {total_files}")
    print(f"Successful: {successful}")
    print(f"Errors: {errors}")
    print(f"Success rate: {(successful/total_files)*100:.1f}%")
    print(f"Total execution time: {total_time:.3f} seconds")
    print(f"Average execution time: {avg_time:.3f} seconds")
    print()

def print_detailed_results(results: List[Dict[str, Any]]):
    """Print detailed results for each file."""

    print("DETAILED RESULTS BY FILE")
    print("=" * 80)

    # Sort by status (SUCCESS first, then by execution time)
    sorted_results = sorted(results, key=lambda x: (x['status'] != 'SUCCESS', x['execution_time']))

    for result in sorted_results:
        status_icon = "OK" if result['status'] == 'SUCCESS' else "ER"
        print(f"{status_icon} {result['filename']:<35} | "
              f"{result['status']:<12} | "
              f"{result['execution_time']:.3f}s | "
              f"Records: {result['num_records']:<3} | "
              f"Analyses: {result['analysis_count']:<3}")

        if result['error_message']:
            print(f"   Error: {result['error_message']}")
        print()

def print_error_categories(error_categories: Dict[str, List[str]]):
    """Print error categories analysis."""

    if not error_categories:
        print("No errors found!")
        return

    print("ERROR ANALYSIS BY CATEGORY")
    print("=" * 80)

    # Sort by frequency
    sorted_categories = sorted(error_categories.items(), key=lambda x: len(x[1]), reverse=True)

    for error_type, filenames in sorted_categories:
        print(f"\n{error_type} ({len(filenames)} files):")
        print("-" * 50)
        for filename in sorted(filenames):
            print(f"  - {filename}")

def main():
    """Main function to run batch tests."""

    print("Starting batch test of annotation files...")
    print()

    # Find all annotation JSON files
    annotation_dir = Path("dataset/json/annotation")
    annotation_files = list(annotation_dir.glob("*_annot.json"))

    if not annotation_files:
        print(f"No annotation files found in {annotation_dir}")
        return

    print(f"Found {len(annotation_files)} annotation files to test")
    print()

    # Test each file
    results = []
    for i, json_file in enumerate(annotation_files, 1):
        print(f"Testing {i}/{len(annotation_files)}: {json_file.name}")
        result = test_single_annotation_file(str(json_file))
        results.append(result)

        # Print immediate result
        status_icon = "OK" if result['status'] == 'SUCCESS' else "ERROR"

        # Print analysis results if successful
        if result['status'] == 'SUCCESS' and result.get('analysis_result'):
            print("\n=======  ANALYSIS  =======")
            for analysis_item in result['analysis_result']:
                line_range = analysis_item['line_range']
                analysis = analysis_item['analysis']
                for ln, records in analysis.items():
                    for rec in records:
                        kind = rec.get("kind", "?")
                        vars_ = rec.get("vars", {})
                        print(f"{ln:4} │ {kind:<14} │ {vars_}")
            print("==========================\n")

        print(f"  {status_icon} {result['status']} - {result['execution_time']:.3f}s")
        if result['error_message']:
            print(f"    Error: {result['error_message']}")
        print()

    # Print summary and analysis
    print_results_summary(results)
    print_detailed_results(results)

    # Analyze errors
    error_categories = categorize_errors(results)
    print_error_categories(error_categories)

    # Save results to file
    output_file = "batch_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total_files': len(results),
                'successful': len([r for r in results if r['status'] == 'SUCCESS']),
                'errors': len([r for r in results if r['status'] in ['ERROR', 'LOAD_ERROR']]),
                'total_time': sum(r['execution_time'] for r in results),
                'avg_time': sum(r['execution_time'] for r in results) / len(results)
            },
            'results': results,
            'error_categories': error_categories
        }, f, indent=2, ensure_ascii=False)

    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()