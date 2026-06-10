# FromSamToGarm - Migrate from Samsung Health to Garmin Connect

## What is this?
This is a collection of three scripts that allow you to move some of your data from Samsung Health to Garmin Connect.

This fork updates the original scripts to be compatible with newer Samsung Health export formats (tested with exports from 2025–2026). See the [Compatibility Notes](#compatibility-notes) section for details on what changed.

---

## Preparation
First, you have to export your whole Samsung Health data via the app. Copy everything into a folder on your computer.

Next, you will need a recent version of **Python** installed on your computer, as well as the **lxml** package. You can install it with:

```bash
pip install lxml
```

Finally, download the three scripts and copy them into the folder where you have your Samsung Health data (the folder containing the `.csv` files).

Please check your operating system's documentation to find out how to install Python and how to run scripts.

---

## Warning
You might want to open a clean test account on Garmin Connect and test the scripts first, because there is currently no way to efficiently delete multiple activities at once. If you mess up your pre-existing data, it will be a lot of work to clean things up...

---

## Importing weight data
You can import data on your weight, height and BMI from Samsung Health.

1. Run the `weight.py` script. It should automatically find the file containing the weight data from Samsung Health. It will convert the data and create one or more files in the same folder. Those files are called `weight-export-XX.csv` with XX being a number.
2. Go to the Garmin Connect web portal and click the "Upload or Import Activity" icon in the upper right corner. Choose "Import Data".
3. Find the `weight-export-XX.csv` files created by the script. Drag and drop them into the drop zone.
4. Click "Import Data". Garmin may detect the file as "Fitbit® Data" — this is expected and will import correctly. The script prepares data in metric units, so set "Length Units" and "Weight Units" to metric accordingly, even if you normally use British or American units. Garmin Connect will convert the data for you.
5. Click "Continue" and wait for the magic to happen.

**Note:** You can import your data several times. In this case, existing values will be overwritten.

**Note:** Some weight entries may not have a height value recorded (common when weight was logged by a third-party app like MyFitnessPal). The script handles this by carrying forward the last known height value to calculate BMI.

---

## Importing general activity data
You can import data on calories burned (resting and active), steps, distance, floors climbed and intensity minutes. Please note that the way Samsung Health records activity minutes differs from the way Garmin records and counts intensity minutes.

1. Run the `activity.py` script. It should automatically find the files containing the relevant data from Samsung Health. It will convert the data and create one or more files in the same folder. Those files are called `activities-export-XX.csv` with XX being a number.
2. Go to the Garmin Connect web portal and click the "Upload or Import Activity" icon in the upper right corner. Choose "Import Data".
3. Find the `activities-export-XX.csv` files created by the script. Drag and drop them into the drop zone.
4. Click "Import Data". The script will prepare the data in metric units, so you will have to set "Length Units" and "Weight Units" accordingly, even if you normally use British or American units. Garmin Connect will convert the data for you.
5. Click "Continue" and wait for the magic to happen.

**Note:** There might be some error messages, in extreme cases for the majority of files. This is often a transient issue with Garmin's importer — retrying the failed files usually works. The import itself is generally successful even when errors are shown.

To verify your data imported correctly: click "Activities" → "Steps" in the main navigation, click the "Reports" icon in the Steps card, and select "1 Year". Do the same for floors climbed and calories. For intensity minutes, expect a significant difference between Samsung Health and Garmin Connect, as they count active minutes differently.

In case of problems, you can import your data several times. Steps, floors, calories and minutes will not be cumulated — the most recent import will overwrite existing data.

---

## Importing activities and exercises
You can import recorded activities, e.g. runs or bike rides. Please note that the import is not perfect, but many things work fine, including duration, GPS data, heart rate, and calories burned.

**Note:** While Garmin Connect offers a wide range of activity types, the TCX (Training Center Database File) standard only allows three types: Running, Biking and Other. You will probably have to manually adjust the activity type after importing. Samsung activity type codes are used in the filename (e.g. `1002` = running, `1001` = walking, `11007` = cycling, `13001` = hiking) to make bulk re-typing easier.

1. Run the `exercises.py` script. It should automatically find the files containing the relevant data from Samsung Health. It will convert the data and create a TCX file for every recorded activity in a subfolder called `exports`. This subfolder will be created if it does not exist.
2. Go to the Garmin Connect web portal and click the "Upload or Import Activity" icon in the upper right corner. Choose "Import Data".
3. Go to the `exports` folder. Drag and drop files into the drop zone. Aim for batches of around 100 at a time.
4. Click "Import Data". Set units to metric as described above.
5. Click "Continue" and wait for the magic to happen.

**Tip:** Import files grouped by activity type prefix (e.g. all `1002_*` runs together) — this makes it easier to bulk-update the activity type in Garmin Connect after importing.

**Tip:** Garmin Connect will detect and skip duplicate uploads, so it is safe to re-run batches that had errors.

---

## Importing sleep data
Sorry, you cannot import sleep data.

---

## Compatibility Notes

This fork was updated to handle Samsung Health export schema changes introduced in newer app versions. If you are using a **2024 or later Samsung Health export**, you may encounter issues with the original scripts. The following changes were made:

### `exercises.py`
- The glob pattern was updated from `com.samsung.shealth.exercise.*.csv` to `com.samsung.shealth.exercise.20*.csv` to avoid accidentally matching sub-files such as `hr_zone`, `extension`, `weather`, and `periodization_training_schedule`, which share the same prefix.
- In newer exports, `datauuid` and `start_time` in the exercise file use the full `com.samsung.health.exercise.` column prefix. The field mapping was updated accordingly.
- `total_calorie` and `heart_rate_sample_count` remain unprefixed bare column names.
- The exercise CSV is encoded with a UTF-8 BOM; the file is now opened with `utf-8-sig` encoding to handle this correctly.
- The `live_data` and `location_data` fields now contain JSON filenames rather than `0`/`1` flags. The script was updated to detect presence by checking for a non-empty, non-`"0"` value.

### `activity.py`
- In newer exports, the `day_time` field in `com.samsung.shealth.activity.day_summary` is a human-readable datetime string (e.g. `2026-01-30 00:00:00.000`) rather than a Unix millisecond timestamp. The script now handles both formats.
- A bug in `merge_data` where dates present in the floors data but not the calories data would cause a `KeyError` has been fixed.
- Missing `Floors` values (empty strings) are now defaulted to `0` before writing, preventing import failures in Garmin Connect.

### `weight.py`
- Some weight entries have an empty `height` field (common for entries logged by third-party apps). The script now carries forward the last known height value and skips rows with no weight recorded, rather than crashing.

---

## Bugs and improvements
Feel free to open an issue or create a pull request on GitHub.

---

## Known Problems

- **Negative calories:** Sometimes Garmin Connect will show negative calories for certain days, especially days where no exercise is recorded. A simple fix is to create a manual activity with 0 calories for the affected day — this triggers a recalculation. Once done, you can delete or repurpose the activity for the next affected day.

- **Transient upload errors:** Garmin Connect's importer occasionally returns errors on individual files even when the data is valid. Simply retry the failed files — they usually succeed on the second or third attempt.

- **Activity type labels:** All imported exercises default to "Running", "Biking", or "Other" due to TCX format limitations. Use the Samsung activity type code in the filename to identify and bulk-update activity types in Garmin Connect after importing.
