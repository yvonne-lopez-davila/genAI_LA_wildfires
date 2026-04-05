"""
Parse the California FAIR Plan residential ZIP exposure PDF into a CSV.

Example:
    python3 parse_fair_plan_pdf.py /path/to/CFP-5-yr-TIV-Zip-FY25-DWE-251114.pdf

This is a one-off data preparation script, not part of normal app runtime.
Install its dependencies from `py/requirements-data.txt` when regenerating
the FAIR Plan CSV from the source PDF.

Can be used to regenerate the FAIR Plan dataset CSV if the source PDF is 
updated in the future, or to parse other similar FAIR Plan PDFs if needed.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BASE_DIR / "insurance_datasets" / "fair_plan_residential_exposure_zip.csv"

ROW_RE = re.compile(
    r"^\s*(?P<zipcode>\d{5})\s+"
    r"(?P<fy2025_yoy_growth>-?\d+%)\s+(?P<fy2025_exposure>[\d,]+|-?)\$\s+"
    r"(?P<fy2024_yoy_growth>-?\d+%)\s+(?P<fy2024_exposure>[\d,]+|-?)\$\s+"
    r"(?P<fy2023_yoy_growth>-?\d+%)\s+(?P<fy2023_exposure>[\d,]+|-?)\$\s+"
    r"(?P<fy2022_yoy_growth>-?\d+%)\s+(?P<fy2022_exposure>[\d,]+|-?)\$\s+"
    r"(?P<fy2021_exposure>[\d,]+|-?)\$\s*$"
)


def parse_pdf(pdf_path: Path) -> list[dict[str, str]]:
    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        reader.decrypt("")

    rows: list[dict[str, str]] = []
    seen_zips: set[str] = set()

    for page in reader.pages:
        text = page.extract_text() or ""
        for line in text.splitlines():
            match = ROW_RE.match(line)
            if not match:
                continue

            row = match.groupdict()
            zipcode = row["zipcode"]
            if zipcode in seen_zips:
                continue

            rows.append(row)
            seen_zips.add(zipcode)

    rows.sort(key=lambda row: row["zipcode"])
    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "zipcode",
        "fy2025_yoy_growth",
        "fy2025_exposure",
        "fy2024_yoy_growth",
        "fy2024_exposure",
        "fy2023_yoy_growth",
        "fy2023_exposure",
        "fy2022_yoy_growth",
        "fy2022_exposure",
        "fy2021_exposure",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path, help="Path to FAIR Plan PDF")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    rows = parse_pdf(args.pdf_path)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} ZIP rows to {args.output}")


if __name__ == "__main__":
    main()
