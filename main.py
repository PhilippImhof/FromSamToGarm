#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import importlib
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from getpass import getpass
from pathlib import Path
from typing import Any


EXPORT_DIR = Path("exports")
RUNNING_TYPES = {"1001", "1002", "13001", "13003", "15005"}
BIKING_TYPES = {"11007", "13004", "15003"}
STRENGTH_ACTIVITY_TYPE_KEY = "strength_training"
WALKING_ACTIVITY_TYPE_KEY = "walking"
WALKING_PACE_THRESHOLD_MIN_PER_KM = 10.0
TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"


@dataclass
class WeightEntry:
    date: str
    timestamp: str
    weight: float
    bmi: float | None
    body_fat_percent: float | None


def import_garmin() -> Any:
    try:
        module = importlib.import_module("garminconnect")
        return module.Garmin
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: garminconnect. Install with: pip install garminconnect"
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run Samsung-to-Garmin exporters and upload data to Garmin Connect. "
            "TCX and weight/body composition are uploaded via API."
        )
    )
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Skip running weight.py, activity.py and exercises.py.",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Only generate files, do not upload anything.",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("GARMIN_EMAIL", ""),
        help="Garmin email. Defaults to GARMIN_EMAIL env var.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("GARMIN_PASSWORD", ""),
        help="Garmin password. Defaults to GARMIN_PASSWORD env var.",
    )
    parser.add_argument(
        "--mfa-code",
        default=os.getenv("GARMIN_MFA_CODE", ""),
        help=(
            "Optional one-time Garmin MFA code. "
            "Defaults to GARMIN_MFA_CODE env var."
        ),
    )
    parser.add_argument(
        "--tokenstore",
        default=os.getenv("GARMINTOKENS", ".garmin_tokens"),
        help="Token file path for Garmin session reuse.",
    )
    parser.add_argument(
        "--max-tcx",
        type=int,
        default=0,
        help="Upload at most N TCX files (0 means all).",
    )
    parser.add_argument(
        "--allow-duplicate-weigh-ins",
        action="store_true",
        help="Upload weight rows even if Garmin already has weigh-ins for the same date.",
    )
    parser.add_argument(
        "--set-other-to-strength",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "After TCX upload, reclassify Samsung non-running/non-biking workouts "
            "to Garmin Strength Training. Enabled by default."
        ),
    )
    return parser.parse_args()


def run_exporters() -> None:
    scripts = ["weight.py", "activity.py", "exercises.py"]
    for script in scripts:
        print(f"Running {script}...")
        subprocess.run([sys.executable, script], check=True)


def list_export_files() -> tuple[list[Path], list[Path], list[Path]]:
    tcx_files = sorted(EXPORT_DIR.glob("*.tcx"))
    weight_csv_files = sorted(EXPORT_DIR.glob("weight-export-*.csv"))
    activities_csv_files = sorted(EXPORT_DIR.glob("activities-export-*.csv"))
    return tcx_files, weight_csv_files, activities_csv_files


def parse_weight_files(weight_csv_files: list[Path]) -> list[WeightEntry]:
    entries: list[WeightEntry] = []

    for csv_file in weight_csv_files:
        with csv_file.open(newline="", encoding="utf-8") as handle:
            # Fitbit-style Garmin import files include a first header line, e.g. "Body".
            first_line = handle.readline().strip()
            if first_line != "Body":
                # If first row is already the CSV header, rewind to parse from start.
                handle.seek(0)

            reader = csv.DictReader(handle)
            for row in reader:
                date = (row.get("Date") or "").strip()
                if not date:
                    continue

                try:
                    weight = float((row.get("Weight") or "").strip())
                except ValueError:
                    continue

                bmi = _optional_float(row.get("BMI"))
                fat = _optional_float(row.get("Fat"))
                timestamp = f"{date}T12:00:00"

                entries.append(
                    WeightEntry(
                        date=date,
                        timestamp=timestamp,
                        weight=weight,
                        bmi=bmi,
                        body_fat_percent=fat,
                    )
                )

    return entries


def _optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed


def login_garmin(
    email: str,
    password: str,
    tokenstore: str,
    mfa_code: str = "",
) -> Any:
    if not email and not password and not tokenstore:
        raise RuntimeError(
            "Provide Garmin credentials or a tokenstore path via --tokenstore/GARMINTOKENS."
        )

    if email and not password:
        password = getpass("Garmin password: ")

    initial_mfa_code = (mfa_code or "").strip()

    def prompt_mfa() -> str:
        if initial_mfa_code:
            return initial_mfa_code
        return input("Garmin MFA code: ").strip()

    Garmin = import_garmin()
    api = Garmin(
        email=email or None,
        password=password or None,
        prompt_mfa=prompt_mfa,
    )
    api.login(tokenstore=tokenstore)
    return api


