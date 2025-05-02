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
        # Sheet is empty, initialize columns
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

    # 1. تأكد من تحويل كل القيم إلى string أو فارغة
    for col in df_copy.columns:
        df_copy[col] = df_copy[col].apply(
            lambda x: x.isoformat() if isinstance(x, (datetime, pd.Timestamp)) and not pd.isnull(x)
            else "" if pd.isnull(x)
            else str(x)
        )

    # 2. تنظيف أي NaN
    df_copy = df_copy.fillna("")

    # 3. مسح الشيت وتحديثه بشكل آمن
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
    selected_vin = st.sidebar.selectbox("Select Vehicle (VIN)", valid_vins) if valid_vins else None
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
    st.container().write(f"**Vehicle VIN: {selected_vin}**")
    st.container().plotly_chart(create_flow_chart(selected_row), use_container_width=True)
    st.container().dataframe(filtered_df[["VIN", "Model", "Current Line", "Last Updated"] + PRODUCTION_LINES], height=600, use_container_width=True)

# --- Daily Summary ---
with st.expander("📅 Daily Production Summary", expanded=True):
    col1, col2, col3 = st.columns(3)
    df["Start Time"] = pd.to_datetime(df["Start Time"], errors="coerce")
    df["Last Updated"] = pd.to_datetime(df["Last Updated"], errors="coerce")
    today = pd.Timestamp.now().normalize()

    vehicles_today = df[df["Start Time"].dt.normalize() == today]
    completed_today = df[(
        df["Last Updated"].dt.normalize() == today) &
        (df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1))
    ]
    in_progress = df[df["Current Line"] != "Delivery"]

    col1.metric("🆕 Vehicles Added Today", len(vehicles_today))
    col2.metric("✅ Completed Today", len(completed_today))
    col3.metric("🔄 Still In Progress", len(in_progress))

# --- Daily completions trend ---
with st.expander("📈 Daily Completions Trend", expanded=True):
    daily_counts = df[df["Last Updated"].notna()].copy()
    daily_counts["Completed Date"] = daily_counts["Last Updated"].dt.date
    daily_counts = daily_counts[(
        daily_counts.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)
    )]
    trend = daily_counts.groupby("Completed Date").size().reset_index(name="Completed Count")
    if not trend.empty:
        st.line_chart(trend.rename(columns={"Completed Date": "index"}).set_index("index"))
    else:
        st.info("ℹ️ No completed vehicles yet to display in trend.")

# --- Line Progress Tracker ---
with st.expander("🏭 Line Progress Tracker", expanded=True):
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

# Add vehicle
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
