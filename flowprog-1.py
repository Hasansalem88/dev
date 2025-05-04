import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import gspread
from google.oauth2 import service_account
import xlsxwriter
from io import BytesIO

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

# Function to export DataFrame to Excel and provide download link
def export_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Vehicle Details')
        writer.save()  # Ensures the content is written to the output stream
    output.seek(0)
    return output

# Section: Vehicle Details
if report_option == "Vehicle Details":
    st.subheader("🚘 All Vehicle Details")

    # Filter out the 'Start Time' and '*_time' columns before displaying
    columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]

    # Apply color styling based on status for individual cells
    def color_cells(val):
        # Status colors mapping
        status_colors = {
            "Completed": "background-color: #d4edda",      # Light green
            "In Progress": "background-color: #fff3cd",     # Light yellow/orange
            "Repair Needed": "background-color: #f8d7da"    # Light red
        }
        
        # Apply the correct background color for the specific cell based on its value
        if val in ["Completed", "In Progress", "Repair Needed"]:
            return status_colors.get(val, "")
        return ""

    # Generate a list of color styles for each cell based on its value
    def apply_style_to_df(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)

        for i, row in df.iterrows():
            for col in df.columns:
                styles.at[i, col] = color_cells(row[col])

        return styles

    # Apply styles and filter the dataframe to only show necessary columns
    styled_df = df[columns_to_display]
    styles = apply_style_to_df(styled_df)

    # Display the dataframe with the styles
    st.write(styled_df.style.apply(lambda x: styles.loc[x.name], axis=1))

    # Add the download button for Excel file
    st.download_button(
        label="Download as Excel 📥",
        data=export_to_excel(df),
        file_name="vehicle_details.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
