import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
from io import BytesIO

# Page setup
st.set_page_config(layout="wide", page_title="🚗 Vehicle Production Tracker")
st.title("🚗 Vehicle Production Flow Dashboard")

# Access credentials from Streamlit secrets
secrets = dict(st.secrets["gcp_service_account"])
secrets["private_key"] = secrets["private_key"].replace("\\n", "\n")

# Define Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Create credentials
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
    df = pd.DataFrame(records)
    df["VIN"] = df["VIN"].astype(str)  # Ensure VIN column is treated as a string
    return df

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

# Helper function to get the next line in production
def get_next_line(current_line):
    try:
        current_index = PRODUCTION_LINES.index(current_line)
        if current_index + 1 < len(PRODUCTION_LINES):
            return PRODUCTION_LINES[current_index + 1]
        return None  # If it's the last line, no next line
    except ValueError:
        return None

# Access credentials from Streamlit secrets
secrets = dict(st.secrets["gcp_service_account"])
secrets["private_key"] = secrets["private_key"].replace("\\n", "\n")

# Define Google Sheets scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Create credentials
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

# Continue the rest of your code here...

# Sidebar Filters
st.sidebar.header("🔍 Filters")
selected_status = st.sidebar.selectbox("Current Line Status", ["All"] + ["In Progress", "Completed", "Repair Needed"])
selected_line = st.sidebar.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
if st.sidebar.button("Reset Filters"):
    selected_status = "All"
    selected_line = "All"

filtered_df = df.copy()
if selected_status != "All":
    if selected_status == "Completed":
        filtered_df = filtered_df[filtered_df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
    else:
        filtered_df = filtered_df[filtered_df.apply(lambda row: row.get(row["Current Line"], None) == selected_status, axis=1)]

if selected_line != "All":
    filtered_df = filtered_df[filtered_df["Current Line"] == selected_line]

st.sidebar.markdown(f"**Matching Vehicles:** {len(filtered_df)}")

# Helper for status highlighting
def highlight_status(val):
    if val == "Completed":
        return "background-color: #d4edda; color: #155724;"  # Green
    elif val == "In Progress":
        return "background-color: #fff3cd; color: #856404;"  # Yellow
    elif val == "Repair Needed":
        return "background-color: #f8d7da; color: #721c24;"  # Red
    return ""

# Section: Vehicle Details
st.subheader("📋 Vehicle Details")

columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]
styled_df = filtered_df[columns_to_display].style.applymap(highlight_status, subset=PRODUCTION_LINES)
st.dataframe(styled_df, use_container_width=True)

# Excel export
def export_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Vehicle Details')
        worksheet = writer.sheets['Vehicle Details']
        
        # Add format options
        completed_format = writer.book.add_format({'bg_color': '#d4edda', 'font_color': '#155724'})  # Green
        in_progress_format = writer.book.add_format({'bg_color': '#fff3cd', 'font_color': '#856404'})  # Yellow
        repair_needed_format = writer.book.add_format({'bg_color': '#f8d7da', 'font_color': '#721c24'})  # Red
        
        # Loop through each row and apply the formatting based on the status
        for row_idx, row in df.iterrows():
            for col_idx, value in enumerate(row):
                if value == "Completed":
                    worksheet.write(row_idx + 1, col_idx, value, completed_format)
                elif value == "In Progress":
                    worksheet.write(row_idx + 1, col_idx, value, in_progress_format)
                elif value == "Repair Needed":
                    worksheet.write(row_idx + 1, col_idx, value, repair_needed_format)
                else:
                    worksheet.write(row_idx + 1, col_idx, value)
        
        # Adjust the column width based on the maximum length of the data
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_length)
    
    output.seek(0)
    return output

