import pandas as pd
import glob
import os

# Annotation 파일 목록
annot_files = glob.glob(r'dataset/json/annotation/*_annot.json')
annot_contracts = set([os.path.basename(f).replace('_c_annot.json', '').replace('_annot.json', '') for f in annot_files])

# CSV에서 처리된 컨트랙트
df = pd.read_csv('Evaluation/soldebug_benchmark_results.csv')
processed_contracts = set(df['Contract'].unique())

print(f'Total annotation files: {len(annot_contracts)}')
print(f'Processed contracts: {len(processed_contracts)}')
print(f'Missing contracts: {len(annot_contracts - processed_contracts)}')
print(f'\nMissing: {sorted(annot_contracts - processed_contracts)}')

# 부분적으로만 처리된 케이스 확인
print(f'\n--- Contracts with incomplete measurements ---')
for contract in processed_contracts:
    count = len(df[df['Contract'] == contract])
    if count < 4:
        print(f'{contract}: only {count}/4 measurements')
