import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_worksheet(sheet_name):
    client = get_gspread_client()
    spreadsheet = client.open_by_key(st.secrets["sheet_id"])
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=sheet_name, rows=500, cols=10)

def read_sheet(sheet_name):
    ws = get_worksheet(sheet_name)
    records = ws.get_all_records()
    return pd.DataFrame(records)

def write_sheet(sheet_name, df):
    ws = get_worksheet(sheet_name)
    ws.clear()
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
    else:
        ws.update([df.columns.values.tolist()])
    st.cache_data.clear()

def clean_types(df, text_cols, number_cols):
    """Force consistent dtypes so st.data_editor's grid doesn't get confused
    by mixed str/int/float cells coming back from Google Sheets."""
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    for col in number_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df
