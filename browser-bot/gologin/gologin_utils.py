import os
import csv
import random
import requests
import pandas as pd

from dotenv import load_dotenv
from database.db import SessionLocal
from database.models import Profile

load_dotenv()

GOLOGIN_TOKEN = os.environ.get("GOLOGIN_TOKEN")
API_URL = os.environ.get("API_URL")

if not GOLOGIN_TOKEN:
    raise ValueError("GOLOGIN_TOKEN is not set in the environment.")
if not API_URL:
    raise ValueError("API_URL is not set in the environment.")

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



def create_gologin_profile(email: str, password: str) -> str:
    profile_name = email.split("@")[0]
    geo = random.choice(COUNTRIES)
    screen = random.choice(SCREENS)
    resolution = f"{screen['width']}x{screen['height']}"

    payload = {
        "name": profile_name,
        "browserType": "chrome",
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
    }

    res = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {GOLOGIN_TOKEN}"},
        json=payload,
        timeout=15
    )

    print("Status code:", res.status_code)
    print("Response text:", res.text)

    res.raise_for_status()
    profile_id = res.json().get("id")

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
        db_profile = Profile(
            email=email,
            password=password,
            profile_id=profile_id,
        )
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
            profile_id = create_gologin_profile(email, password)
            print(f"Created profile ID: {profile_id}")
        except Exception as e:
            print(f"Failed to create profile for {email}: {e}")