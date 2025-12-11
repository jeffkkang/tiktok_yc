import pandas as pd
from pathlib import Path

# Base directory
base_dir = Path(__file__).resolve().parent

# Read the mailsuite campaign details
mailsuite_df = pd.read_csv(base_dir / 'results/mailsuite_campaign_detail_1760021637.csv')

# Filter for Soft bounce and Pending status
bounced_emails = mailsuite_df[mailsuite_df['Status'].isin(['Soft bounce', 'Pending'])]['Email'].tolist()

print(f"Found {len(bounced_emails)} emails with 'Soft bounce' or 'PENDING' status")

# Read the profiles CSV
profiles_df = pd.read_csv(base_dir / 'all_profiles_with_followers_and_emails_ver1_filtered.csv')

# Filter profiles that match the bounced emails
filtered_profiles = profiles_df[profiles_df['creator_email'].isin(bounced_emails)]

print(f"Found {len(filtered_profiles)} matching profiles")

# Save to new CSV
output_path = base_dir / 'results/soft_bounce_and_pending_profiles.csv'
filtered_profiles.to_csv(output_path, index=False)

print(f"Saved filtered profiles to: {output_path}")