def _extract_activity_ids_from_import_result(result: Any) -> list[str]:
    """Best-effort extraction of activity IDs from Garmin import response payloads."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_l = str(key).lower()
                if "activityid" in key_l and isinstance(value, (int, str)):
                    value_s = str(value)
                    if value_s.isdigit():
                        found.add(value_s)
                walk(value)
            return

        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(result)
    return sorted(found)


def _is_eu_upload_consent_error(exc: Exception) -> bool:
    """Detect Garmin API 412 EU upload consent errors."""
    msg = str(exc).lower()
    return (
        "user is from eu location" in msg
        or (
            "412" in msg
            and "upload consent" in msg
            and ("eu" in msg or "location" in msg)
        )
    )


def _resolve_activity_type(api: Any, type_key: str) -> tuple[int, str, int] | None:
    """Fetch Garmin type metadata (typeId, typeKey, parentTypeId) for type_key."""
    try:
        activity_types = api.get_activity_types()
    except Exception:
        return None

    if not isinstance(activity_types, list):
        return None

    for item in activity_types:
        if not isinstance(item, dict):
            continue
        if str(item.get("typeKey", "")).lower() != type_key.lower():
            continue

        type_id = item.get("typeId")
        parent_type_id = item.get("parentTypeId")
        if isinstance(type_id, int) and isinstance(parent_type_id, int):
            return (type_id, str(item["typeKey"]), parent_type_id)

    return None


def _extract_samsung_type_code(file_path: Path) -> str | None:
    """Return Samsung exercise type code from generated file name: <type>_<date>_<uuid>.tcx."""
    prefix = file_path.stem.split("_", 1)[0]
    return prefix if prefix.isdigit() else None


def _safe_float(text: str | None) -> float | None:
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _average_pace_min_per_km_from_tcx(file_path: Path) -> float | None:
    """Read average pace from TCX lap summary values when available."""
    try:
        root = ET.parse(file_path).getroot()
    except Exception:
        return None

    lap = root.find(f".//{{{TCX_NS}}}Lap")
    if lap is None:
        return None

    duration = _safe_float(lap.findtext(f"{{{TCX_NS}}}TotalTimeSeconds"))
    distance = _safe_float(lap.findtext(f"{{{TCX_NS}}}DistanceMeters"))

    if duration is None or distance is None or duration <= 0 or distance <= 0:
        return None

    # pace (min/km) = duration_seconds / 60 / (distance_m / 1000)
    return duration * 1000.0 / (60.0 * distance)


def _classify_target_activity_type(file_path: Path) -> str | None:
    """Determine post-upload Garmin activity type based on pace and Samsung type code."""
    pace_min_per_km = _average_pace_min_per_km_from_tcx(file_path)
    if (
        pace_min_per_km is not None
        and pace_min_per_km > WALKING_PACE_THRESHOLD_MIN_PER_KM
    ):
        return WALKING_ACTIVITY_TYPE_KEY

    stype = _extract_samsung_type_code(file_path)
    if stype is None:
        return None
    if stype in RUNNING_TYPES or stype in BIKING_TYPES:
        return None
    return STRENGTH_ACTIVITY_TYPE_KEY


def upload_tcx_files(
    api: Any,
    tcx_files: list[Path],
    max_tcx: int = 0,
    set_other_to_strength: bool = True,
) -> tuple[int, int, int, int, int, int]:
    uploaded = 0
    duplicates = 0
    failed = 0
    consent_blocked = 0
    retyped = 0
    retype_failed = 0

    type_meta_by_key: dict[str, tuple[int, str, int]] = {}
    if set_other_to_strength:
        for key in (STRENGTH_ACTIVITY_TYPE_KEY, WALKING_ACTIVITY_TYPE_KEY):
            resolved = _resolve_activity_type(api, key)
            if resolved is not None:
                type_meta_by_key[key] = resolved
            else:
                print(f"[TCX] warning: could not resolve Garmin activity type '{key}'.")

    selected_files = tcx_files if max_tcx <= 0 else tcx_files[:max_tcx]

    for file_path in selected_files:
        try:
            import_result = api.import_activity(str(file_path))
            uploaded += 1
            print(f"[TCX] uploaded: {file_path.name}")

            target_type_key = (
                _classify_target_activity_type(file_path)
                if set_other_to_strength
                else None
            )
            target_type = (
                type_meta_by_key.get(target_type_key)
                if target_type_key is not None
                else None
            )

            if set_other_to_strength and target_type is not None:
                activity_ids = _extract_activity_ids_from_import_result(import_result)
                if not activity_ids:
                    print(
                        f"[TCX] uploaded but type unchanged (no activity id in response): {file_path.name}"
                    )
                else:
                    type_id, type_key, parent_type_id = target_type
                    for activity_id in activity_ids:
                        try:
                            api.set_activity_type(
                                activity_id=activity_id,
                                type_id=type_id,
                                type_key=type_key,
                                parent_type_id=parent_type_id,
                            )
                            retyped += 1
                            print(
                                f"[TCX] retyped as {type_key}: {file_path.name} (activity {activity_id})"
                            )
                        except Exception as exc:
                            retype_failed += 1
                            print(
                                f"[TCX] retype failed: {file_path.name} (activity {activity_id}) ({exc})"
                            )
        except Exception as exc:  # API wrapper raises custom exceptions with status text.
            msg = str(exc).lower()
            if _is_eu_upload_consent_error(exc):
                consent_blocked += 1
                print(f"[TCX] blocked: {file_path.name} ({exc})")
                print(
                    "[TCX] action required: Garmin EU upload consent is not granted. "
                    "Open Garmin Connect in a browser, complete the upload consent prompt, "
                    "then re-run with --skip-generate."
                )
                break
            if "duplicate" in msg or "409" in msg:
                duplicates += 1
                print(f"[TCX] duplicate: {file_path.name}")
            else:
                failed += 1
                print(f"[TCX] failed: {file_path.name} ({exc})")

    return uploaded, duplicates, failed, consent_blocked, retyped, retype_failed


def _has_existing_weigh_in(api: Any, date: str) -> bool:
    try:
        data = api.get_daily_weigh_ins(date)
    except Exception:
        return False

    values = data.get("dateWeightList", []) if isinstance(data, dict) else []
    return bool(values)


def upload_weight_entries(
    api: Any,
    entries: list[WeightEntry],
    allow_duplicates: bool,
) -> tuple[int, int, int]:
    uploaded = 0
    skipped_existing = 0
    failed = 0

    # Keep one reading per date to avoid redundant uploads when files are split.
    by_date: dict[str, WeightEntry] = {}
    for entry in entries:
        by_date[entry.date] = entry

    for date in sorted(by_date.keys()):
        entry = by_date[date]

        if not allow_duplicates and _has_existing_weigh_in(api, entry.date):
            skipped_existing += 1
            print(f"[WEIGHT] skipped existing date: {entry.date}")
            continue

        try:
            api.add_body_composition(
                timestamp=entry.timestamp,
                weight=entry.weight,
                percent_fat=entry.body_fat_percent,
                bmi=entry.bmi,
            )
            uploaded += 1
            print(f"[WEIGHT] uploaded: {entry.date}")
        except Exception as exc:
            failed += 1
            print(f"[WEIGHT] failed: {entry.date} ({exc})")

    return uploaded, skipped_existing, failed


def main() -> int:
    args = parse_args()

    if not args.skip_generate:
        run_exporters()

    tcx_files, weight_csv_files, activities_csv_files = list_export_files()

    print("\nExport summary:")
    print(f"  TCX files: {len(tcx_files)}")
    print(f"  Weight CSV files: {len(weight_csv_files)}")
    print(f"  Activities CSV files: {len(activities_csv_files)}")

    if args.skip_upload:
        print("Upload skipped (--skip-upload).")
        return 0

    api = login_garmin(
        args.email,
        args.password,
        args.tokenstore,
        mfa_code=args.mfa_code,
    )

    print("\nUploading TCX activities...")
    (
        tcx_uploaded,
        tcx_duplicates,
        tcx_failed,
        tcx_consent_blocked,
        tcx_retyped,
        tcx_retype_failed,
    ) = upload_tcx_files(
        api,
        tcx_files,
        max_tcx=args.max_tcx,
        set_other_to_strength=args.set_other_to_strength,
    )

    print("\nUploading weight/body composition...")
    weight_entries = parse_weight_files(weight_csv_files)
    weight_uploaded, weight_skipped, weight_failed = upload_weight_entries(
        api,
        weight_entries,
        allow_duplicates=args.allow_duplicate_weigh_ins,
    )

    print("\nActivities CSV upload note:")
    print(
        "  Garmin's activity file upload API supports FIT/GPX/TCX only. "
        "Daily Activities CSV import is a different Garmin web import flow and is not "
        "available through this API client."
    )

    print("\nUpload summary:")
    print(
        "  "
        f"TCX uploaded={tcx_uploaded}, duplicates={tcx_duplicates}, failed={tcx_failed}, "
        f"consent_blocked={tcx_consent_blocked}, "
        f"retyped_to_strength={tcx_retyped}, retype_failed={tcx_retype_failed}"
    )
    print(
        f"  Weight uploaded={weight_uploaded}, skipped_existing={weight_skipped}, failed={weight_failed}"
    )

    return 0 if (tcx_failed == 0 and tcx_consent_blocked == 0 and weight_failed == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
