import pandas as pd

df = pd.read_excel('dataset/evaluation_Dataset.xlsx', header=0)
df.columns = ['Index', 'Size_KB', 'Sol_File_Name', 'Contract_Name', 'Function_Name',
              'Original_Function_Line', 'Annotation_Targets', 'State_Slots', 'ByteOp',
              'Target_Variables']

# Remove first row if it's the Korean header
if len(df) > 0 and df.iloc[0]['Size_KB'] == '용량':
    df = df.iloc[1:].reset_index(drop=True)

# Find BitBookStake
matching = df[df['Sol_File_Name'].str.contains('BitBook', case=False, na=False)]
print("Matching rows for 'BitBook':")
print(matching[['Sol_File_Name', 'Contract_Name']])

print("\n\nAll unique Sol_File_Name values:")
for name in sorted(df['Sol_File_Name'].unique()):
    print(f"  - {name}")
