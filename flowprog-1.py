import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
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

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = service_account.Credentials.from_service_account_info(secrets, scopes=SCOPES)

# Authenticate Google Sheets
try:
    client = gspread.authorize(creds)
    sheet = client.open("VehicleDashboardtest").sheet1
except Exception as e:
    st.error(f"❌ Error opening Google Sheet: {e}")
    st.stop()

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

try:
    df = load_data()
except Exception as e:
    st.error(f"❌ Failed to load data from Google Sheet: {e}")
    st.stop()

st.sidebar.title("📂 Report Menu")
report_option = st.sidebar.radio("Select Report Section", [
    "Vehicle Details", "Dashboard Summary", "Production Trend", "Line Progress", "Add/Update Vehicle"
])

with st.sidebar:
    st.header("🔍 Filters")
    selected_status = st.selectbox("Current Line Status", ["All"] + ["In Progress", "Completed", "Repair Needed"])
    selected_line = st.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
    if st.button("Reset Filters"):
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

if report_option == "Vehicle Details":
    st.subheader("🚘 All Vehicle Details")
    columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]
    def highlight_status(val):
        if val == "Completed": return 'background-color: #A9DFBF;'
        if val == "In Progress": return 'background-color: #F9E79F;'
        if val == "Repair Needed": return 'background-color: #F1948A;'
        return ''
    styled_df = filtered_df[columns_to_display].style.applymap(highlight_status)
    st.dataframe(styled_df)

elif report_option == "Production Trend":
    st.subheader("📈 Production Trend")
    df['Start Date'] = pd.to_datetime(df['Start Time'], errors='coerce').dt.date
    production_trend = df.groupby('Start Date').size().reset_index(name='Vehicle Count')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(production_trend['Start Date'], production_trend['Vehicle Count'], marker='o')
    ax.set_xlabel("Date")
    ax.set_ylabel("Vehicle Count")
    ax.set_title("Production Trend")
    st.pyplot(fig)

elif report_option == "Line Progress":
    st.subheader("🔄 Line Progress")
    progress_data = []
    for line in PRODUCTION_LINES:
        progress_data.append({
            "Production Line": line,
            "Completed": (df[line] == "Completed").sum(),
            "In Progress": (df[line] == "In Progress").sum(),
            "Repair Needed": (df[line] == "Repair Needed").sum()
        })
    line_progress_df = pd.DataFrame(progress_data).set_index("Production Line")
    fig, ax = plt.subplots(figsize=(12, 8))
    line_progress_df.plot(kind="bar", stacked=True, ax=ax, colormap="Set3")
    ax.set_title("Line Progress")
    ax.set_ylabel("Number of Vehicles")
    st.pyplot(fig)

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
            update_status = st.selectbox("New Status", ["Completed", "In Progress", "Repair Needed"])
            if st.button("Update Status"):
                idx = df[df["VIN"] == update_vin].index[0]
                df.at[idx, update_line] = update_status
                df.at[idx, f"{update_line}_time"] = datetime.now()
                df.at[idx, "Current Line"] = update_line
                df.at[idx, "Last Updated"] = datetime.now()
                save_data(df)
                st.success("✅ Status updated successfully!")
                st.rerun()
        else:
            st.warning("⚠️ No VINs available for update.")
