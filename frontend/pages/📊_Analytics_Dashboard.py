# File path: frontend/pages/📊_Analytics_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import calendar
import io
import logging
import os
import sys
from pathlib import Path

# --- Determine Project Root and Add to Python Path ---
try:
    # Get the directory of the current file
    SCRIPT_DIR = Path(__file__).resolve().parent
    # Calculate the project root by going up three levels
    PROJECT_ROOT = SCRIPT_DIR.parent.parent
except NameError:
    # Handle cases where __file__ is not defined (e.g., interactive mode)
    PROJECT_ROOT = Path.cwd()
    logging.warning(f"Could not determine script directory, assuming project root is CWD: {PROJECT_ROOT}")

# Add the project root to the Python path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    logging.info(f"Added project root to sys.path: {PROJECT_ROOT}")

# Now import the backend functions
from backend.db import get_tickets_df # Ensure this fetches necessary columns
from backend.openai_agent import generate_insights # Assuming this exists

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - DASHBOARD - %(message)s')

# --- Page Configuration ---
st.set_page_config(page_title="Enhanced Analytics Dashboard", layout="wide")
st.title("📊 Ticket Analytics Dashboard")
st.markdown("Explore trends, status, resolution times, and insights from ticket data.")

# --- Helper Functions ---
@st.cache_data # Cache the data loading
def load_data():
    """Loads ticket data and performs initial cleaning."""
    logging.info("Attempting to load data from DB...")
    try:
        df = get_tickets_df()
        if df is None or df.empty:
             logging.warning("get_tickets_df() returned None or empty DataFrame.")
             return pd.DataFrame(), False, False # Return flags indicating missing columns

        logging.info(f"Successfully loaded {len(df)} rows from DB.")
        has_status = 'status' in df.columns
        has_resolved_at = 'resolved_at' in df.columns
        logging.info(f"Schema check: has_status={has_status}, has_resolved_at={has_resolved_at}")

        # --- Data Cleaning & Feature Engineering ---
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df.dropna(subset=['created_at'], inplace=True) # Drop rows with invalid creation dates

        df['creation_date'] = df['created_at'].dt.date
        df['creation_day_name'] = df['created_at'].dt.day_name()
        # Ensure Category is treated as string, fillna AFTER type conversion
        df['category'] = df['category'].fillna('Unknown').astype(str)
        df['file_type'] = df['file_type'].fillna('Unknown').astype(str)

        if has_status:
            df['status'] = df['status'].fillna('Unknown').astype(str)
        else:
            df['status'] = 'Unknown'

        df['resolution_time_hours'] = None
        if has_resolved_at:
            df['resolved_at'] = pd.to_datetime(df['resolved_at'], errors='coerce')
            if has_status:
                closed_mask = ( (df['status'] == 'Closed') & df['resolved_at'].notna() & df['created_at'].notna() & (df['resolved_at'] > df['created_at']) )
                if closed_mask.any():
                    df.loc[closed_mask, 'resolution_time_hours'] = (df.loc[closed_mask, 'resolved_at'] - df.loc[closed_mask, 'created_at']) / pd.Timedelta(hours=1)
                    logging.info(f"Calculated resolution time for {closed_mask.sum()} tickets.")
        return df, has_status, has_resolved_at

    except Exception as e:
        logging.error(f"Error during data loading or processing: {e}", exc_info=True)
        return pd.DataFrame(), False, False


def format_date(dt):
    if pd.isnull(dt): return "N/A"
    if isinstance(dt, (datetime, date)): return dt.strftime("%b %d, %Y")
    return str(dt)

