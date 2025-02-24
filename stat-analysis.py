import json
import pytz
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

def load_chrome_history(chrome_file):
    """
    Grab chrome history from json file, outputs a dataframe with all records and timestamp.
    """
    with open(chrome_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    history_list = data.get("Browser History", [])
    records = []
    eastern = pytz.timezone("US/Eastern")
    for entry in history_list:
        # Convert microseconds to seconds
        timestamp_s = entry["time_usec"] / 1e6
        dt_utc = datetime.utcfromtimestamp(timestamp_s)
        # Convert to US/Eastern
        dt_est = eastern.localize(dt_utc)
        records.append({"datetime_est": dt_est})

    return pd.DataFrame(records)

def load_safari_history(safari_file):
    """
    Grabs safari history, loads into dataframe with timestamp for each record.
    """
    with open(safari_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    history_list = data.get("history", [])
    records = []
    eastern = pytz.timezone("US/Eastern")
    for entry in history_list:
        time_usec = entry.get("destination_time_usec")
        if not time_usec:
            continue
        timestamp_s = time_usec / 1e6
        dt_utc = datetime.utcfromtimestamp(timestamp_s)
        dt_est = eastern.localize(dt_utc)
        records.append({"datetime_est": dt_est})

    return pd.DataFrame(records)

def filter_to_january_2025(df):
    """
    Filters the DataFrame to only include entries from 1/1 to 1/31
    """
    eastern = pytz.timezone("US/Eastern")
    start_jan = eastern.localize(datetime(2025, 1, 1, 0, 0, 0))
    end_jan = eastern.localize(datetime(2025, 1, 31, 23, 59, 59))
    mask = (df["datetime_est"] >= start_jan) & (df["datetime_est"] <= end_jan)
    return df.loc[mask].copy()

def aggregate_hourly_activity(df):
    """
    Groups the data by date and hour (0-23), counting the number of events per hour.
    Returns a DataFrame with dates as the index and columns 0 through 23 (each representing an hour).
    """
    df["date"] = df["datetime_est"].dt.date
    df["hour"] = df["datetime_est"].dt.hour
    activity = df.groupby(["date", "hour"]).size().unstack(fill_value=0)
    activity = activity.reindex(columns=range(24), fill_value=0)
    return activity


# ---------------------------
# 5. Compute Inferred Sleep Range Per Date
# ---------------------------
def compute_sleep_range(activity, min_inactive_hours=5):
    """
    Finds longest contiguous block of 5 or greater hours.
    Returns a DataFrame with columns: [date, sleep_start_hour, sleep_end_hour, sleep_duration_hours].
    """
    results = []
    for date, row in activity.iterrows():
        longest_block = None
        longest_length = 0
        current_start = None
        current_length = 0
        for hour in range(24):
            if row.get(hour, 0) == 0:
                if current_start is None:
                    current_start = hour
                    current_length = 1
                else:
                    current_length += 1
            else:
                if current_start is not None:
                    if current_length >= min_inactive_hours and current_length > longest_length:
                        longest_block = (current_start, hour - 1)
                        longest_length = current_length
                    current_start = None
                    current_length = 0
        if current_start is not None:
            if current_length >= min_inactive_hours and current_length > longest_length:
                longest_block = (current_start, 23)
                longest_length = current_length

        if longest_block is not None:
            results.append({
                "date": date,
                "sleep_start_hour": longest_block[0],
                "sleep_end_hour": longest_block[1],
                "sleep_duration_hours": longest_length
            })
        else:
            results.append({
                "date": date,
                "sleep_start_hour": None,
                "sleep_end_hour": None,
                "sleep_duration_hours": None
            })

    return pd.DataFrame(results)


def plot_sleep_gantt(sleep_df):
    """
    Plots a Gantt chart–style horizontal bar chart showing sleep intervals for each date.
    X-axis: Hours of day (0 to 24)
    Y-axis: Dates
    """
    sleep_df_valid = sleep_df.dropna(subset=["sleep_start_hour", "sleep_end_hour"]).copy()
    sleep_df_valid.sort_values("date", inplace=True)
    sleep_df_valid.reset_index(drop=True, inplace=True)
    y_positions = range(len(sleep_df_valid))
    date_labels = sleep_df_valid["date"].astype(str)
    fig, ax = plt.subplots(figsize=(10, 0.3 * len(sleep_df_valid) + 2))
    for i, row in sleep_df_valid.iterrows():
        start = row["sleep_start_hour"]
        duration = row["sleep_duration_hours"]
        ax.barh(i, duration, left=start, height=0.4, color="red", alpha=0.7)
    ax.set_yticks(list(y_positions))
    ax.set_yticklabels(date_labels)
    ax.set_xlabel("Hour of Day (US/Eastern)")
    ax.set_title("Inferred Sleep Intervals for January 2025")
    ax.set_xlim(0, 24)
    plt.tight_layout()
    plt.show()

def main():
    chrome_file = "History.json"
    safari_file = "safari.json"

    # Load history data
    chrome_df = load_chrome_history(chrome_file)
    safari_df = load_safari_history(safari_file)

    # Merge and filter to January 2025
    merged = pd.concat([chrome_df, safari_df], ignore_index=True)
    merged = filter_to_january_2025(merged)

    # Remove timezone info for Excel export
    merged["datetime_est"] = merged["datetime_est"].dt.tz_localize(None)

    # Aggregate hourly activity
    activity = aggregate_hourly_activity(merged)

    # Compute sleep range per date
    sleep_ranges_df = compute_sleep_range(activity, min_inactive_hours=5)

    # Export sleep ranges to Excel
    output_file = "sleep_ranges_per_date.xlsx"
    sleep_ranges_df.to_excel(output_file, index=False)
    print(f"Exported sleep ranges for {len(sleep_ranges_df)} dates to '{output_file}'.")

    # Plot a Gantt chart of sleep intervals
    plot_sleep_gantt(sleep_ranges_df)


if __name__ == "__main__":
    main()