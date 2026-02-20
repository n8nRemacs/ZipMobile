#!/usr/bin/env python3
"""Export GSMArena phones from PostgreSQL to Excel"""

import psycopg2
import pandas as pd
from datetime import datetime

DB_CONFIG = {
    'host': '85.198.98.104',
    'port': 5433,
    'user': 'postgres',
    'password': 'Mi31415926pSss!',
    'database': 'postgres'
}

EXCEL_FILE = f'gsmarena_phones_db_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'


def export_to_excel():
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)

    print("Fetching data...")
    query = """
        SELECT
            brand as "Brand",
            model_name as "Model",
            model_url as "URL",
            image_url as "Image",
            release_year as "Year",
            display_size_inches as "Display (inches)",
            display_type as "Display Type",
            display_resolution as "Resolution",
            refresh_rate as "Refresh Rate",
            chipset as "Chipset",
            cpu as "CPU",
            gpu as "GPU",
            ram as "RAM",
            storage as "Storage",
            main_camera_mp as "Main Camera",
            selfie_camera_mp as "Selfie Camera",
            battery_capacity_mah as "Battery (mAh)",
            charging_wired as "Charging",
            os as "OS",
            weight_grams as "Weight (g)",
            dimensions as "Dimensions",
            nfc as "NFC",
            network_5g as "5G Bands",
            colors as "Colors",
            price as "Price",
            parsed_at as "Parsed At"
        FROM zip_gsmarena_raw
        ORDER BY brand, model_name
    """

    df = pd.read_sql(query, conn)
    conn.close()

    # Remove timezone for Excel compatibility
    if 'Parsed At' in df.columns:
        df['Parsed At'] = pd.to_datetime(df['Parsed At']).dt.tz_localize(None)

    print(f"Total records: {len(df)}")
    print(f"\nBy brand:")
    for brand, count in df.groupby('Brand').size().sort_values(ascending=False).head(15).items():
        print(f"  {brand}: {count}")

    print(f"\nSaving to {EXCEL_FILE}...")
    df.to_excel(EXCEL_FILE, index=False, engine='openpyxl')

    print(f"\nDone! Exported {len(df)} phones to {EXCEL_FILE}")
    print(f"Brands: {df['Brand'].nunique()}")


if __name__ == "__main__":
    export_to_excel()
