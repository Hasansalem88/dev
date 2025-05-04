import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
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

    # Apply styling based on status
    def highlight_status(val):
        color = ''
        if val == "Completed":
            color = 'background-color: #A9DFBF;'  # Green
        elif val == "In Progress":
            color = 'background-color: #F9E79F;'  # Yellow
        elif val == "Repair Needed":
            color = 'background-color: #F1948A;'  # Red
        return color

    # Apply styles to the dataframe
    styled_df = filtered_df[columns_to_display].style.applymap(highlight_status)

    # Display the styled dataframe
    st.dataframe(styled_df)

    # Button to download as Excel
    def export_to_excel(df):
        output = BytesIO()
        
        # Create a new Excel file with formatting
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Vehicle Details')
            worksheet = writer.sheets['Vehicle Details']
            
            # Define cell formatting
            completed_format = worksheet.add_format({'bg_color': '#A9DFBF'})  # Green
            in_progress_format = worksheet.add_format({'bg_color': '#F9E79F'})  # Yellow
            repair_needed_format = worksheet.add_format({'bg_color': '#F1948A'})  # Red
            
            # Apply formatting to cells based on status
            for row_idx, row in df.iterrows():
                for col_idx, col_name in enumerate(df.columns):
                    status = row[col_name]
                    if status == "Completed":
                        worksheet.write(row_idx + 1, col_idx, status, completed_format)
                    elif status == "In Progress":
                        worksheet.write(row_idx + 1, col_idx, status, in_progress_format)
                    elif status == "Repair Needed":
                        worksheet.write(row_idx + 1, col_idx, status, repair_needed_format)
                    else:
                        worksheet.write(row_idx + 1, col_idx, status)

            # Adjust column widths to fit content
            for i, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2  # +2 for some padding
                worksheet.set_column(i, i, max_length)

        output.seek(0)
        return output

    # Trigger download
    st.download_button(
        label="Download Vehicle Details as Excel",
        data=export_to_excel(filtered_df),
        file_name="vehicle_details.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# Section: Dashboard Summary
elif report_option == "Dashboard Summary":
    st.subheader("📊 Dashboard Summary")
    st.write("This section will show the summary of the production flow, with key metrics for vehicle statuses.")

# Section: Production Trend
elif report_option == "Production Trend":
    st.subheader("📈 Production Trend")
    st.write("This section will show the trends of vehicle production over time.")

# Section: Line Progress
elif report_option == "Line Progress":
    st.subheader("🔄 Line Progress")
    st.write("This section will show the progress of vehicles on each production line.")

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
            new_status = st.selectbox("New Status", ["Completed", "In Progress", "Repair Needed"])
            if st.button("Update Status"):
                idx = df[df["VIN"] == update_vin].index[0]
                df.at[idx, update_line] = new_status
                df.at[idx, f"{update_line}_time"] = datetime.now()
                df.at[idx, "Last Updated"] = datetime.now()
                save_data(df)
                st.success("✅ Status updated successfully!")
                st.rerun()
