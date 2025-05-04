import streamlit as st
import pandas as pd
from datetime import datetime
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
    "Vehicle Details",  # First option
    "Dashboard Summary",
    "Production Trend",
    "Line Progress",
    "Add/Update Vehicle"
])

# Sidebar Filters
with st.sidebar:
    st.header("🔍 Filters")
    selected_status = st.selectbox("Current Line Status", ["All"] + list(["In Progress", "Completed", "Repair Needed"]))
    selected_line = st.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
    if st.button("Reset Filters"):
        selected_status = "All"
        selected_line = "All"

# Apply filters
filtered_df = df.copy()
if selected_status != "All":
    if selected_status == "Completed":
        filtered_df = filtered_df[filtered_df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
    else:
        filtered_df = filtered_df[filtered_df.apply(lambda row: row.get(row["Current Line"], None) == selected_status, axis=1)]
if selected_line != "All":
    filtered_df = filtered_df[filtered_df["Current Line"] == selected_line]

st.sidebar.markdown(f"**Matching Vehicles:** {len(filtered_df)}")

# Section: Vehicle Details
if report_option == "Vehicle Details":
    st.subheader("🚘 All Vehicle Details")

    # Filter out the 'Start Time' and '*_time' columns before displaying
    columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]

    # Apply color styling based on status for individual cells
    def color_cells(val):
        # Status colors mapping
        status_colors = {
            "Completed": "background-color: #d4edda",  # Light green
            "In Progress": "background-color: #fff3cd",  # Light yellow/orange
            "Repair Needed": "background-color: #f8d7da"  # Light red
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

    # Adjust column width based on the max content length in each column
    def adjust_column_widths(worksheet, df):
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2  # +2 for some padding
            worksheet.set_column(i, i, max_length)

    # Display the dataframe with the styles
    st.write(styled_df.style.apply(lambda x: styles.loc[x.name], axis=1))

    # Button to download as Excel with formatting and column width adjustment
    def export_to_excel(df):
        output = BytesIO()
        
        # Create a new Excel file with xlsxwriter engine
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Vehicle Details')
            worksheet = writer.sheets['Vehicle Details']
            
            # Adjust column widths
            adjust_column_widths(worksheet, df)
            
            # Apply formatting after writing the data
            cell_format = worksheet.add_format({'text_wrap': True})  # Ensure format is applied after the sheet is created
            
            # Loop through each cell to apply the formatting
            for i, row in df.iterrows():
                for j, value in enumerate(row):
                    worksheet.write(i + 1, j, value, cell_format)

        output.seek(0)
        return output

    # Trigger download
    st.download_button(
        label="Download Vehicle Details as Excel",
        data=export_to_excel(styled_df),
        file_name="vehicle_details.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Section: Add/Update Vehicle
elif report_option == "Add/Update Vehicle":
    with st.expander("✏️ Add New Vehicle", expanded=True):
        new_vin = st.text_input("VIN (exactly 5 characters)").strip().upper()
        new_model = st.selectbox("Model", ["C43"])
        new_start_time = st.date_input("Start Date", datetime.now().date())
        if st.button("Add Vehicle"):
            if len(new_vin) != 5:
                st.error("❌ VIN must be exactly 5 characters.")
            elif new_vin in df["VIN"].values:
                st.error("❌ This VIN already exists.")
            else:
                vehicle = {
                    "VIN": new_vin,
                    "Model": new_model,
                    "Current Line": "Body Shop",
                    "Start Time": datetime.combine(new_start_time, datetime.min.time()),
                    "Last Updated": datetime.now(),
                }
                for line in PRODUCTION_LINES:
                    vehicle[line] = "In Progress" if line == "Body Shop" else ""
                    vehicle[f"{line}_time"] = datetime.now() if line == "Body Shop" else ""
                df = pd.concat([df, pd.DataFrame([vehicle])], ignore_index=True)
                save_data(df)
                st.success(f"✅ {new_vin} added successfully!")
                st.rerun()

    with st.expander("✏️ Update Vehicle Status"):
        if not df.empty and "VIN" in df.columns:
            update_vin = st.selectbox("VIN to Update", df["VIN"])
            current_line = df.loc[df["VIN"] == update_vin, "Current Line"].values[0]
            update_line = st.selectbox("Production Line", PRODUCTION_LINES, index=PRODUCTION_LINES.index(current_line))
            new_status = st.selectbox("New Status", list(STATUS_COLORS.keys()))
            if st.button("Update Status"):
                idx = df[df["VIN"] == update_vin].index[0]
                current_idx = PRODUCTION_LINES.index(current_line)
                update_idx = PRODUCTION_LINES.index(update_line)
                if new_status == "In Progress" and update_idx < current_idx:
                    st.warning("⚠️ Cannot revert a completed line back to 'In Progress'.")
                else:
                    df.at[idx, update_line] = new_status
                    df.at[idx, f"{update_line}_time"] = datetime.now()
                    df.at[idx, "Last Updated"] = datetime.now()
                    if new_status == "Completed" and update_line == current_line and current_idx < len(PRODUCTION_LINES) - 1:
                        df.at[idx, "Current Line"] = PRODUCTION_LINES[current_idx + 1]
                    save_data(df)
                    st.success("✅ Status updated successfully!")
                    st.rerun()
