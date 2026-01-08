import os, time, request
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from garminconnect import Garmin

app = Flask(__name__)

# Env
GARMIN_USER = os.getenv("GARMIN_USER")
GARMIN_PASS = os.getenv("GARMIN_PASS")
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.getenv("STRAVA_REFRESH_TOKEN")

STRAVA_TOKEN_URL = ""
STRAVA_ACTIVITIES_URL = ""

def parse_iso(dt_str):
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

def refresh_strava_token():
    resp = requests.post(STRAVA_TOKEN_URL, data = {
        "client_id": STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": STRAVA_REFRESH_TOKEN
    })
    resp.raise_for_status()
    return resp.json()["access_token"]

def fetch_training_load(start_dt_local, sport_type):
    gc = Garmin(GARMIN_USER, GARMIN_PASS)
    gc.login()
    recent = gc.activites(0, 20)

    sport_type = sport_type.lower()
    for act in recent:
        st = act.get("startTimeLocal")
        if not st:
            continue
        dt = datetime.strptime(st, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if abs((dt - start_dt_local).total_seconds()) <= 600:
            details = gc.get_activity_details(act.get("activityId"))
            for key in ["trainingLoad", "epoc", "epocValue"]:
                if key in details:
                    return int(details[key])
            if "summaryDTO" in details:
                for key in ["trainingLoad", "epoc", "epocValue"]:
                    if key in details["summaryDTO"]:
                        return int(details["summaryDTO"][key])
    return None

def update_strava_description(activity_id, prepend_text, bearer):
    get = requests.get(f"{STRAVA_ACTIVITIES_URL}/{activity_id}", headers={"Authorization": f"Bearer {bearer}"})
    current = (get.json().get("description") or "").strip()
    new_desc = f"{prepend_text}\n{current}".strip()
    put = requests.put(f"{STRAVA_ACTIVITIES_URL}/{activity_id}", headers={"Authorization": f"Bearer {bearer}"}, data={"description": new_desc})
    put.raise_for_status()
    return put.json

@app.post("/zap")
def zap_handler():
    payload = requests.get_json(force=True)
    activity_id = payload.get("activity_id")
    start_local = payload.get("start_date_local")
    sport_type = payload.get("type")
    if not activity_id or not start_local:
        return jsonify({"error": "Missing fields"}), 400

    time.sleep(10)
    tl = fetch_training_load(parse_iso(start_local), sport_type)
    prefix = f"Garmin Load - {tl if tl else "N/A"}"
    token = refresh_strava_token()
    upd = update_strava_description(int(activity_id), prefix, token)
    return jsonify({"ok": True, "training_load": tl, "strava_activity": upd.get("id")})            