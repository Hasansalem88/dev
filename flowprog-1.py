import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import gspread
from google.oauth2 import service_account

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

# Sidebar Filters (VIN filter removed)
with st.sidebar:
    st.header("🔍 Filters")
    selected_status = st.selectbox("Current Line Status", ["All"] + list(STATUS_COLORS.keys()))
    selected_line = st.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
    if st.button("Reset Filters"):
        selected_status = "All"
        selected_line = "All"

# Apply filters (VIN filter logic removed)
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
    
# Section 1: Dashboard Summary
if report_option == "Dashboard Summary":
    with st.container():
        st.subheader("📅 Daily Production Summary")
        col1, col2, col3 = st.columns(3)
        df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce")
        df["Last Updated"] = pd.to_datetime(df["Last Updated"], errors="coerce")
        today = pd.Timestamp.now().normalize()
        vehicles_today = df[df["Start Time"].dt.normalize() == today]
        completed_today = df[(df["Last Updated"].dt.normalize() == today) & (df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1))]
        in_progress = df[df["Current Line"] != "Delivery"]
        col1.metric("🆕 Vehicles Added Today", len(vehicles_today))
        col2.metric("✅ Completed Today", len(completed_today))
        col3.metric("🔄 Still In Progress", len(in_progress))

# --- Daily completions trend ---
if report_option == "Production Trend":
    with st.container():
        st.subheader("📈 Daily Completions Trend")
        daily_counts = df[df["Last Updated"].notna()].copy()
        daily_counts["Last Updated"] = pd.to_datetime(daily_counts["Last Updated"], errors="coerce")
        daily_counts = daily_counts[daily_counts["Last Updated"].notna()]
        daily_counts = daily_counts[daily_counts.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
        daily_counts["Completed Date"] = daily_counts["Last Updated"].dt.date
        trend = daily_counts.groupby("Completed Date").size().reset_index(name="Completed Count")
        if not trend.empty:
            st.line_chart(trend.rename(columns={"Completed Date": "index"}).set_index("index"))
        else:
            st.info("ℹ️ No completed vehicles yet to display in trend.")

# Section 3: Line Progress
elif report_option == "Line Progress":
    with st.container():
        st.subheader("🏭 Line Progress Tracker")
        line_counts = df["Current Line"].value_counts().reindex(PRODUCTION_LINES, fill_value=0).reset_index()
        line_counts.columns = ["Production Line", "Vehicle Count"]
        fig_progress = px.bar(
            line_counts,
            x="Production Line",
            y="Vehicle Count",
            title="Vehicles Currently at Each Production Line",
            text="Vehicle Count"
        )
        fig_progress.update_traces(textposition="outside")
        fig_progress.update_layout(xaxis_title="", yaxis_title="Vehicles", height=400)
        st.plotly_chart(fig_progress, use_container_width=True)

def highlight_vehicle_status(row):
    # Check overall line status
    status_colors = {
        "Completed": "background-color: #d4edda",      # Light green
        "In Progress": "background-color: #fff3cd",     # Light yellow/orange
        "Repair Needed": "background-color: #f8d7da"    # Light red
    }

    row_status = None
    if all(row.get(line) == "Completed" for line in PRODUCTION_LINES):
        row_status = "Completed"
    elif any(row.get(line) == "Repair Needed" for line in PRODUCTION_LINES):
        row_status = "Repair Needed"
    else:
        row_status = "In Progress"

    return [status_colors.get(row_status, "")] * len(row)

# Section 4: Vehicle Details
elif report_option == "Vehicle Details":
    st.subheader("🚘 All Vehicle Details")

    def color_row(row):
        color = STATUS_COLORS.get(row["Current Line"], "#f0f0f0")
        return [f"background-color: {color}"] * len(row)

    styled_df = df.style.apply(color_row, axis=1)
    st.write(styled_df)
    else:
        st.info("ℹ️ No vehicles match the selected filters.")
        
# Section 5: Add/Update Vehicle
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
                        next_line = PRODUCTION_LINES[current_idx + 1]
                        df.at[idx, "Current Line"] = next_line
                        df.at[idx, next_line] = "In Progress"
                        df.at[idx, f"{next_line}_time"] = datetime.now()
                    save_data(df)
                    st.success(f"✅ Updated {update_vin} at {update_line} to {new_status}")
                    st.rerun()
        else:
            st.info("ℹ️ No VINs available to update.")
