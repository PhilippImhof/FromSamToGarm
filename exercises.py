#!/usr/bin/env python3

import csv
import datetime
import glob
import json
import os
from lxml import etree as XML


# Define the various namespaces
nsmap = {
    None: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns2": "http://www.garmin.com/xmlschemas/UserProfile/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
    "ns4": "http://www.garmin.com/xmlschemas/ProfileExtension/v1",
    "ns5": "http://www.garmin.com/xmlschemas/ActivityGoals/v1",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Return the right qualified name for a given name space.
def ns3_tag(name):
    return XML.QName(nsmap["ns3"], name)


def fetch_exercise_list():
    """
    Fetch the list of exercises from Samsung's CSV file. The file contains general
    data about each exercise, like the date and time, the calories burned or the duration.
    The list also tells us, whether there is live data (e.g. heart rate) and/or location data
    available.
    """
    exercise_files = glob.glob("com.samsung.shealth.exercise.*.csv")
    if len(exercise_files) == 0:
        raise Exception("No exercise data found.")
    filename = exercise_files[0]

    prefix = "com.samsung.health.exercise."
    fields = [
        prefix + "datauuid",
        prefix + "start_time",
        "total_calorie",
        prefix + "duration",
        prefix + "exercise_type",
        "heart_rate_sample_count",
        prefix + "mean_heart_rate",
        prefix + "max_heart_rate",
        prefix + "min_heart_rate",
        prefix + "mean_speed",
        prefix + "max_speed",
        prefix + "mean_cadence",
        prefix + "max_cadence",
        prefix + "distance",
        prefix + "location_data",
        prefix + "live_data",
    ]
    with open(filename, newline="") as exercise_list:
        # Skip first line
        next(exercise_list)
        reader = csv.DictReader(exercise_list)
        data = []
        for row in reader:
            dataset = {}
            for f in fields:
                dataset[f.replace(prefix, "")] = row[f]
            data.append(dataset)

        return data


def fetch_live_data(uuid):
    """
    Fetch the live data (e.g. heart rate) from the file mentioned in the exercise list.
    The data is stored in JSON format.
    """
    subdir = uuid[0]
    filename = f"jsons/com.samsung.shealth.exercise/{subdir}/{uuid}.com.samsung.health.exercise.live_data.json"
    with open(filename) as f:
        live_data = json.load(f)

    return live_data


def fetch_location_data(uuid):
    """
    Fetch the location data (GPS coordinates) from the file mentioned in the exercise list.
    The data is stored in JSON format.
    """
    subdir = uuid[0]
    filename = f"jsons/com.samsung.shealth.exercise/{subdir}/{uuid}.com.samsung.health.exercise.location_data.json"
    with open(filename) as f:
        location_data = json.load(f)

    return location_data


def create_lap(
    start_time,
    duration,
    distance,
    calories,
    avg_hr="",
    max_hr="",
    avg_speed="",
    max_speed="",
    avg_cadence="",
    max_cadence="",
):
    """
    Take the retrieved and calculated data to create a <Lap> tag.
    The StartTime attribute is required. Every <Lap> must have
    a <TotalTimeSeconds>, a <DistanceMeters>, a <Calories>, an <Intensity>
    and a <TriggerMethod> tag. The following tags are optional:
     * <MaximumSpeed>
     * <AverageHeartRateBpm>
     * <Cadence>
     * <Track>
     * <Notes>, note that these will not be shown in Garmin Connect
     * <Extensions>, which can contain AvgSpeed, AvgRunCadence and MaxRunCadence
    The order and requirements are described in the schemas:
    https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd
    https://www8.garmin.com/xmlschemas/ActivityExtensionv2.xsd
    """
    lap = XML.Element("Lap", {"StartTime": start_time})
    if duration:
        duration = int(duration) / 1000
        XML.SubElement(lap, "TotalTimeSeconds").text = str(duration)
    if distance:
        XML.SubElement(lap, "DistanceMeters").text = distance
    if max_speed:
        XML.SubElement(lap, "MaximumSpeed").text = max_speed
    if calories:
        XML.SubElement(lap, "Calories").text = str(int(round(float(calories), 0)))
    if avg_hr and avg_hr != "0.0":
        ahr = XML.SubElement(lap, "AverageHeartRateBpm")
        XML.SubElement(ahr, "Value").text = str(int(float(avg_hr)))
    if max_hr and avg_hr != "0.0":
        mhr = XML.SubElement(lap, "MaximumHeartRateBpm")
        XML.SubElement(mhr, "Value").text = str(int(float(max_hr)))
    XML.SubElement(lap, "Intensity").text = "Active"
    XML.SubElement(lap, "TriggerMethod").text = "Manual"
    if avg_speed or avg_cadence or max_cadence:
        ext = XML.SubElement(lap, "Extensions")
        lx = XML.SubElement(ext, ns3_tag("LX"))
        if avg_speed and avg_speed != "0.0":
            XML.SubElement(lx, ns3_tag("AvgSpeed")).text = avg_speed
        if avg_cadence and avg_cadence != "0.0":
            XML.SubElement(lx, ns3_tag("AvgRunCadence")).text = avg_cadence
        if max_cadence and max_cadence != "0.0":
            XML.SubElement(lx, ns3_tag("MaxRunCadence")).text = max_cadence

    return lap


def create_trackpoint(data):
    """
    Take the retrieved and calculated data to create a <Trackpoint> tag.
    Every <Trackpoint> must have a <Time> tag. The following tags are optional:
     * <Position>, containing latitude and longitude in degrees
     * <AltitudeMeters>
     * <DistanceMeters>
     * <HeartRateBpm>, note: this must be an integer
     * <Cadence>
     * <SensorState>
     * <Extensions>, which can contain Speed or RunCadence
    The order and requirements are described in the schemas:
    https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd
    https://www8.garmin.com/xmlschemas/ActivityExtensionv2.xsd

    Note: We will not use AltitudeMeters and DistanceMeters, because they will interfere
    with the values that Garmin Connect calculates based on the GPS coordinates. This
    can lead to strange effects when viewing the activity details. The same is valid for the
    trackpoint extension Speed.
    """
    trackpoint = XML.Element("Trackpoint")
    XML.SubElement(trackpoint, "Time").text = data["time"]
    if data.get("altitude") and data.get("longitude"):
        position = XML.SubElement(trackpoint, "Position")
        XML.SubElement(position, "LatitudeDegrees").text = str(data["latitude"])
        XML.SubElement(position, "LongitudeDegrees").text = str(data["longitude"])
    # Not used, see above.
    # if data.get("altitude"):
    #    XML.SubElement(trackpoint, "AltitudeMeters").text = str(data["altitude"])
    # Not used, see above.
    # if data.get("distance"):
    #    XML.SubElement(trackpoint, "DistanceMeters").text = str(data["distance"])
    if data.get("heart_rate"):
        hr = XML.SubElement(trackpoint, "HeartRateBpm")
        XML.SubElement(hr, "Value").text = str(data["heart_rate"])
    if data.get("cadence"):
        XML.SubElement(trackpoint, "Cadence").text = str(data["cadence"])
    # Not used, see above.
    # if data.get("speed"):
    #    tpx = XML.SubElement(trackpoint, ns3_tag("TPX"))
    #    XML.SubElement(tpx, ns3_tag("Speed")).text = str(data["speed"])

    # If the trackpoint only contains one tag, it is the <Time> information, so the trackpoint
    # is basically empty. It should not be added to the file.
    if len(trackpoint) == 1:
        return None
    return trackpoint


def create_activity(id, sport="Other"):
    """
    Take the retrieved and calculated data to create an <Activity> tag.
    Every <Activity> must have an <Id> tag. The following tags are optional:
     * <Position>, containing latitude and longitude in degrees
     * <Lap>
     * <Notes>, note: they will not be shown in Garmin Connect
     * <Training>
     * <Creator>
     * <Extensions>
    The <Activity> must have the "Sport" attibute which must be set to "Running"
    or "Biking" or "Other". Although there are many very specific activity types
    in Garmin Connect, those cannot be used in a TCX file.
    """
    act = XML.Element("Activity", {"Sport": sport})
    XML.SubElement(act, "Id").text = id

    return act


def create_root():
    """
    This prepares the XML file's root tag.
    """
    attr_qname = XML.QName(nsmap["xsi"], "schemaLocation")
    root = XML.Element(
        "TrainingCenterDatabase",
        {
            attr_qname: "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"
        },
        version="1.1",
        nsmap=nsmap,
    )
    XML.SubElement(root, "Activities")
    return root


def build_xml(a_id, ex_type, lap, trackpoints=[]):
    """
    Build a valid TCX file with all the data we have prepared.
    """
    root = create_root()
    activity = create_activity(a_id, ex_type)
    track = XML.Element("Track")
    root.find("*").append(activity)
    activity.append(lap)
    for tp in trackpoints:
        # Empty trackpoints should not be added.
        if tp is not None:
            track.append(tp)

    # We only add the track, if it contains at least one trackpoint.
    if len(track) > 0:
        lap.append(track)

    return XML.tostring(root, pretty_print=True, encoding="utf-8", xml_declaration=True)


def convert_activity_type(stype):
    """
    This converts Samsung Health's exercise type to a valid sport type for the <Activity>.
    Although Garmin Connect has a wide range of very specific activity types, we can only use
    "Running", "Biking" or "Other" in a TCX file.

    The corresponding types used in Samsung Health are 1002 (running) and 11007 (cycling). For
    a complete list of all exercise types, see:
    https://developer.samsung.com/health/android/data/api-reference/EXERCISE_TYPE.html
    """
    if stype == "1002":
        return "Running"
    if stype == "11007":
        return "Biking"
    return "Other"


def find_nearest_time(ts, data):
    """
    This function searches data and finds the timestamp that is closes to ts.
    We need this to avoid having e.g. trackpoints with a heart rate, but no
    GPS information. Garmin Connect will not properly handle that and we get strange
    results. So it is better to lose some accuracy by shifting the live data a bit.
    """
    timestamps = list(sorted(map(lambda d: d["start_time"], data)))

    closest_match = 0
    for t in timestamps:
        if abs(t - ts) < abs(closest_match - ts):
            closest_match = t

    return closest_match


def merge_location_and_live_data(locationdata, livedata):
    """
    Merge location data and live data. This includes shifting live data a bit, so it is
    linked to a position. Also, we will duplicate heart rate data to all following trackpoints,
    until we get a new heart rate. Without this, the heart rate will not be shown correctly in
    Garmin Connect. Instead of having a nice diagram, the user will just see a few spikes and
    heart rate will be counted as zero for the trackpoints where HR data is missing.
    """
    merged_data = {}

    for entry in locationdata:
        # Convert the timestamp (milliseconds from Unix epoch) to the proper format.
        time = datetime.datetime.fromtimestamp(
            entry["start_time"] / 1000, datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # First, we copy the location data.
        if entry["start_time"] not in merged_data:
            merged_data[entry["start_time"]] = {
                "time": time,
                "latitude": entry["latitude"],
                "longitude": entry["longitude"],
            }
            if "altitude" in entry:
                merged_data[entry["start_time"]]["altitude"] = entry["altitude"]

    # Now for the live data...
    for entry in livedata:
        ts = entry["start_time"]
        # If necessary, shift the timestamp a bit, in order to have the live data included
        # in an existing trackpoint that has position data in it.
        if ts not in merged_data and locationdata:
            ts = find_nearest_time(ts, locationdata)
            entry["start_time"] = ts

        # Convert the (maybe updated) timestamp to the proper format.
        time = datetime.datetime.fromtimestamp(
            ts / 1000, datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # If there is heart rate data, it must be an integer.
        if "heart_rate" in entry:
            entry["heart_rate"] = int(entry["heart_rate"])

        # Live data entries can contain various types of data, we do not know
        # beforehand what we can expect, so we try them all.
        for key in ["distance", "cadence", "heart_rate", "speed"]:
            if entry.get(key):
                # If the timestamp is not yet in the merged_data, we create a new entry.
                # This can happen, if there was no location data, because in that case
                # we kept the original timestamp and did not try to shift it.
                if ts not in merged_data:
                    merged_data[ts] = {"time": time, key: entry[key]}

                # If the key is not already there, add it to the merged data. But do not
                # overwrite existing stuff.
                if key not in merged_data[ts]:
                    merged_data[ts][key] = entry[key]

    # Last step: copy heart rate into upcoming trackpoints, if they don't have one.
    # Otherwise, Garmin Connect will assume the heart rate was zero at those positions.
    merged_data = dict(sorted(merged_data.items()))
    hr = 0
    for d in merged_data:
        if merged_data[d].get("heart_rate"):
            hr = merged_data[d].get("heart_rate")
        else:
            merged_data[d]["heart_rate"] = hr

    return merged_data


def prepare_exercise_data(exercise):
    """
    Fetch and merge the data for the given exercise and create proper XML.
    """

    # The time code is used as the Id and StartTime for the lap. It is almost in the right format,
    # we just need to add the T separator between the date and the time and append a Z for the UTC
    # time zone.
    time = exercise["start_time"].replace(" ", "T") + "Z"
    ex_type = convert_activity_type(exercise["exercise_type"])

    lap = create_lap(
        time,
        exercise["duration"],
        exercise["distance"],
        exercise["total_calorie"],
        exercise["mean_heart_rate"],
        exercise["max_heart_rate"],
        exercise["mean_speed"],
        exercise["max_speed"],
        exercise["mean_cadence"],
        exercise["max_cadence"],
    )

    live_data = []
    if ex["live_data"]:
        live_data = fetch_live_data(ex["datauuid"])

    location_data = []
    if ex["location_data"]:
        location_data = fetch_location_data(ex["datauuid"])

    data = merge_location_and_live_data(location_data, live_data)
    trackpoints = []
    for d in data:
        trackpoints.append(create_trackpoint(data[d]))

    return build_xml(time, ex_type, lap, trackpoints)


def write_to_file(filename, xml):
    """
    Simply write the XML code into a file.
    """
    with open(filename, "w", newline="") as f:
        f.write(xml.decode())


# We will generate quite a bunch of files, so it is better to have them all in one
# subdir.
if not os.path.isdir("exports"):
    os.makedirs("exports")

print("Fetching exercises...", end="")
exercises = fetch_exercise_list()
print(f"done. Found {len(exercises)} exercises.")
print("Preparing individual TCX files", end="")
for ex in exercises:
    print(".", end="", flush=True)
    xml = prepare_exercise_data(ex)
    date_code = ex["start_time"][0:10]
    write_to_file(f"exports/{ex['exercise_type']}_{date_code}_{ex['datauuid']}.tcx", xml)

print("done")
