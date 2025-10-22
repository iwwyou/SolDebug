"""
Test missing contracts individually
"""
import json
import time
import re
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers


def extract_contract_and_function(records):
    contract_name = None
    function_name = None
    for rec in records:
        code = rec['code'].strip()
        if code.startswith('contract '):
            match = re.match(r'contract\s+(\w+)', code)
            if match:
                contract_name = match.group(1)
        if code.startswith('function '):
            match = re.match(r'function\s+(\w+)', code)
            if match:
                function_name = match.group(1)
    return contract_name, function_name


def simulate_inputs(records):
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)
    in_testcase = False

    start_time = time.time()

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)
        stripped = code.lstrip()

        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False
            continue

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

        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

    end_time = time.time()
    return (end_time - start_time) * 1000


# Test missing files
missing_files = [
    'Lock_c_annot.json',
    'LockupContract_c_annot.json',
    'PoolKeeper_c_annot.json',
    'ThorusBond_c_annot.json'
]

for filename in missing_files:
    filepath = f'dataset/json/annotation/{filename}'

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            records = json.load(f)

        contract, function = extract_contract_and_function(records)
        print(f'\n{filename}:')
        print(f'  Contract: {contract}, Function: {function}')

        latency = simulate_inputs(records)
        print(f'  Latency: {latency:.2f} ms')
        print(f'  Status: SUCCESS')

    except Exception as e:
        print(f'\n{filename}:')
        print(f'  ERROR: {e}')
