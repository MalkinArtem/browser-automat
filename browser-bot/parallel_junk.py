import time
import logging
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

from database.db import SessionLocal
from database.models import Profile
from email_process import process_account, ensure_screenshots_dir

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))
logger.addHandler(console_handler)

MAX_WORKERS = 3

def main():
    ensure_screenshots_dir()
    emails_df = pd.read_csv("emails/emails_to_junk.csv")
    log_file_path = "failed_accounts.log"

    db = SessionLocal()
    tasks = []
    for _, row in emails_df.iterrows():
        email = row["Email"]
        profile = db.query(Profile).filter_by(email=email).first()
        if not profile:
            logger.warning(f"Email not found in DB: {email}")
            continue
        tasks.append((email, profile.password, profile.profile_id))
    db.close()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_account, email, pwd, pid): email
            for email, pwd, pid in tasks
        }

        for fut in as_completed(futures):
            email = futures[fut]
            try:
                fut.result()
                logger.info(f"[CONCURRENCY] Finished processing {email}")
            except Exception as e:
                logger.error(f"[CONCURRENCY] Error processing {email}: {e}")
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                with open(log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] Failed: {email} — {e}\n")

if __name__ == "__main__":
    main()