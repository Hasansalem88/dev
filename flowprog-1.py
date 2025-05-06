import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
from io import BytesIO

# Page setup
st.set_page_config(layout="wide", page_title="🚗 Vehicle Production Tracker")
st.title("🚗 Vehicle Production Flow Dashboard")

# --- Admin Login System ---
users = {"admin": "admin123"}

st.sidebar.title("🔐 Admin Login")
username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")
login_btn = st.sidebar.button("Login")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if login_btn:
    if username in users and users[username] == password:
        st.session_state.logged_in = True
        st.sidebar.success("✅ Logged in as admin")
    else:
        st.sidebar.error("❌ Invalid username or password")

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

# --- Enhanced Scorecards ---
st.subheader("📊 Production Overview")

# Calculate metrics
total_vehicles = len(df)
completed_vehicles = len(df[df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)])
in_progress_vehicles = len(df[df.apply(lambda row: any(row.get(line) == "In Progress" for line in PRODUCTION_LINES), axis=1)])
repair_needed_vehicles = len(df[df.apply(lambda row: any(row.get(line) == "Repair Needed" for line in PRODUCTION_LINES), axis=1)])

# Create columns
col1, col2, col3 = st.columns(3)

# Custom CSS for cards
st.markdown("""
<style>
    .metric-card {
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .completed-card {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
    }
    .progress-card {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
    }
    .repair-card {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
    }
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Completed Card
with col1:
    st.markdown(f"""
    <div class="metric-card completed-card">
        <h3>✅ Completed</h3>
        <div class="metric-value">{completed_vehicles}</div>
        <p>{round(completed_vehicles/total_vehicles*100 if total_vehicles > 0 else 0, 1)}% of total</p>
    </div>
    """, unsafe_allow_html=True)

# In Progress Card
with col2:
    st.markdown(f"""
    <div class="metric-card progress-card">
        <h3>🔄 In Progress</h3>
        <div class="metric-value">{in_progress_vehicles}</div>
        <p>{round(in_progress_vehicles/total_vehicles*100 if total_vehicles > 0 else 0, 1)}% of total</p>
    </div>
    """, unsafe_allow_html=True)

# Repair Needed Card
with col3:
    st.markdown(f"""
    <div class="metric-card repair-card">
        <h3>⚠️ Repair Needed</h3>
        <div class="metric-value">{repair_needed_vehicles}</div>
        <p>{round(repair_needed_vehicles/total_vehicles*100 if total_vehicles > 0 else 0, 1)}% of total</p>
    </div>
    """, unsafe_allow_html=True)

# Optional: Add a small space before the next section
st.markdown("<br>", unsafe_allow_html=True)

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

# أولاً تأكد من أن المستخدم مسجل دخوله
if "logged_in" in st.session_state and st.session_state["logged_in"]:
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
                # Update status and move to next line if completed
                idx = df[df["VIN"] == update_vin].index[0]
                if new_status == "Completed":
                    next_line = get_next_line(current_line)
                    if next_line:
                        df.at[idx, update_line] = new_status
                        df.at[idx, f"{update_line}_time"] = datetime.now()
                        df.at[idx, "Current Line"] = next_line
                        df.at[idx, f"{next_line}_time"] = datetime.now()
                        # Set next line's status to "In Progress"
                        df.at[idx, next_line] = "In Progress"
                        df.at[idx, f"{next_line}_time"] = datetime.now()
                    else:
                        st.error(f"❌ This vehicle has already reached the final line!")
                else:
                    df.at[idx, update_line] = new_status
                    df.at[idx, f"{update_line}_time"] = datetime.now()

                df.at[idx, "Last Updated"] = datetime.now()
                save_data(df)
                st.success(f"✅ {update_vin} status updated to {new_status} on {update_line}.")
                st.rerun()
else:
    st.info("🔒Add Vin - Admin Only.")

# Section: Delete Vehicle
if st.session_state.get("logged_in"):
    st.subheader("🗑️ Delete Vehicle")

    with st.expander("🗑️ Remove Vehicle", expanded=True):
        vin_to_delete = st.selectbox("Select VIN to Delete", df["VIN"])

        if st.button("Delete Vehicle"):
            if vin_to_delete:
                df = df[df["VIN"] != vin_to_delete]
                save_data(df)
                st.success(f"✅ Vehicle {vin_to_delete} has been deleted.")
                st.rerun()
else:
    st.info("🔒 Update Status - Admin Only.")
    
# Section: Bulk Update Status
if st.session_state.get("logged_in"):
    st.subheader("📊 Bulk Update Vehicle Status")

    with st.expander("🔄 Bulk Update Status", expanded=True):
        bulk_update_vin = st.text_area("Enter VINs (separate by comma)").strip().upper()
        bulk_new_status = st.selectbox("New Status for All VINs", ["Completed", "In Progress", "Repair Needed"])

        if st.button("Update Bulk Status"):
            if bulk_update_vin:
                vins = [vin.strip().zfill(5) for vin in bulk_update_vin.split(",")]
                for vin in vins:
                    if vin in df["VIN"].values:
                        idx = df[df["VIN"] == vin].index[0]
                        current_line = df.at[idx, "Current Line"]
                        if bulk_new_status == "Completed":
                            next_line = get_next_line(current_line)
                            if next_line:
                                df.at[idx, current_line] = bulk_new_status
                                df.at[idx, f"{current_line}_time"] = datetime.now()
                                df.at[idx, "Current Line"] = next_line
                                df.at[idx, f"{next_line}_time"] = datetime.now()
                                # Set next line's status to "In Progress"
                                df.at[idx, next_line] = "In Progress"
                                df.at[idx, f"{next_line}_time"] = datetime.now()
                        else:
                            df.at[idx, current_line] = bulk_new_status
                            df.at[idx, f"{current_line}_time"] = datetime.now()
                        df.at[idx, "Last Updated"] = datetime.now()
                save_data(df)
                st.success(f"✅ Bulk status updated for {len(vins)} vehicles.")
                st.rerun()
else:
    st.info("🔒 Delete Vin - Admin Only.")
