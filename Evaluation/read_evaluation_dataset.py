#!/usr/bin/env python3
"""
Read evaluation_dataset.xlsx to extract annotation target variables
"""
import pandas as pd
import json
from pathlib import Path

DATASET_FILE = Path("dataset/evaluation_dataset.xlsx")
OUTPUT_JSON = Path("Evaluation/annotation_targets.json")

def main():
    print("Reading evaluation_dataset.xlsx...")

    # Read all sheets
    excel_file = pd.ExcelFile(DATASET_FILE)
    print(f"Found {len(excel_file.sheet_names)} sheets:")
    for sheet in excel_file.sheet_names:
        print(f"  - {sheet}")

    # Read first sheet (or all sheets if needed)
    df = pd.read_excel(DATASET_FILE, sheet_name=0)

    print(f"\nColumns: {list(df.columns)}")
    print(f"Rows: {len(df)}")

    print("\nFirst few rows:")
    print(df.head(20))

    # Save to JSON for inspection
    df.to_json(OUTPUT_JSON, orient='records', indent=2, force_ascii=False)
    print(f"\n[+] Saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
