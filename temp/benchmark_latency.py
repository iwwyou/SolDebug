"""
SolQDebug Latency Benchmark Script

This script measures the latency of SolQDebug on annotation files with varying input ranges,
and compares against Remix debugging performance.
"""

import json
import glob
import csv
import time
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers


class LatencyBenchmark:
    def __init__(self, annotation_dir: str, remix_csv: str, output_csv: str):
        self.annotation_dir = Path(annotation_dir)
        self.remix_csv = Path(remix_csv)
        self.output_csv = Path(output_csv)
        self.remix_data = self._load_remix_data()

    def _load_remix_data(self) -> Dict[Tuple[str, str], Dict]:
        """Load Remix benchmark results and index by (contract, function)"""
        remix_dict = {}
        with open(self.remix_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                contract = row['contract_name']
                function = row['function_name']
                key = (contract, function)
                remix_dict[key] = {
                    'byteop_count': row['byteop_count'],
                    'pure_debug_ms': row['pure_debug_time_ms'],
                    'total_ms': row['total_time_ms']
                }
        return remix_dict

    def _extract_contract_and_function(self, records: List[Dict]) -> Tuple[Optional[str], Optional[str]]:
        """Extract contract name and function name from JSON records"""
        contract_name = None
        function_name = None

        for rec in records:
            code = rec['code'].strip()

            # Extract contract name
            if code.startswith('contract '):
                match = re.match(r'contract\s+(\w+)', code)
                if match:
                    contract_name = match.group(1)

            # Extract function name
            if code.startswith('function '):
                match = re.match(r'function\s+(\w+)', code)
                if match:
                    function_name = match.group(1)

        return contract_name, function_name

    def _modify_interval_values(self, records: List[Dict], delta: int) -> List[Dict]:
        """
        Modify [min, max] interval values to [min, max + delta]
        Leaves symbolicAddress, arrayAddress, and arrays unchanged
        """
        modified_records = []

        for rec in records.copy():
            code = rec['code']

            # Check if this is a debugging annotation with interval
            if code.strip().startswith('// @'):
                # Pattern: // @StateVar xxx = [min, max];
                pattern = r'(// @\w+\s+\w+(?:\.\w+)*\s*=\s*)\[(\d+),\s*(\d+)\]'
                match = re.search(pattern, code)

                if match:
                    # Increase max value by delta
                    prefix = match.group(1)
                    min_val = int(match.group(2))
                    original_max = int(match.group(3))
                    new_max = original_max + delta
                    new_code = re.sub(pattern, f'{prefix}[{min_val},{new_max}]', code)
                    rec = rec.copy()
                    rec['code'] = new_code

            modified_records.append(rec)

        return modified_records

    def _simulate_inputs(self, records: List[Dict]) -> float:
        """
        Run the SolQDebug analyzer on the given records and measure latency
        Returns latency in milliseconds
        """
        contract_analyzer = ContractAnalyzer()
        snapman = contract_analyzer.snapman
        batch_mgr = DebugBatchManager(contract_analyzer, snapman)
        in_testcase = False

        start_time = time.time()

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
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        return latency_ms

    def run_benchmark(self):
        """Run the full benchmark across all annotation files"""
        results = []
        annotation_files = sorted(self.annotation_dir.glob('*_annot.json'))

        print(f"Found {len(annotation_files)} annotation files")
        print(f"Testing with input ranges: [min, 0], [min, 2], [min, 5], [min, 10]")
        print("=" * 80)

        for annot_file in annotation_files:
            print(f"\nProcessing: {annot_file.name}")

            # Extract .sol filename (remove _c_annot.json)
            sol_name = annot_file.stem.replace('_annot', '').replace('_c', '')

            # Load JSON
            with open(annot_file, 'r', encoding='utf-8') as f:
                records = json.load(f)

            # Extract contract and function names
            contract_name, function_name = self._extract_contract_and_function(records)

            if not contract_name or not function_name:
                print(f"  [SKIP] Could not extract contract/function name")
                continue

            print(f"  Contract: {contract_name}, Function: {function_name}")

            # Get Remix data
            remix_key = (contract_name, function_name)
            remix_info = self.remix_data.get(remix_key)

            if not remix_info:
                print(f"  [WARN] No matching Remix data found")
                byteop_count = "N/A"
                remix_pure_base = None
                remix_total_base = None
            else:
                byteop_count = remix_info['byteop_count']
                remix_pure_base = float(remix_info['pure_debug_ms'])
                remix_total_base = float(remix_info['total_ms'])

            # Test with different max values: 0, 2, 5, 10
            for max_val in [0, 2, 5, 10]:
                print(f"  Testing with input_range max={max_val}...", end=' ')

                # Modify intervals
                modified_records = self._modify_interval_values(records, max_val)

                # Measure latency
                try:
                    latency_ms = self._simulate_inputs(modified_records)
                    print(f"[OK] {latency_ms:.2f} ms")

                    # Remix time scales with input range (minimum 1)
                    range_multiplier = max(max_val, 1)
                    if remix_pure_base is not None:
                        remix_pure = f"{remix_pure_base * range_multiplier:.2f}"
                        remix_total = f"{remix_total_base * range_multiplier:.2f}"
                    else:
                        remix_pure = "N/A"
                        remix_total = "N/A"

                    results.append({
                        'Contract': sol_name,
                        'Function': function_name,
                        'ByteOp_Count': byteop_count,
                        'Input_Range': max_val,
                        'SolQDebug_Latency_ms': f"{latency_ms:.2f}",
                        'Remix_PureDebug_ms': remix_pure,
                        'Remix_Total_ms': remix_total
                    })
                except Exception as e:
                    print(f"[ERROR] {e}")

        # Write results to CSV
        print("\n" + "=" * 80)
        print(f"Writing results to: {self.output_csv}")

        with open(self.output_csv, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['Contract', 'Function', 'ByteOp_Count', 'Input_Range',
                         'SolQDebug_Latency_ms', 'Remix_PureDebug_ms', 'Remix_Total_ms']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"[DONE] Benchmark complete! Total measurements: {len(results)}")


def main():
    # Configuration
    ANNOTATION_DIR = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\dataset\json\annotation"
    REMIX_CSV = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\Evaluation\Remix\remix_benchmark_results.csv"
    OUTPUT_CSV = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\Evaluation\soldebug_benchmark_results.csv"

    benchmark = LatencyBenchmark(ANNOTATION_DIR, REMIX_CSV, OUTPUT_CSV)
    benchmark.run_benchmark()


if __name__ == "__main__":
    main()
