import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import gspread
from google.oauth2 import service_account
from io import BytesIO
import xlsxwriter

# Page setup
st.set_page_config(layout="wide", page_title="🚗 Assembly Line Tracker")
st.title("🚗 Vehicle Production Flow Dashboard")

# Access the credentials from Streamlit secrets
secrets = dict(st.secrets["gcp_service_account"])
secrets["private_key"] = secrets["private_key"].replace("\\n", "\n")

# Define the required Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Apply scopes when creating the credentials
creds = service_account.Credentials.from_service_account_info(secrets, scopes=SCOPES)

# Authenticate Google Sheets
try:
    client = gspread.authorize(creds)
    sheet = client.open("VehicleDashboardtest").sheet1
except Exception as e:
    st.error(f"❌ Error opening Google Sheet: {e}")
    st.stop()

# Constants
PRODUCTION_LINES = [
    "Body Shop", "Paint", "TRIM", "UB", "FINAL",
    "Odyssi", "Wheel Alignment", "ADAS", "PQG",
    "Tests Track", "CC4", "DVX", "Audit", "Delivery"
]

STATUS_COLORS = {
    "In Progress": "#FFA500",
    "Completed": "#008000",
    "Repair Needed": "#FF0000",
}

# Load or initialize data
def load_data():
    records = sheet.get_all_records()
    if not records:
        columns = ["VIN", "Model", "Current Line", "Start Time", "Last Updated"]
        for line in PRODUCTION_LINES:
            columns.append(line)
            columns.append(f"{line}_time")
        empty_df = pd.DataFrame(columns=columns)
        sheet.update([list(empty_df.columns)] + [[]])
        return empty_df
    return pd.DataFrame(records)

# Save data to Google Sheets
def save_data(df):
    df_copy = df.copy()
    for col in df_copy.columns:
        df_copy[col] = df_copy[col].apply(lambda x: 
            x.isoformat() if isinstance(x, (datetime, pd.Timestamp)) and not pd.isnull(x)
            else "" if pd.isnull(x) or x == pd.NaT
            else str(x)
        )
    try:
        sheet.clear()
        sheet.update([list(df_copy.columns)] + df_copy.values.tolist())
    except Exception as e:
        st.error(f"❌ Failed to save data to Google Sheet: {e}")

# Load data
try:
    df = load_data()
except Exception as e:
    st.error(f"❌ Failed to load data from Google Sheet: {e}")
    st.stop()

# Sidebar Navigation
st.sidebar.title("📂 Report Menu")
report_option = st.sidebar.radio("Select Report Section", [
    "Vehicle Details",
    "Dashboard Summary",
    "Production Trend",
    "Line Progress",
    "Add/Update Vehicle"
])

# Sidebar Filters
with st.sidebar:
    st.header("🔍 Filters")
    selected_status = st.selectbox("Current Line Status", ["All"] + list(STATUS_COLORS.keys()))
    selected_line = st.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
    if st.button("Reset Filters"):
        selected_status = "All"
        selected_line = "All"

# Apply filters
filtered_df = df.copy()
if "VIN" in filtered_df.columns:
    if selected_status != "All":
        if selected_status == "Completed":
            filtered_df = filtered_df[filtered_df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
        else:
            filtered_df = filtered_df[filtered_df.apply(lambda row: row.get(row["Current Line"], None) == selected_status, axis=1)]
    if selected_line != "All":
        filtered_df = filtered_df[filtered_df["Current Line"] == selected_line]
    st.sidebar.markdown(f"**Matching Vehicles:** {len(filtered_df)}")
else:
    st.sidebar.error("❌ 'VIN' column not found in Google Sheet.")

# Section: Vehicle Details
if report_option == "Vehicle Details":
    st.subheader("🚘 All Vehicle Details")
    columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]

    def color_cells(val):
        status_colors = {
            "Completed": "background-color: #d4edda",
            "In Progress": "background-color: #fff3cd",
            "Repair Needed": "background-color: #f8d7da"
        }
        return status_colors.get(val, "")

    def apply_style_to_df(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            for col in df.columns:
                styles.at[i, col] = color_cells(row[col])
        return styles

    styled_df = df[columns_to_display]
    styles = apply_style_to_df(styled_df)
    st.write(styled_df.style.apply(lambda x: styles.loc[x.name], axis=1))

    # XLSX Download
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        styled_df.to_excel(writer, index=False, sheet_name="Vehicle Details")
        worksheet = writer.sheets["Vehicle Details"]
        for i, col in enumerate(styled_df.columns):
            max_len = max(styled_df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_len)
        workbook = writer.book
        format_green = workbook.add_format({"bg_color": "#d4edda"})
        format_yellow = workbook.add_format({"bg_color": "#fff3cd"})
        format_red = workbook.add_format({"bg_color": "#f8d7da"})
        for row_idx, row in styled_df.iterrows():
            for col_idx, val in enumerate(row):
                fmt = None
                if val == "Completed":
                    fmt = format_green
                elif val == "In Progress":
                    fmt = format_yellow
                elif val == "Repair Needed":
                    fmt = format_red
                if fmt:
                    worksheet.write(row_idx + 1, col_idx, val, fmt)
    st.download_button(
        label="📄 Download XLSX",
        data=buffer.getvalue(),
        file_name="vehicle_details.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
