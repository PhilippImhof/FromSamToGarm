#!/usr/bin/env python3


import csv
import datetime
import glob
import os


def parse_day_time(value):
    """Parse Samsung Health day_time values from multiple export formats."""
    value = str(value).strip()

    # Newer exports often use epoch milliseconds.
    try:
        return datetime.datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Some exports use ISO-like datetime strings.
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(f"Unsupported day_time format: {value}")


def fetch_floor_data():
    """
    Fetch and consolidate the floors climbed data. There are normally multiple entries per day,
    because floors climbed seem to be stored whenever they are registered. So we have to group
    them all and add them up.
    """
    floor_files = sorted(
        glob.glob(
            "samsunghealth*/**/com.samsung.health.floors_climbed.*.csv",
            recursive=True,
        )
    )
    if len(floor_files) == 0:
        raise Exception("No floors data found.")
    filename = floor_files[-1]

    with open(filename, newline="") as floor_data:
        # Skip first line
        next(floor_data)
        reader = csv.DictReader(floor_data)
        floor_data = {}
        for row in reader:
            date = row["start_time"][0:10]
            floors = int(float(row["floor"]))
            # If there are floors for this date, add the newly read data to the existing value.
            # Otherwise, create a new key.
            if date in floor_data:
                floor_data[date] += floors
            else:
                floor_data[date] = floors

    return floor_data


def fetch_calorie_data():
    """
    Fetch the calorie data.
    """

    calorie_files = sorted(
        glob.glob(
            "samsunghealth*/**/com.samsung.shealth.calories_burned.details.*.csv",
            recursive=True,
        )
    )
    if len(calorie_files) == 0:
        raise Exception("No calorie data found.")
    filename = calorie_files[-1]

    with open(filename, newline="") as calories_data:
        # Skip first line
        next(calories_data)
        reader = csv.DictReader(calories_data)
        calorie_data = {}
        prefix = "com.samsung.shealth.calories_burned."
        for row in reader:
            date = parse_day_time(row[prefix + "day_time"])
            rest_calorie = float(row[prefix + "rest_calorie"])
            active_calorie = float(row[prefix + "active_calorie"])
            calorie_data[date] = int(round(rest_calorie + active_calorie, 0))

        return calorie_data


def fetch_activity_data():
    """
    Fetch the activity data.
    """

    activity_files = sorted(
        glob.glob(
            "samsunghealth*/**/com.samsung.shealth.activity.day_summary.*.csv",
            recursive=True,
        )
    )
    if len(activity_files) == 0:
        raise Exception("No activity data found.")
    filename = activity_files[-1]

    with open(filename, newline="") as activity_data:
        # Skip first line
        next(activity_data)
        reader = csv.DictReader(activity_data)
        activity_data = {}
        for row in reader:
            date = parse_day_time(row["day_time"])
            step_count = int(row["step_count"])
            # Samsung Health stores the distance in m, Garmin Connect expects it to be in km.
            distance = round(float(row["distance"]) / 1000, 2)
            calorie = float(row["calorie"])
            # Times are stored in milliseconds.
            run_time = int(row["run_time"]) / 60000
            walk_time = int(row["walk_time"]) / 60000
            activity_data[date] = {
                "Steps": step_count,
                "Distance": distance,
                "Minutes Sedentary": 0,  # We set this to zero, because Garmin won't show it anyway.
                "Minutes Lightly Active": int(walk_time),
                "Minutes Fairly Active": 0,
                "Minutes Very Active": int(run_time),
                "Activity Calories": int(calorie),
            }

        return activity_data


def merge_data(floors, calories, activities):
    merged_data = {}

    for date, cals in calories.items():
        merged_data[date] = {"Calories Burned": cals}

    for date, f in floors.items():
        if date not in merged_data:
            merged_data[date] = {"Calories Burned": 0}
        merged_data[date]["Floors"] = f

    for date, dic in activities.items():
        # If no steps have been recorded for a given date, we can drop that entry entirely,
        # because that means other data will not be useful anyway: no activity calories, no distance
        # no intensity minutes.
        dropkey = dic["Steps"] == 0
        if date in merged_data:
            if dropkey:
                merged_data.pop(date)
            else:
                merged_data[date].update(dic)
        else:
            merged_data[date] = dic

    # Ensure all required columns exist to avoid empty CSV fields.
    for date in merged_data:
        row = merged_data[date]
        merged_data[date] = {
            "Calories Burned": int(row.get("Calories Burned", 0) or 0),
            "Steps": int(row.get("Steps", 0) or 0),
            "Distance": round(float(row.get("Distance", 0) or 0), 2),
            "Floors": int(row.get("Floors", 0) or 0),
            "Minutes Sedentary": int(row.get("Minutes Sedentary", 0) or 0),
            "Minutes Lightly Active": int(row.get("Minutes Lightly Active", 0) or 0),
            "Minutes Fairly Active": int(row.get("Minutes Fairly Active", 0) or 0),
            "Minutes Very Active": int(row.get("Minutes Very Active", 0) or 0),
            "Activity Calories": int(row.get("Activity Calories", 0) or 0),
        }

    return dict(sorted(merged_data.items()))


def write_to_file(data):
    """
    Write the data to a series of CSV files. We can only store a certain number of lines per file,
    because if the files become too large, Garmin Connect will fail importing them.
    Note: Garmin Connect might still show an error message. This does not mean the import failed.
          Please check your data. The CSV files generated will be sorted by date, so when you go
          back in time, you can easily check if your data is there or not.
    """
    LINES_PER_FILE = 100
    export_dir = "exports"
    os.makedirs(export_dir, exist_ok=True)

    dest = None
    lines_written = 0
    columns = [
        "Date",
        "Calories Burned",
        "Steps",
        "Distance",
        "Floors",
        "Minutes Sedentary",
        "Minutes Lightly Active",
        "Minutes Fairly Active",
        "Minutes Very Active",
        "Activity Calories",
    ]
    for d in data:
        # Add the date key to the row.
        data[d]["Date"] = d
        if lines_written % LINES_PER_FILE == 0:
            filename = os.path.join(
                export_dir,
                f"activities-export-{lines_written // LINES_PER_FILE + 1}.csv",
            )
            if hasattr(dest, "close"):
                dest.close()

            dest = open(filename, "w", newline="")
            dest.write("Activities\n")
            writer = csv.DictWriter(
                dest,
                fieldnames=columns,
                lineterminator="\n",
                quoting=csv.QUOTE_MINIMAL,
            )
            writer.writeheader()

        writer.writerow(data[d])
        lines_written += 1

    try:
        dest.close()
    except:
        pass


data = merge_data(fetch_floor_data(), fetch_calorie_data(), fetch_activity_data())
write_to_file(data)
