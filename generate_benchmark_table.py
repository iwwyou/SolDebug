import pandas as pd
import re

df = pd.read_excel('dataset/evaluation_Dataset.xlsx', skiprows=1)
df.columns = df.columns.str.strip()

print(r'\begin{table*}[t]')
print(r'\centering')
print(r'\small')
print(r'\begin{tabular}{@{}lll@{}}')
print(r'\toprule')
print(r'\textbf{File Name} & \textbf{Function} & \textbf{Lines} \\')
print(r'\midrule')

for i, row in df.iterrows():
    fname = row['.sol File Name'].replace('_', r'\_')
    func = row['Function Name'].replace('_', r'\_')
    # Remove everything in parentheses from line numbers
    line = str(row['Original Function Line'])
    line = re.sub(r'\([^)]*\)', '', line).strip()
    print(f'{fname} & \\texttt{{{func}}} & {line} \\\\')

print(r'\bottomrule')
print(r'\end{tabular}')
print(r'\caption{Benchmark dataset: 30 representative contracts from DAppSCAN with diverse debugging scenarios.}')
print(r'\label{tab:benchmark-dataset}')
print(r'\end{table*}')
