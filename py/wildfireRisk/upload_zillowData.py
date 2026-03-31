"""
Preprocesses and uploads Zillow Home Value Index (ZHVI) data to LLMProxy RAG.

Usage:
    python upload_zillow.py --file zhvi_ca.csv

What this does:
    1. Reads the Zillow ZHVI CSV (filtered to CA)
    2. Converts wide date format to readable text, one chunk per metro/region
    3. Uploads each chunk to LLMProxy under the same session_id as HomeRiskClient
    4. Waits for processing

The session_id must match HomeRiskClient's session_id so RAG retrieval works.
"""

import argparse
import time
import pandas as pd
from llmproxy import LLMProxy
from dotenv import load_dotenv

load_dotenv()

# Must match session_id in HomeRiskClient
SESSION_ID = "LA_risk_analysis"

# Only keep date columns from this year onward
# Set to None to keep all historical data
START_YEAR = None


def format_row_as_text(row, date_cols):
    """
    Convert a single metro row into a readable text chunk for RAG.
    Example output:
        Zillow Home Value Index - Los Angeles, CA (msa)
        Jan 2000: $221,540 | Feb 2000: $222,364 | ... | Dec 2024: $812,000
    """
    region_name = row.get("RegionName", "Unknown")
    region_type = row.get("RegionType", "")
    state = row.get("StateName", "")

    header = f"Zillow Home Value Index - {region_name}, {state} ({region_type})"

    # Format each date/value pair, skip nulls
    values = []
    for col in date_cols:
        val = row.get(col)
        if pd.notna(val):
            try:
                formatted = f"{col}: ${int(val):,}"
                values.append(formatted)
            except (ValueError, TypeError):
                continue

    if not values:
        return None

    # Join w/ pipe separator, wrap at every 12 months 
    chunks = [values[i:i+12] for i in range(0, len(values), 12)]
    value_lines = "\n".join(" | ".join(chunk) for chunk in chunks)

    return f"{header}\n{value_lines}"


def main(file_path: str):
    print(f"Reading {file_path}...")
    df = pd.read_csv(file_path)

    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    # Identify date columns (starts with digit)
    date_cols = [c for c in df.columns if c[0].isdigit()]

    # Including all years now, but could shrink window to only include START_YEAR and on
    if START_YEAR:
        date_cols = [c for c in date_cols if int(c.split("/")[-1]) >= START_YEAR]
        print(f"Trimmed to {len(date_cols)} date columns from {START_YEAR} onward")
    else:
        print(f"Using all {len(date_cols)} date columns")

    proxy = LLMProxy()

    success = 0
    failed = 0
    skipped = 0

    for i, (_, row) in enumerate(df.iterrows()):
        region_name = row.get("RegionName", f"Region_{i}")
        text = format_row_as_text(row, date_cols)

        if not text:
            skipped += 1
            continue

        result = proxy.upload_text(
            text=text,
            session_id=SESSION_ID,
            description=f"ZHVI: {region_name}",
            strategy="smart"
        )

        if "error" in result:
            print(f"  FAILED [{region_name}]: {result['error']}")
            failed += 1
        else:
            print(f"  Uploaded [{i+1}/{len(df)}]: {region_name}")
            success += 1

        # Small delay in between row uploads
        time.sleep(0.5)

    print(f"\nDone. {success} uploaded, {failed} failed, {skipped} skipped.")
    print(f"Waiting 30 seconds for processing...")
    time.sleep(30)
    print("RAG database ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload Zillow ZHVI data to RAG")
    parser.add_argument("--file", type=str, default="zillow_datasets/zhvi_ca.csv",
                        help="Path to filtered Zillow ZHVI CSV file")
    args = parser.parse_args()
    main(args.file)