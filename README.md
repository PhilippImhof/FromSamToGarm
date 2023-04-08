# FromSamToGarm - Migrate from Samsung Health to Garmin Connect


## What is this?

This is a collection of three scripts that allow you to move some of your data from Samsung Health to Garmin Connect.


## Preparation

First, you have to export your whole Samsung Health data via the app. Copy everything into a folder on your computer.

Next, you will need to have a recent version of Python installed on your computer. A recent version of the lxml package is also needed.

Finally, you download the three scripts and copy them into the folder where you have your Samsung Health data.

Please check your operating system's documentation to find out how to install Python and how to run scripts.


## Warning

You might want to open a clean test account on Garmin Connect and test the scripts first, because there is currently no way to efficiently delete multiple activities at once. If you mess up your pre-existing data, it will be a lot of work to clean things up...


## Importing weight data

You can import data on your weight, height and BMI from Samsung Health.

1. Run the `weight.py` script. It should automatically find the file containing the weight data from Samsung Health. It will convert the data and create one or more files in the same folder. Those files are called `weight-export-XX.csv` with XX being a number.
2. Go to the Garmin Connect web portal and click the "Upload or Import Activity" icon in the upper right corner. Choose "Import Data".
3. Find the `weight-export-XX.csv` files created by the script. Drag and drop them into the drop zone.
4. Click "Import Data". The script will prepare the data in metric units, so you will have to set "Length Units" and "Weight Units" accordingly, even if you normally use British or American units. Garmin Connect will convert the data for you.
5. Click "Continue" and wait for the magic to happen.


## Importing general activity data

You can import data on calories burned (resting and active), steps, distance, floors climbed and intensity minutes. Please note that the way Samsung Health records activity minutes differs from the way Garmin records and counts intensity minutes.

1. Run the `activity.py` script. It should automatically find the files containing the relevant data from Samsung Health. It will convert the data and create one or more files in the same folder. Those files are called `activities-export-XX.csv` with XX being a number.
2. Go to the Garmin Connect web portal and click the "Upload or Import Activity" icon in the upper right corner. Choose "Import Data".
3. Find the `activities-export-XX.csv` files created by the script. Drag and drop them into the drop zone.
4. Click "Import Data". The script will prepare the data in metric units, so you will have to set "Length Units" and "Weight Units" accordingly, even if you normally use British or American units. Garmin Connect will convert the data for you.
5. Click "Continue" and wait for the magic to happen.

Note: There might be some error messages, in extreme casese for the majority of files. Most of the time the import still works. Just check your statistics by clicking "Activities" and then "Steps" in the main navigation. In the "Steps" card, click the "Reports" icon and click on "1 Year". This should make it easy enough for you to check whether the data is plausible. Do this for the floors climbed and calories as well. If you do it for the intensity minutes, please remember what was said above: there will probably be a major difference between Samsung Health and Garmin Connect, because Garmin's intensity minutes are not counted in the same way as Samsung's active minutes.


## Importing activities and exercises

You can import recorded activities, e.g. runs or bike rides. Please note that the import is not perfect, but many things work fine, including duration of the activity and the calories burned.

Please note: While Garmin Connect offers a vide range of activity types, the TCX (Training Center Database File) standard only allows three types: Running, Biking and Other. This means that you will probably have to manually adjust the type of your activities once they are imported.

1. Run the `exercises.py` script. It should automatically find the files containing the relevant data from Samsung Health. It will convert the data and create a whole bunch of TCX files (one for every recorded activity) in a subfolder called `exports`. This subfolder will be created, if it does not exist.
2. Go to the Garmin Connect web portal and click the "Upload or Import Activity" icon in the upper right corner. Choose "Import Data".
3. Go to the `exports` folder created by the script. Drag and drop as many files as you wish into the drop zone. (You should probably not take more than one hundred at a time.)
4. Click "Import Data". The script will prepare the data in metric units, so you will have to set "Length Units" and "Weight Units" accordingly, even if you normally use British or American units. Garmin Connect will convert the data for you.
5. Click "Continue" and wait for the magic to happen.

It might be best to import the files by group, e.g. all files starting with `0`, all with `1` etc. This will make it easier for you to know what is done and what is not. In any case, Garmin Connect will check whether an activity has already been imported and will not import it a second time.


## Importing sleep data

Sorry, you cannot import sleep data.


## Bugs and improvements

Feel free to open an issue or create a pull request on GitHub.