import json
import pytz
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def load_chrome_history(chrome_file):
    """Extract browsing history from Chrome JSON session data."""
    with open(chrome_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = []
    eastern = pytz.timezone("US/Eastern")

    # Extract history from session tabs
    for session in data.get("Session", []):
        tab = session.get("tab", {})
        for entry in tab.get("navigation", []):
            timestamp_s = entry.get("timestamp_msec", 0) / 1000  # Convert milliseconds to seconds
            dt_utc = datetime.utcfromtimestamp(timestamp_s).replace(tzinfo=pytz.utc)
            dt_est = dt_utc.astimezone(eastern)

            records.append({"datetime_est": dt_est, "url": entry.get("virtual_url", ""), "title": entry.get("title", "")})

    return pd.DataFrame(records)

def load_safari_history(safari_file):
    """Extract browsing history from Safari JSON data."""
    with open(safari_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = []
    eastern = pytz.timezone("US/Eastern")

    for entry in data.get("history", []):
        timestamp_s = entry.get("time_usec", 0) / 1e6  # Convert microseconds to seconds
        dt_utc = datetime.utcfromtimestamp(timestamp_s).replace(tzinfo=pytz.utc)
        dt_est = dt_utc.astimezone(eastern)

        records.append({"datetime_est": dt_est, "url": entry.get("url", ""), "title": entry.get("title", "")})

    return pd.DataFrame(records)

def filter_to_january_2025(df):
    """Filter browsing history to only include January 2025 records."""
    eastern = pytz.timezone("US/Eastern")
    start_jan = eastern.localize(datetime(2025, 1, 1, 0, 0, 0))
    end_jan = eastern.localize(datetime(2025, 1, 31, 23, 59, 59))
    return df[(df["datetime_est"] >= start_jan) & (df["datetime_est"] <= end_jan)].copy()

def aggregate_hourly_activity(df):
    """Aggregate browsing activity by hour per day."""
    df["date"] = df["datetime_est"].dt.date
    df["hour"] = df["datetime_est"].dt.hour
    activity = df.groupby(["date", "hour"]).size().unstack(fill_value=0)
    return activity.reindex(columns=range(24), fill_value=0)

def compute_sleep_range(activity, min_inactive_hours=5):
    """Determine inferred sleep range based on inactivity periods."""
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

        if current_start is not None and current_length >= min_inactive_hours:
            longest_block = (current_start, 23)
            longest_length = current_length

        results.append({
            "date": date,
            "sleep_start_hour": longest_block[0] if longest_block else None,
            "sleep_end_hour": longest_block[1] if longest_block else None,
            "sleep_duration_hours": longest_length if longest_block else None
        })

    return pd.DataFrame(results)

def plot_sleep_gantt(sleep_df):
    """Plot inferred sleep intervals as a Gantt chart."""
    sleep_df_valid = sleep_df.dropna(subset=["sleep_start_hour", "sleep_end_hour"]).copy()
    sleep_df_valid.sort_values("date", inplace=True)
    
    fig, ax = plt.subplots(figsize=(10, max(3, 0.3 * len(sleep_df_valid) + 2)))
    for i, row in enumerate(sleep_df_valid.itertuples()):
        ax.barh(i, row.sleep_duration_hours, left=row.sleep_start_hour, height=0.4, color="red", alpha=0.7)
    
    ax.set_yticks(range(len(sleep_df_valid)))
    ax.set_yticklabels(sleep_df_valid["date"].astype(str))
    ax.set_xlabel("Hour of Day (US/Eastern)")
    ax.set_title("Inferred Sleep Intervals for January 2025")
    ax.set_xlim(0, 24)
    plt.tight_layout()
    plt.show()

def main():
    chrome_file = "History.json"
    safari_file = "safari.json"

    # Load and merge history
    chrome_df = load_chrome_history(chrome_file)
    safari_df = load_safari_history(safari_file)
    merged = pd.concat([chrome_df, safari_df], ignore_index=True)
    merged = filter_to_january_2025(merged)

    # Convert timestamps to naive format for Excel export
    merged["datetime_est"] = merged["datetime_est"].dt.tz_localize(None)

    # Compute hourly activity
    activity = aggregate_hourly_activity(merged)

    # Compute sleep range
    sleep_ranges_df = compute_sleep_range(activity)

    # Export sleep data
    output_file = "sleep_ranges_per_date.xlsx"
    sleep_ranges_df.to_excel(output_file, index=False)
    print(f"Exported sleep ranges for {len(sleep_ranges_df)} dates to '{output_file}'.")

    # Plot results
    plot_sleep_gantt(sleep_ranges_df)

if __name__ == "__main__":
    main()