st.download_button(
    label="📥 Download Vehicle Details as Excel",
    data=export_to_excel(filtered_df[columns_to_display]),
    file_name="vehicle_details.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Section: Add / Update Vehicle
st.subheader("✏️ Add / Update Vehicle")

with st.expander("➕ Add New Vehicle", expanded=True):
    new_vin = st.text_input("VIN (exactly 5 characters)").strip().upper()
    new_model = st.selectbox("Model", ["C43"])
    new_start_time = st.date_input("Start Date", datetime.now().date())

    # Reload the full DataFrame and fix VIN formatting
    df["VIN"] = df["VIN"].astype(str).str.zfill(5).str.upper()  # Always format VINs to 5-character padded strings

    if st.button("Add Vehicle"):
        new_vin_clean = new_vin.zfill(5).upper()  # Pad and uppercase to match stored format

        if len(new_vin_clean) != 5:
            st.error("❌ VIN must be exactly 5 characters.")
        elif new_vin_clean in df["VIN"].values:
            st.error("❌ This VIN already exists.")
        else:
            vehicle = {
                "VIN": new_vin_clean,
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
            st.success(f"✅ {new_vin_clean} added successfully!")
            st.rerun()

with st.expander("🔄 Update Vehicle Status", expanded=True):
    if not df.empty and "VIN" in df.columns:
        update_vin = st.selectbox("Select VIN", df["VIN"])
        current_line = df.loc[df["VIN"] == update_vin, "Current Line"].values[0]
        update_line = st.selectbox("Production Line", PRODUCTION_LINES, index=PRODUCTION_LINES.index(current_line))
        new_status = st.selectbox("New Status", ["Completed", "In Progress", "Repair Needed"])
        
        if st.button("Update Status"):
            # Check if the new status is "Completed"
            if new_status == "Completed":
                # Move the vehicle to the next line with "In Progress" status
                next_line = get_next_line(current_line)
                if next_line:
                    idx = df[df["VIN"] == update_vin].index[0]
                    df.at[idx, update_line] = "Completed"
                    df.at[idx, f"{update_line}_time"] = datetime.now()
                    df.at[idx, "Last Updated"] = datetime.now()

                    # Set the next line to "In Progress"
                    df.at[idx, "Current Line"] = next_line
                    df.at[idx, next_line] = "In Progress"
                    df.at[idx, f"{next_line}_time"] = datetime.now()
                    save_data(df)
                    st.success(f"✅ {update_vin} moved to {next_line} with 'In Progress' status!")
                    st.rerun()
                else:
                    st.error("❌ This is the last production line, no next line available.")
            else:
                # If not completed, just update the selected line
                idx = df[df["VIN"] == update_vin].index[0]
                df.at[idx, update_line] = new_status
                df.at[idx, f"{update_line}_time"] = datetime.now()
                df.at[idx, "Last Updated"] = datetime.now()
                save_data(df)
                st.success("✅ Status updated successfully!")
                st.rerun()

# Section: Bulk Update Vehicle Status
st.subheader("🔄 Bulk Update Vehicle Status")

# Select VINs for bulk update
selected_vins = st.multiselect("Select VINs to update", df["VIN"].unique())

if selected_vins:
    # Select Production Line and Status
    selected_status = st.selectbox("New Status", ["Completed", "In Progress", "Repair Needed"])
    selected_line = st.selectbox("Production Line", PRODUCTION_LINES)

    if st.button("Update Selected VINs"):
        # Loop through selected VINs and update their status
        for vin in selected_vins:
            # Find the row corresponding to the VIN
            idx = df[df["VIN"] == vin].index[0]
            
            # Update the status and timestamp for the selected line
            df.at[idx, selected_line] = selected_status
            df.at[idx, f"{selected_line}_time"] = datetime.now()
            df.at[idx, "Last Updated"] = datetime.now()
        
        # Save the updated DataFrame to Google Sheets
        save_data(df)
        
        st.success("✅ Selected VINs status updated successfully!")
        st.experimental_rerun()  # Refresh the app to reflect the changes

with st.expander("🗑️ Delete Vehicle", expanded=False):
    if not df.empty and "VIN" in df.columns:
        df["VIN"] = df["VIN"].astype(str).str.zfill(5).str.upper()
        delete_vin = st.selectbox("Select VIN to delete", df["VIN"].unique())

        if st.button("Delete Vehicle"):
            df = df[df["VIN"] != delete_vin]
            save_data(df)
            st.success(f"🗑️ VIN {delete_vin} has been deleted.")
            st.rerun()

