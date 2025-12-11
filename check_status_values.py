import pandas as pd
from pathlib import Path

# Read the mailsuite campaign details
base_dir = Path(__file__).resolve().parent
mailsuite_df = pd.read_csv(base_dir / 'results/mailsuite_campaign_detail_1760021637.csv')

# Check unique status values
print("Unique Status values:")
print(mailsuite_df['Status'].unique())
print(f"\nTotal rows: {len(mailsuite_df)}")

# Count each status
print("\nStatus counts:")
print(mailsuite_df['Status'].value_counts())
