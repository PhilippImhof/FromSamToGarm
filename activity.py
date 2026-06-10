#!/usr/bin/env python3


import csv
import datetime
import glob


def fetch_floor_data():
    """
    Fetch and consolidate the floors climbed data. There are normally multiple entries per day,
    because floors climbed seem to be stored whenever they are registered. So we have to group
    them all and add them up.
    """
    floor_files = glob.glob("com.samsung.health.floors_climbed.*.csv")
    if len(floor_files) == 0:
        raise Exception("No floors data found.")
    filename = floor_files[0]

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

    calorie_files = glob.glob("com.samsung.shealth.calories_burned.details.*.csv")
    if len(calorie_files) == 0:
        raise Exception("No calorie data found.")
    filename = calorie_files[0]

    with open(filename, newline="") as calories_data:
        # Skip first line
        next(calories_data)
        reader = csv.DictReader(calories_data)
        calorie_data = {}
        prefix = "com.samsung.shealth.calories_burned."
        for row in reader:
            date = datetime.datetime.fromtimestamp(
                int(row[prefix + "day_time"]) / 1000
            ).strftime("%Y-%m-%d")
            rest_calorie = float(row[prefix + "rest_calorie"])
            active_calorie = float(row[prefix + "active_calorie"])
            calorie_data[date] = int(round(rest_calorie + active_calorie, 0))

        return calorie_data


def fetch_activity_data():
    activity_files = glob.glob("com.samsung.shealth.activity.day_summary.*.csv")
    if len(activity_files) == 0:
        raise Exception("No activity data found.")
    filename = activity_files[0]

    with open(filename, newline="") as activity_data:
        next(activity_data)
        reader = csv.DictReader(activity_data)
        activity_data = {}
        for row in reader:
            # Handle both Unix ms timestamps and human-readable datetime strings
            raw = row["day_time"].strip()
            try:
                date = datetime.datetime.fromtimestamp(int(raw) / 1000).strftime("%Y-%m-%d")
            except ValueError:
                date = raw[0:10]

            step_count = int(row["step_count"])
            distance = round(float(row["distance"]) / 1000, 2)
            calorie = float(row["calorie"])
            run_time = int(row["run_time"]) / 60000
            walk_time = int(row["walk_time"]) / 60000
            activity_data[date] = {
                "Steps": step_count,
                "Distance": distance,
                "Minutes Sedentary": 0,
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
            merged_data[date] = {"Calories Burned": 0}  # was missing, create entry first
        merged_data[date]["Floors"] = f

    for date, dic in activities.items():
        dropkey = dic["Steps"] == 0
        if date in merged_data:
            if dropkey:
                merged_data.pop(date)
            else:
                merged_data[date].update(dic)
        else:
            if not dropkey:
                merged_data[date] = dic

    return dict(sorted(merged_data.items()))


def write_to_file(data):
    LINES_PER_FILE = 100

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
        data[d]["Date"] = d
        # Default any missing fields to 0 to avoid empty cells
        for col in columns:
            if col not in data[d] or data[d][col] == "" or data[d][col] is None:
                data[d][col] = 0

        if lines_written % LINES_PER_FILE == 0:
            filename = f"activities-export-{lines_written // LINES_PER_FILE + 1}.csv"
            if hasattr(dest, "close"):
                dest.close()

            dest = open(filename, "w", newline="")
            dest.write("Activities\n")
            writer = csv.DictWriter(
                dest, fieldnames=columns, lineterminator="\n", quoting=csv.QUOTE_ALL
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
