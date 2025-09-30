#!/usr/bin/env python3
import pandas as pd

excel_path = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\dataset\evaluation_Dataset.xlsx"
excel_data = pd.read_excel(excel_path)

# Amoss와 ATIDStaking 데이터 확인
contracts = ['Amoss', 'ATIDStaking']

for contract in contracts:
    print(f"\n=== {contract} ===")
    rows = excel_data[excel_data['Unnamed: 2'].str.contains(contract, na=False)]

    if not rows.empty:
        row = rows.iloc[0]
        print(f"Function Name: {row['Unnamed: 4']}")
        print(f"Target Variables: {row['Unnamed: 9']}")
    else:
        print(f"No data found for {contract}")