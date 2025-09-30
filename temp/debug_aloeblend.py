#!/usr/bin/env python3
"""
Debug AloeBlend_c_annot.json step by step to find exact error location.
"""

import json
import time
import traceback
import sys
import os

# Add the current directory to Python path to import modules
sys.path.append(os.getcwd())

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

def debug_step_by_step():
    """Debug AloeBlend step by step with detailed logging."""

    # Load the annotation file
    with open('dataset/json/annotation/AloeBlend_c_annot.json', 'r', encoding='utf-8') as f:
        test_inputs = json.load(f)

    print("=== DEBUGGING AloeBlend_c_annot.json STEP BY STEP ===")
    print(f"Total records: {len(test_inputs)}")
    print()

    # Initialize components
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)

    in_testcase = False
    step = 0

    for rec in test_inputs:
        step += 1
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]

        print(f"STEP {step}: Processing record")
        print(f"  Lines {s}-{e}: {repr(code)}")
        print(f"  Event: {ev}")

        try:
            # Update contract analyzer
            print("  -> Updating contract analyzer...")
            contract_analyzer.update_code(s, e, code, ev)
            print("  -> Contract analyzer updated successfully")

            stripped = code.lstrip()

            # Handle @Debugging BEGIN/END
            if stripped.startswith("// @Debugging BEGIN"):
                print("  -> Debug BEGIN detected")
                batch_mgr.reset()
                in_testcase = True
                continue

            if stripped.startswith("// @Debugging END"):
                print("  -> Debug END detected")
                batch_mgr.flush()
                in_testcase = False
                continue

            # Handle debug comments (@StateVar, @GlobalVar, etc.)
            if stripped.startswith("//") and ("@StateVar" in stripped or "@GlobalVar" in stripped or "@LocalVar" in stripped):
                print(f"  -> Debug annotation detected: {stripped}")

                try:
                    if ev == "add":
                        print("  -> Adding line to batch manager...")
                        batch_mgr.add_line(code, s, e)
                        print("  -> Line added successfully")
                    elif ev == "modify":
                        print("  -> Modifying line in batch manager...")
                        batch_mgr.modify_line(code, s, e)
                        print("  -> Line modified successfully")
                    elif ev == "delete":
                        print("  -> Deleting line from batch manager...")
                        batch_mgr.delete_line(s)
                        print("  -> Line deleted successfully")

                    # If outside BEGIN-END, flush immediately
                    if not in_testcase:
                        print("  -> Flushing batch manager (outside testcase)...")
                        batch_mgr.flush()
                        print("  -> Batch manager flushed successfully")

                except Exception as e:
                    print(f"  *** ERROR in batch manager operation: {type(e).__name__}: {e}")
                    print(f"  *** Traceback: {traceback.format_exc()}")
                    return step, f"Batch manager error: {e}"

                continue

            # Handle regular Solidity code
            if code.strip():
                print("  -> Processing regular Solidity code...")

                try:
                    print("  -> Getting current context...")
                    ctx = contract_analyzer.get_current_context_type()
                    print(f"  -> Context: {ctx}")

                    print("  -> Generating parse tree...")
                    tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                    print("  -> Parse tree generated successfully")

                    print("  -> Visiting parse tree...")
                    EnhancedSolidityVisitor(contract_analyzer).visit(tree)
                    print("  -> Parse tree visited successfully")

                except Exception as e:
                    print(f"  *** ERROR in Solidity processing: {type(e).__name__}: {e}")
                    print(f"  *** Traceback: {traceback.format_exc()}")
                    return step, f"Solidity processing error: {e}"

            # Get analysis for this line
            try:
                print("  -> Getting line analysis...")
                analysis = contract_analyzer.get_line_analysis(s, e)
                if analysis:
                    print(f"  -> Analysis found for lines {s}-{e}")
                    for ln, recs in analysis.items():
                        for r in recs:
                            print(f"    L{ln:3} | {r['kind']:>14} | {r['vars']}")
                else:
                    print(f"  -> No analysis found for lines {s}-{e}")

            except Exception as e:
                print(f"  *** ERROR in getting analysis: {type(e).__name__}: {e}")
                print(f"  *** Traceback: {traceback.format_exc()}")
                return step, f"Analysis error: {e}"

            print("  -> Step completed successfully")

        except Exception as e:
            print(f"  *** UNEXPECTED ERROR in step: {type(e).__name__}: {e}")
            print(f"  *** Traceback: {traceback.format_exc()}")
            return step, f"Unexpected error: {e}"

        print("-" * 80)

    print("All steps completed successfully!")
    return None, None

def main():
    """Main debugging function."""
    error_step, error_msg = debug_step_by_step()

    if error_step:
        print(f"\n*** ERROR OCCURRED AT STEP {error_step} ***")
        print(f"Error: {error_msg}")
    else:
        print("\n*** ALL STEPS COMPLETED SUCCESSFULLY ***")

if __name__ == "__main__":
    main()