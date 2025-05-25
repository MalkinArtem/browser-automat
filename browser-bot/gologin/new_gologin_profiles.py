import os
import csv
import random
import pandas as pd
from gologin import GoLogin
from dotenv import load_dotenv
from database.db import SessionLocal
from database.models import Profile

load_dotenv()

GOLOGIN_TOKEN = os.environ.get("GOLOGIN_TOKEN")

if not GOLOGIN_TOKEN:
    raise ValueError("GOLOGIN_TOKEN is not set.")

OS_OPTIONS = ["win", "mac", "lin"]
PLATFORM_OPTIONS = ["Win32", "MacIntel", "Linux x86_64"]
VENDOR_OPTIONS = ["Google Inc.", "Apple Computer, Inc."]
COUNTRIES = ["US", "GB", "CA", "AU", "NZ"]
SCREENS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 2560, "height": 1440}
]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

import json

def create_profile_with_sdk(email: str, password: str) -> str:
    gl = GoLogin({"token": GOLOGIN_TOKEN})
    profile_name = email.split("@")[0]
    geo = random.choice(COUNTRIES)
    screen = random.choice(SCREENS)
    resolution = f"{screen['width']}x{screen['height']}"

    profile_id = gl.create({
        "name": profile_name,
        "os": random.choice(OS_OPTIONS),
        "navigator": {
            "language": "en-US",
            "platform": random.choice(PLATFORM_OPTIONS),
            "vendor": random.choice(VENDOR_OPTIONS),
            "userAgent": random.choice(USER_AGENTS),
            "resolution": resolution,
            "hardwareConcurrency": random.randint(2, 8),
            "deviceMemory": random.choice([4, 8, 16])
        },
        "screen": screen,
        "geoProxy": {"country": geo},
        "proxy": {"mode": "gologin"},
        "timezone": {"enabled": True},
        "webRTC": {"mode": "alerted"},
        "canvas": {"mode": "noise"},
        "webGL": {"mode": "noise"}
    })

    print(f"[DEBUG] Created profile ID for {email}: {profile_id}")

    if not isinstance(profile_id, str) or not profile_id.isalnum():
        raise ValueError(f"Invalid profile ID returned for {email}: {profile_id}")

    save_profile_entry(email, password, profile_id)
    return profile_id

def save_profile_entry(email: str, password: str, profile_id: str) -> None:
    file_exists = os.path.isfile("../emails/profiles.csv")
    with open("../emails/profiles.csv", mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Email", "Pass", "Profile_id"])
        writer.writerow([email, password, profile_id])

    db = SessionLocal()
    try:
        db_profile = Profile(email=email, password=password, profile_id=profile_id)
        db.add(db_profile)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"DB Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    df = pd.read_csv("../emails/emails_to_profiles.csv")
    for _, row in df.iterrows():
        email = row["Email"]
        password = row["Pass"]
        try:
            profile_id = create_profile_with_sdk(email, password)
            print(f"Created profile ID: {profile_id}")
        except Exception as e:
            print(f"Failed to create profile for {email}: {e}")
