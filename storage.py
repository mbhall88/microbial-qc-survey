"""Response persistence with a Google Sheets backend and a local CSV fallback.

append_response(row) writes one survey response. If Google service-account
credentials are present in st.secrets, the row is appended to the configured
Google Sheet; otherwise it is appended to a local CSV (header written once).
"""
from __future__ import annotations

import csv
from pathlib import Path

CSV_PATH = Path("survey_responses.csv")

# Column order for the persisted response row (the saved schema).
RESPONSE_FIELDS = [
    "timestamp",
    "w_accuracy",
    "w_contiguity",
    "w_decontam",
    "w_replicon",
]


def append_response(row: dict, csv_path: Path = CSV_PATH) -> str:
    """Append one response row to durable storage. Returns the backend used.

    Uses Google Sheets when credentials are configured; otherwise falls back to a
    local CSV at csv_path (writing a header row if the file does not yet exist).
    Raises on write failure so the caller can surface an error to the user.
    """
    if _sheets_configured():
        _append_to_sheet(row)
        return "sheets"
    _append_to_csv(row, csv_path)
    return "csv"


def _append_to_csv(row: dict, csv_path: Path) -> None:
    ordered = {field: row.get(field, "") for field in RESPONSE_FIELDS}
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESPONSE_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(ordered)


def _sheets_configured() -> bool:
    """True when Google service-account creds are available in Streamlit secrets."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return False
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        # st.secrets access raises if no secrets.toml exists; treat as unconfigured.
        return False


def _append_to_sheet(row: dict) -> None:
    import gspread
    import streamlit as st
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["sheet_id"]).sheet1
    
    # Write header if the sheet is brand new and empty
    if not sheet.get_all_values():
        sheet.append_row(RESPONSE_FIELDS)
        
    sheet.append_row([row.get(field, "") for field in RESPONSE_FIELDS])