def format_timedelta_hours(hours):
    if pd.isnull(hours) or hours < 0: return "N/A"
    days = int(hours // 24)
    rem_hours = int(hours % 24)
    parts = []
    if days > 0: parts.append(f"{days} day{'s' if days > 1 else ''}")
    if rem_hours > 0 or days == 0: parts.append(f"{rem_hours} hr{'s' if rem_hours > 1 else ''}")
    return " ".join(parts) if parts else "0 hrs"


# --- Load Data ---
df_full, has_status_col, has_resolved_col = load_data()

# Display warnings if columns missing (can be commented out if preferred)
# if not df_full.empty:
#     if not has_status_col: st.sidebar.warning("'status' column missing.", icon="⚠️")
#     if not has_resolved_col: st.sidebar.warning("'resolved_at' column missing.", icon="⚠️")

# --- Sidebar Filters ---
st.sidebar.header("⚙️ Dashboard Filters")

if df_full.empty:
    st.warning("⚠️ No ticket data available to display.")
    st.stop()

# Date Range Filter
min_date = df_full['creation_date'].min()
max_date = df_full['creation_date'].max()
default_start_date = max(min_date, max_date - timedelta(days=30))

date_range = st.sidebar.date_input( "Select Date Range", value=(default_start_date, max_date), min_value=min_date, max_value=max_date)
start_date, end_date = date_range if len(date_range) == 2 else (default_start_date, max_date)
if start_date > end_date: start_date = end_date

# Category Filter
all_categories = sorted(df_full['category'].unique().tolist())
# Exclude 'Pending' and 'Unknown' from default selection if desired, but keep in options
default_categories = [cat for cat in all_categories if cat not in ['Pending', 'Unknown']]
selected_categories = st.sidebar.multiselect("Filter Categories", options=all_categories, default=default_categories if default_categories else all_categories)
# Allow selecting 'All' implicitly if nothing is selected OR explicitly
show_all_categories = not selected_categories # If list is empty, show all

# Status Filter
selected_status = ['All']
if has_status_col:
    all_status = ['All'] + sorted(df_full['status'].unique().tolist())
    selected_status = st.sidebar.multiselect("Filter Status", options=all_status, default=['All'])

# --- NEW: Option to Hide Pending Category ---
hide_pending = st.sidebar.checkbox("Hide 'Pending' Category", value=False, help="Exclude tickets with category 'Pending' from charts and metrics below.")


# Time Aggregation Filter
time_agg = st.sidebar.radio("Aggregate Trend By:", ('Daily', 'Weekly', 'Monthly'), index=0, horizontal=True)


# --- Apply Filters ---
# Start with base date filter
df_filtered = df_full[ (df_full['creation_date'] >= start_date) & (df_full['creation_date'] <= end_date) ]

# Apply category filter (handle 'All' case)
if not show_all_categories:
    df_filtered = df_filtered[df_filtered['category'].isin(selected_categories)]

# Apply status filter (handle 'All' case)
if has_status_col and 'All' not in selected_status and selected_status:
    df_filtered = df_filtered[df_filtered['status'].isin(selected_status)]

# --- Apply Hide Pending Filter AFTER other filters ---
if hide_pending:
     df_display = df_filtered[df_filtered['category'] != 'Pending'].copy()
     st.sidebar.info(f"Hiding tickets with 'Pending' category.")
else:
     df_display = df_filtered.copy() # Use the filtered data directly

if df_display.empty:
    st.warning(f"⚠️ No ticket data found for the selected filters (including 'Hide Pending' if checked).")
    st.stop()


# --- Dashboard Metrics ---
st.header("📊 Key Metrics Overview")
with st.container(border=True): # Group metrics visually
    total_tickets_d = len(df_display)
    tickets_today_d = len(df_display[df_display['creation_date'] == date.today()])
    unique_categories_d = df_display['category'].nunique() # Based on displayed data
    most_common_category_d = df_display['category'].mode()[0] if not df_display.empty else "N/A"

    open_tickets_d = 'N/A'
    closed_tickets_d = 'N/A'
    avg_res_time_d = None

    if has_status_col:
        open_statuses = ['Open', 'In Progress', 'Pending', 'New', 'Reopened'] # Adjust as needed
        open_tickets_d = df_display[df_display['status'].isin(open_statuses)].shape[0]
        closed_tickets_d = df_display[df_display['status'] == 'Closed'].shape[0]

    if has_resolved_col and 'resolution_time_hours' in df_display.columns:
        valid_res_times = df_display.loc[df_display['resolution_time_hours'].notna() & (df_display['resolution_time_hours'] >= 0), 'resolution_time_hours']
        if not valid_res_times.empty:
            avg_res_time_d = valid_res_times.mean()

    # Display metrics in columns
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total Tickets Shown", total_tickets_d, help="Total tickets matching all active filters.")
    metric_cols[1].metric("Tickets Today", tickets_today_d, help="Tickets created today matching filters.")
    metric_cols[2].metric("Unique Categories Shown", unique_categories_d, help="Number of distinct categories in the filtered data.")
    metric_cols[3].metric("Most Common Category", most_common_category_d, help="Most frequent category in the filtered data.")

    if has_status_col or avg_res_time_d is not None:
        metric_cols_2 = st.columns(4)
        col_idx = 0
        if has_status_col:
            metric_cols_2[col_idx].metric("Open Tickets", open_tickets_d, help="Tickets with status like Open, In Progress, Pending...")
            col_idx += 1
            metric_cols_2[col_idx].metric("Closed Tickets", closed_tickets_d, help="Tickets with status 'Closed'")
            col_idx +=1
        if avg_res_time_d is not None:
            metric_cols_2[col_idx].metric("Avg. Resolution Time", format_timedelta_hours(avg_res_time_d), help="Average time (Created to Resolved) for 'Closed' tickets shown.")
            col_idx += 1

st.caption(f"Displaying data from {format_date(start_date)} to {format_date(end_date)}. {len(df_filtered) - len(df_display) if hide_pending else 0} 'Pending' tickets hidden.")
st.divider()


# --- AI-Generated Insights (Optional - keep as is or remove if focusing only on visuals) ---
# (Keeping the previous AI Insight code - can be commented out if not needed now)
ai_prompt_context = "Analyze the filtered ticket data shown."
if has_status_col: ai_prompt_context += " Consider ticket statuses."
if has_resolved_col and avg_res_time_d is not None: ai_prompt_context += f" The average resolution time is roughly {format_timedelta_hours(avg_res_time_d)}."

if len(df_display) >= 10:
    with st.expander("🔍 AI-Powered Insights (Based on Shown Data)", expanded=False):
        try:
            insights = generate_insights(df_display)
            st.info(insights)
        except Exception as e:
            st.error(f"Failed to generate insights: {e}")
# Corrected Line: else is now aligned with the 'if' above
else:
    st.info(f"ℹ️ At least 10 tickets needed in the view to generate AI insights (currently showing {len(df_display)}).")
st.divider()


# --- Visualizations ---
st.header("📈 Data Visualizations")

# Define colors - explicitly set 'Pending' and 'Unknown' to gray
category_colors = px.colors.qualitative.Pastel # Base palette
color_map = {cat: color for cat, color in zip(df_display['category'].unique(), category_colors)}
color_map['Pending'] = '#CCCCCC' # Assign gray to Pending
color_map['Unknown'] = '#E0E0E0' # Assign slightly different gray to Unknown

# Define tabs dynamically based on available data
viz_tabs_list = ["📊 By Category", "📅 Over Time", "🧩 Other Breakdowns"] # Reorganize tabs
status_resolution_tab_name = "⏳ Status & Resolution"
if has_status_col or (has_resolved_col and 'resolution_time_hours' in df_display.columns):
     viz_tabs_list.insert(2, status_resolution_tab_name) # Insert as 3rd tab

tabs = st.tabs(viz_tabs_list)
tab_map = {name: tab for name, tab in zip(viz_tabs_list, tabs)}

# --- Populate Tab 1: By Category ---
with tab_map["📊 By Category"]:
    st.subheader("Ticket Distribution by Category")
    st.markdown("Shows the number of tickets for each category based on the filters applied.")
    category_counts = df_display['category'].value_counts().reset_index()
    category_counts.columns = ['category', 'count']

    if not category_counts.empty:
        fig_cat = px.bar(
            category_counts.sort_values('count', ascending=False), # Sort bars
            x='category',
            y='count',
            title="<b>Ticket Count per Category</b>",
            labels={'category': 'Category', 'count': 'Number of Tickets'},
            template="plotly_white",
            color='category',
            color_discrete_map=color_map # Apply custom color map
        )
        fig_cat.update_layout(
            title_x=0.5, # Center title
            xaxis_title=None,
            yaxis_title="Number of Tickets",
            showlegend=False # Legend is redundant if bars are colored and labeled
        )
        # Customize hover text
        fig_cat.update_traces(hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>')
        st.plotly_chart(fig_cat, use_container_width=True)

        # Optional: Add summary table next to chart
        # with st.container():
        #     st.dataframe(category_counts, hide_index=True, use_container_width=True)
    else:
        st.info("No category data to display for the current filters.")


# --- Populate Tab 2: Over Time ---
with tab_map["📅 Over Time"]:
    st.subheader(f"Ticket Volume Over Time ({time_agg})")
    st.markdown(f"Shows the number of tickets created per {time_agg.lower()} based on the filters.")
    try:
        df_time_indexed = df_display.set_index(pd.to_datetime(df_display['created_at']))
        if df_time_indexed.index.tz is not None:
             df_time_indexed.index = df_time_indexed.index.tz_localize(None)

        resample_rule = {'Daily': 'D', 'Weekly': 'W-MON', 'Monthly': 'ME'}[time_agg]
        time_counts = df_time_indexed.resample(resample_rule).size().reset_index(name='count')
        time_counts.columns = ['time_period', 'count']

        if not time_counts.empty:
            fig_trend = px.line(
                time_counts, x='time_period', y='count',
                title="<b>Ticket Volume ({time_agg})</b>",
                labels={'time_period': time_agg + ' Period', 'count': 'Number of Tickets'},
                template="plotly_white", markers=True
            )
            fig_trend.update_layout(
                title_x=0.5,
                hovermode="x unified", # Improved hover for line charts
                yaxis_title="Number of Tickets"
            )
            fig_trend.update_traces(hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Tickets: %{y}<extra></extra>')
            st.plotly_chart(fig_trend, use_container_width=True)
        else: st.info("No trend data for the selected period/aggregation.")
    except Exception as e:
        logging.error(f"Error creating trend chart: {e}", exc_info=True)
        st.error("Could not generate trend chart.")


# --- Populate Tab 3: Status & Resolution (Conditional) ---
if status_resolution_tab_name in tab_map:
    with tab_map[status_resolution_tab_name]:
        st.subheader("Status & Resolution Analysis")
        if has_status_col:
            col_status_dist, col_res_time = st.columns(2)
            with col_status_dist:
                st.markdown("###### Status Distribution")
                status_counts = df_display['status'].value_counts().reset_index()
                status_counts.columns = ['status', 'count']
                if not status_counts.empty:
                    fig_status = px.bar(
                        status_counts.sort_values('count', ascending=False), x='status', y='count',
                        title="<b>Ticket Count by Status</b>", template="plotly_white", color='status'
                    )
                    fig_status.update_layout(title_x=0.5, xaxis_title=None, showlegend=False)
                    fig_status.update_traces(hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>')
                    st.plotly_chart(fig_status, use_container_width=True)
                else: st.info("No status data.")

            with col_res_time:
                st.markdown("###### Avg. Resolution Time")
                if has_resolved_col and 'resolution_time_hours' in df_display.columns:
                    st.markdown("Average time (in hours) for 'Closed' tickets, grouped by Category.")
                    valid_res_df = df_display[df_display['resolution_time_hours'].notna() & (df_display['resolution_time_hours'] >= 0)]
                    if not valid_res_df.empty:
                        res_time_cat = valid_res_df.groupby('category')['resolution_time_hours'].mean().reset_index()
                        if not res_time_cat.empty:
                            fig_res_cat = px.bar(
                                res_time_cat.sort_values('resolution_time_hours', ascending=False), x='category', y='resolution_time_hours',
                                title="<b>Avg. Resolution Time by Category</b>",
                                labels={'category': 'Category', 'resolution_time_hours': 'Average Hours to Resolve'},
                                template="plotly_white", color='category', color_discrete_map=color_map
                            )
                            fig_res_cat.update_layout(title_x=0.5, xaxis_title=None, showlegend=False)
                            fig_res_cat.update_traces(hovertemplate='<b>%{x}</b><br>Avg Hours: %{y:.1f}<extra></extra>')
                            st.plotly_chart(fig_res_cat, use_container_width=True)
                        else: st.info("Could not calculate resolution time per category.")
                    else: st.info("No valid resolution time data found for this period.")
                else:
                    st.info("Resolution time data not available.")
        else:
            st.info("Status data column ('status') not available.")


# --- Populate Tab 4: Other Breakdowns ---
other_breakdown_tab = tab_map["🧩 Other Breakdowns"]
with other_breakdown_tab:
    st.subheader("Other Ticket Breakdowns")
    col_dow, col_file = st.columns(2)

    with col_dow:
        st.markdown("###### By Day of Week Created")
        day_counts = df_display['creation_day_name'].value_counts()
        day_order = list(calendar.day_name)
        day_counts = day_counts.reindex(day_order).fillna(0).reset_index()
        day_counts.columns = ['day', 'count']
        if not day_counts[day_counts['count'] > 0].empty:
            fig_day = px.bar(
                day_counts, x='day', y='count',
                title="<b>Tickets by Day of Week</b>",
                labels={'day': 'Day of Week', 'count': 'Number of Tickets'}, template="plotly_white"
            )
            fig_day.update_layout(title_x=0.5)
            fig_day.update_traces(hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>')
            st.plotly_chart(fig_day, use_container_width=True)
        else: st.info("No day-of-week data.")

    with col_file:
         st.markdown("###### By Source File Type")
         file_type_counts = df_display['file_type'].value_counts().reset_index()
         file_type_counts.columns = ['file_type', 'count']
         if not file_type_counts.empty:
            fig_file = px.pie(
                file_type_counts, names='file_type', values='count',
                title="<b>Tickets by Source File Type</b>", hole=0.4,
                template="plotly_white", color_discrete_sequence=px.colors.sequential.Blues_r
            )
            fig_file.update_layout(title_x=0.5, showlegend=True) # Show legend for pie
            fig_file.update_traces(textposition='outside', textinfo='percent+label', hovertemplate='<b>%{label}</b><br>Count: %{value}<br>(%{percent})<extra></extra>')
            st.plotly_chart(fig_file, use_container_width=True)
         else: st.info("No file type data.")


st.divider()

# --- Data Export & Raw Data Table (Using df_display) ---
# (Keeping previous robust export/raw data table code, but ensure it uses df_display)
st.header("⬇️ Data Export & Table View")

with st.container(border=True):
    col_export, col_raw_view = st.columns([1,3]) # Allocate less space for button

    with col_export:
        st.subheader("Export Data")
        st.markdown("Download the data currently displayed in the dashboard charts and tables.")

        # Define columns ideally wanted
        desired_export_columns = [ 'id', 'title', 'category', 'status', 'file_type', 'created_at', 'resolved_at', 'resolution_time_hours' ]
        # Get columns that exist in the DISPLAY dataframe
        existing_columns_in_display = df_display.columns.tolist()
        columns_to_export = [col for col in desired_export_columns if col in existing_columns_in_display]

        if columns_to_export:
            export_df = df_display[columns_to_export].copy()
            # Convert datetimes for CSV
            if 'created_at' in columns_to_export and hasattr(export_df['created_at'].dt, 'tz') and export_df['created_at'].dt.tz is not None:
                export_df['created_at'] = export_df['created_at'].dt.tz_localize(None)
            if 'resolved_at' in columns_to_export and hasattr(export_df['resolved_at'].dt, 'tz') and export_df['resolved_at'].dt.tz is not None:
                export_df['resolved_at'] = export_df['resolved_at'].dt.tz_localize(None)

            try:
                csv_buffer = io.BytesIO()
                export_df.to_csv(csv_buffer, index=False, encoding='utf-8')
                csv_buffer.seek(0)
                csv_data = csv_buffer.read()
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                st.download_button( label="📥 Download Shown Data as CSV", data=csv_data, file_name=f'displayed_tickets_{timestamp}.csv', mime='text/csv', help="Download the data currently shown based on filters")
            except Exception as e:
                 logging.error(f"Error creating CSV for download: {e}", exc_info=True)
                 st.error("Could not prepare data for download.")
        else:
            st.info("No data to export.")

    with col_raw_view:
        with st.expander("📋 View Raw Data Table (Filtered)", expanded=True): # Expand by default
            st.markdown(f"Displaying {len(df_display)} rows matching filters.")
            desired_display_cols_table = [ 'id', 'title', 'category', 'status', 'file_type', 'created_at', 'resolved_at', 'resolution_time_hours' ]
            display_cols_actual_table = [col for col in desired_display_cols_table if col in existing_columns_in_display]

            if display_cols_actual_table:
                rename_map = { 'id': 'ID', 'title': 'Title', 'category': 'Category', 'status': 'Status', 'file_type': 'Source Type', 'created_at': 'Created', 'resolved_at': 'Resolved', 'resolution_time_hours': 'Resolution Hrs' }
                display_df_table = df_display[display_cols_actual_table].rename(columns={k: v for k, v in rename_map.items() if k in display_cols_actual_table})
                col_config_map = { "Created": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"), "Resolved": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"), "Resolution Hrs": st.column_config.NumberColumn(format="%.1f hrs") }
                final_col_config = {ren_col_name: col_config_map[ren_col_name] for ren_col_name in display_df_table.columns if ren_col_name in col_config_map}

                st.dataframe( display_df_table, use_container_width=True, hide_index=True, column_config=final_col_config )
            else: st.warning("No data columns to display.")
