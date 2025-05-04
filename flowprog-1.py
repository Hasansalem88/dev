# Full updated Streamlit app with fixed tabs and wider Excel cells

import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import gspread
from google.oauth2 import service_account
from io import BytesIO
import xlsxwriter

# Page setup
st.set_page_config(layout="wide", page_title="🚗 Assembly Line Tracker")
st.title(":blue_car: Vehicle Production Flow Dashboard")

# Access credentials from secrets
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

STATUS_COLORS = {
    "In Progress": "#FFA500",
    "Completed": "#008000",
    "Repair Needed": "#FF0000",
}

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

# Sidebar Navigation
st.sidebar.title("📂 Report Menu")
report_option = st.sidebar.radio("Select Report Section", [
    "Dashboard Summary",
    "Production Trend",
    "Line Progress",
    "Vehicle Details",
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

filtered_df = df.copy()
if selected_status != "All":
    if selected_status == "Completed":
        filtered_df = filtered_df[filtered_df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
    else:
        filtered_df = filtered_df[filtered_df.apply(lambda row: row.get(row["Current Line"], None) == selected_status, axis=1)]
if selected_line != "All":
    filtered_df = filtered_df[filtered_df["Current Line"] == selected_line]

if report_option == "Dashboard Summary":
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

elif report_option == "Production Trend":
    st.subheader("📈 Daily Completions Trend")
    trend_df = df.copy()
    trend_df["Last Updated"] = pd.to_datetime(trend_df["Last Updated"], errors="coerce")
    trend_df = trend_df[trend_df["Last Updated"].notna() & trend_df.apply(lambda row: all(row.get(line) == "Completed" for line in PRODUCTION_LINES), axis=1)]
    trend_df["Completed Date"] = trend_df["Last Updated"].dt.date
    trend = trend_df.groupby("Completed Date").size().reset_index(name="Completed Count")
    if not trend.empty:
        st.line_chart(trend.set_index("Completed Date"))
    else:
        st.info("ℹ️ No completed vehicles yet to display in trend.")

elif report_option == "Line Progress":
    st.subheader("🏭 Line Progress Tracker")
    line_counts = df["Current Line"].value_counts().reindex(PRODUCTION_LINES, fill_value=0).reset_index()
    line_counts.columns = ["Production Line", "Vehicle Count"]
    fig_progress = px.bar(line_counts, x="Production Line", y="Vehicle Count", text="Vehicle Count")
    fig_progress.update_traces(textposition="outside")
    st.plotly_chart(fig_progress, use_container_width=True)

elif report_option == "Vehicle Details":
    st.subheader("🚘 All Vehicle Details")
    columns_to_display = [col for col in df.columns if not col.endswith("_time") and col != "Start Time"]

    def color_cells(val):
        status_colors = {
            "Completed": "background-color: #d4edda",
            "In Progress": "background-color: #fff3cd",
            "Repair Needed": "background-color: #f8d7da"
        }
        return status_colors.get(val, "")

    def apply_style_to_df(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for i, row in df.iterrows():
            for col in df.columns:
                styles.at[i, col] = color_cells(row[col])
        return styles

    styled_df = df[columns_to_display]
    styles = apply_style_to_df(styled_df)
    st.write(styled_df.style.apply(lambda x: styles.loc[x.name], axis=1))

    # Download button for XLSX with formatting
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    styled_df.to_excel(writer, index=False, sheet_name='Vehicle Details')
    workbook = writer.book
    worksheet = writer.sheets['Vehicle Details']
    
    for idx, col in enumerate(styled_df.columns):
        max_width = max(styled_df[col].astype(str).map(len).max(), len(col)) + 2
        worksheet.set_column(idx, idx, max_width)

    format_green = workbook.add_format({'bg_color': '#d4edda'})
    format_yellow = workbook.add_format({'bg_color': '#fff3cd'})
    format_red = workbook.add_format({'bg_color': '#f8d7da'})

    for row_idx, row in styled_df.iterrows():
        for col_idx, val in enumerate(row):
            fmt = None
            if val == "Completed":
                fmt = format_green
            elif val == "In Progress":
                fmt = format_yellow
            elif val == "Repair Needed":
                fmt = format_red
            if fmt:
                worksheet.write(row_idx + 1, col_idx, val, fmt)

    writer.close()
    output.seek(0)

    st.download_button(
        label="📥 Download XLSX with Formatting",
        data=output,
        file_name="Vehicle_Details.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

elif report_option == "Add/Update Vehicle":
    st.subheader("✏️ Add or Update Vehicle")
    with st.expander("Add New Vehicle", expanded=True):
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

    with st.expander("Update Vehicle Status"):
        if not df.empty:
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
