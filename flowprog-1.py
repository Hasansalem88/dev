import streamlit as st
import pandas as pd
import numpy as np
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
    sheet = client.open("VehicleDashboard").sheet1
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
        # Sheet is empty, initialize columns
        columns = ["VIN", "Model", "Current Line", "Start Time", "Last Updated"]
        for line in PRODUCTION_LINES:
            columns.append(line)
            columns.append(f"{line}_time")
        empty_df = pd.DataFrame(columns=columns)
        sheet.update([empty_df.columns.values.tolist()])
        return empty_df
    return pd.DataFrame(records)

# Save data to Google Sheets
def save_data(df):
    # Create a copy and convert all datetime fields to string
    df_copy = df.copy()
    for col in df_copy.columns:
        df_copy[col] = df_copy[col].apply(
            lambda x: x.isoformat() if isinstance(x, (datetime, pd.Timestamp)) else x
        )
    sheet.clear()
    sheet.update([df_copy.columns.tolist()] + df_copy.values.tolist())

# Load data
try:
    df = load_data()
except Exception as e:
    st.error(f"❌ Failed to load data from Google Sheet: {e}")
    st.stop()

# Sidebar filters
with st.sidebar:
    st.header("🔍 Filters")
    selected_status = st.selectbox("Current Line Status", ["All"] + list(STATUS_COLORS.keys()))
    selected_line = st.selectbox("Filter by Production Line", ["All"] + PRODUCTION_LINES)
    vin_search = st.text_input("Search VIN (partial match allowed)").strip().upper()
    if st.button("Reset Filters"):
        selected_status = "All"
        selected_line = "All"
        vin_search = ""

# Apply filters
filtered_df = df.copy()

if "VIN" in filtered_df.columns:
    if vin_search:
        filtered_df = filtered_df[filtered_df["VIN"].str.upper().str.contains(vin_search)]
    if selected_status != "All":
        if selected_status == "Completed":
            filtered_df = filtered_df[filtered_df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
        else:
            filtered_df = filtered_df[filtered_df.apply(lambda row: row.get(row["Current Line"], None) == selected_status, axis=1)]
    if selected_line != "All":
        filtered_df = filtered_df[filtered_df["Current Line"] == selected_line]

    st.sidebar.markdown(f"**Matching Vehicles:** {len(filtered_df)}")
    valid_vins = filtered_df["VIN"].tolist()
    col1, col2 = st.columns([1, 3])
    selected_vin = col1.selectbox("Select Vehicle (VIN)", valid_vins) if valid_vins else None
else:
    st.sidebar.error("❌ 'VIN' column not found in Google Sheet. Please ensure the header row is correct.")
    selected_vin = None

# Visualize production flow
def create_flow_chart(row):
    flow_data = [
        {
            "Production Line": line,
            "Status": row.get(line, "Not Started"),
            "Color": STATUS_COLORS.get(row.get(line), "#808080")
        } for line in PRODUCTION_LINES
    ]
    fig = px.bar(
        pd.DataFrame(flow_data),
        x="Production Line",
        color="Status",
        color_discrete_map=STATUS_COLORS,
        title=f"Production Flow for {row['VIN']}",
        text="Status"
    )
    fig.update_layout(xaxis_title="", yaxis_title="", showlegend=False, height=400)
    fig.update_traces(textposition='outside')
    return fig

if selected_vin:
    selected_row = df[df["VIN"] == selected_vin].iloc[0]
    st.plotly_chart(create_flow_chart(selected_row), use_container_width=True)
    status_df = filtered_df[["VIN", "Model", "Current Line", "Last Updated"] + PRODUCTION_LINES]
    st.dataframe(status_df, height=600, use_container_width=True)
    st.download_button("⬇️ Download Filtered Data as CSV", status_df.to_csv(index=False), "vehicle_status.csv")

# Add vehicle
with st.expander("✏️ Add New Vehicle"):
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

# Update vehicle
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
            
