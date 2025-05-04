import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
from io import BytesIO

# Page setup
st.set_page_config(layout="wide", page_title="🚗 Vehicle Production Tracker")
st.title("🚗 Vehicle Production Flow Dashboard")

# Constants
PRODUCTION_LINES = [
    "Body Shop", "Paint", "TRIM", "UB", "FINAL",
    "Odyssi", "Wheel Alignment", "ADAS", "PQG",
    "Tests Track", "CC4", "DVX", "Audit", "Delivery"
]
VALID_VIN_LENGTH = 5

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

# Load data from Google Sheets
def load_data():
    try:
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
        # Ensure VIN column is treated as string
        df['VIN'] = df['VIN'].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"❌ Failed to load data from Google Sheet: {e}")
        st.stop()

# Save data to Google Sheets
def save_data(df):
    try:
        df_copy = df.copy()
        for col in df_copy.columns:
            df_copy[col] = df_copy[col].apply(lambda x:
                x.isoformat() if isinstance(x, (datetime, pd.Timestamp)) and not pd.isnull(x)
                else "" if pd.isnull(x) or x == pd.NaT
                else str(x)
            )
        sheet.clear()
        sheet.update([list(df_copy.columns)] + df_copy.values.tolist())
    except Exception as e:
        st.error(f"❌ Failed to save data to Google Sheet: {e}")

# Excel export
def export_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Vehicle Details')
        workbook = writer.book
        worksheet = writer.sheets['Vehicle Details']

        # Format columns
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_length)

        # Add status colors
        for col in PRODUCTION_LINES:
            status_column = df[col]
            for idx, status in enumerate(status_column):
                if status == "Completed":
                    worksheet.write(idx + 1, df.columns.get_loc(col), status, 
                                 workbook.add_format({'bg_color': '#d4edda', 'color': '#155724'}))
                elif status == "In Progress":
                    worksheet.write(idx + 1, df.columns.get_loc(col), status,
                                 workbook.add_format({'bg_color': '#fff3cd', 'color': '#856404'}))
                elif status == "Repair Needed":
                    worksheet.write(idx + 1, df.columns.get_loc(col), status,
                                 workbook.add_format({'bg_color': '#f8d7da', 'color': '#721c24'}))
    output.seek(0)
    return output

# Status highlighting
def highlight_status(val):
    if val == "Completed":
        return "background-color: #d4edda; color: #155724;"
    elif val == "In Progress":
        return "background-color: #fff3cd; color: #856404;"
    elif val == "Repair Needed":
        return "background-color: #f8d7da; color: #721c24;"
    return ""

# Load data
df = load_data()

# Sidebar Filters
st.sidebar.header("🔍 Filters")
selected_status = st.sidebar.selectbox("Current Line Status", ["All", "In Progress", "Completed", "Repair Needed"])
selected_line = st.sidebar.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
if st.sidebar.button("Reset Filters"):
    selected_status = "All"
    selected_line = "All"

# Apply filters
filtered_df = df.copy()
if selected_status != "All":
    if selected_status == "Completed":
        filtered_df = filtered_df[filtered_df.apply(
            lambda row: all(str(row.get(line, '')).upper() == "COMPLETED" for line in PRODUCTION_LINES), axis=1)]
    else:
        filtered_df = filtered_df[filtered_df.apply(
            lambda row: str(row.get(row["Current Line"], '')).upper() == selected_status.upper(), axis=1)]

if selected_line != "All":
    filtered_df = filtered_df[filtered_df["Current Line"].str.upper() == selected_line.upper()]

st.sidebar.markdown(f"**Matching Vehicles:** {len(filtered_df)}")

# Vehicle Details Section
st.subheader("📋 Vehicle Details")
columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]
styled_df = filtered_df[columns_to_display].style.applymap(highlight_status, subset=PRODUCTION_LINES)
st.dataframe(styled_df, use_container_width=True)

# Excel Export
st.download_button(
    label="📥 Download Vehicle Details as Excel",
    data=export_to_excel(filtered_df[columns_to_display]),
    file_name="vehicle_details.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Add/Update Vehicle Section
st.subheader("✏️ Add / Update Vehicle")

with st.expander("➕ Add New Vehicle", expanded=True):
    new_vin = st.text_input("VIN (exactly 5 alphanumeric characters)", 
                           max_chars=VALID_VIN_LENGTH).strip().upper()
    new_model = st.selectbox("Model", ["C43"])
    new_start_time = st.date_input("Start Date", datetime.now().date())
    
    # VIN validation
    vin_error = None
    if new_vin:
        if len(new_vin) != VALID_VIN_LENGTH:
            vin_error = f"VIN must be exactly {VALID_VIN_LENGTH} characters"
        elif not new_vin.isalnum():
            vin_error = "VIN must contain only letters and numbers"
        elif new_vin in df['VIN'].values:
            vin_error = "This VIN already exists"
    
    if vin_error:
        st.error(f"❌ {vin_error}")
    
    if st.button("Add Vehicle", disabled=bool(vin_error)):
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

with st.expander("🔄 Update Vehicle Status", expanded=True):
    if not df.empty and "VIN" in df.columns:
        update_vin = st.selectbox("Select VIN", df["VIN"].unique())
        current_data = df[df["VIN"] == update_vin].iloc[0]
        current_line = current_data["Current Line"]
        
        update_line = st.selectbox(
            "Production Line", 
            PRODUCTION_LINES, 
            index=PRODUCTION_LINES.index(current_line)
        )
        new_status = st.selectbox("New Status", ["Completed", "In Progress", "Repair Needed"])
        
        if st.button("Update Status"):
            idx = df[df["VIN"] == update_vin].index[0]
            df.at[idx, update_line] = new_status
            df.at[idx, f"{update_line}_time"] = datetime.now()
            df.at[idx, "Current Line"] = update_line
            df.at[idx, "Last Updated"] = datetime.now()
            
            save_data(df)
            st.success("✅ Status updated successfully!")
            st.rerun()
