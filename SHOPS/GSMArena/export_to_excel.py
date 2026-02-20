#!/usr/bin/env python3
"""Export all parsed GSMArena phones to Excel"""

import json
import os
import pandas as pd
from datetime import datetime

OUTPUT_DIR = "output"
EXCEL_FILE = f"gsmarena_phones_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

def load_all_phones():
    """Load all phones from JSON files (pick the file with MOST data per brand)"""
    all_phones = []

    # First pass: find best file for each brand (most phones)
    brand_files = {}
    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(OUTPUT_DIR, filename)
        brand_name = filename.split('_')[0]

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            count = len(data) if isinstance(data, list) else 0

            if brand_name not in brand_files or count > brand_files[brand_name][1]:
                brand_files[brand_name] = (filename, count, data)
        except Exception as e:
            print(f"  Error reading {filename}: {e}")

    # Second pass: use best files
    for brand_name in sorted(brand_files.keys()):
        filename, count, data = brand_files[brand_name]
        for phone in data:
            phone['_source_file'] = filename
            phone['_brand'] = brand_name.capitalize()
        all_phones.extend(data)
        print(f"  {brand_name}: {count} phones (from {filename})")

    return all_phones

def flatten_specs(phone):
    """Flatten nested specs into columns"""
    flat = {
        'Brand': phone.get('_brand', ''),
        'Model': phone.get('name', ''),
        'URL': phone.get('url', ''),
        'Image': phone.get('image', ''),
        'Parsed_At': phone.get('parsed_at', ''),
    }

    # Skip internal keys
    skip_keys = {'_brand', '_source_file', 'name', 'url', 'image', 'parsed_at'}

    # Extract all specs (they are at top level, not nested in 'specs')
    for category, details in phone.items():
        if category in skip_keys:
            continue

        if isinstance(details, dict):
            for key, value in details.items():
                col_name = f"{category}_{key}".replace(' ', '_').replace('.', '')
                flat[col_name] = value
        else:
            flat[category] = details

    return flat

def main():
    print("Loading phones from JSON files...")
    phones = load_all_phones()
    print(f"\nTotal phones: {len(phones)}")

    if not phones:
        print("No phones found!")
        return

    print("\nFlattening data...")
    flat_data = [flatten_specs(p) for p in phones]

    print("Creating DataFrame...")
    df = pd.DataFrame(flat_data)

    # Reorder columns: Brand, Model first
    cols = df.columns.tolist()
    priority_cols = ['Brand', 'Model', 'URL', 'Image']
    other_cols = [c for c in cols if c not in priority_cols]
    df = df[priority_cols + sorted(other_cols)]

    print(f"Saving to {EXCEL_FILE}...")
    df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

    print(f"\nDone! Exported {len(df)} phones to {EXCEL_FILE}")
    print(f"Columns: {len(df.columns)}")
    print(f"Brands: {df['Brand'].nunique()}")

if __name__ == "__main__":
    main()
