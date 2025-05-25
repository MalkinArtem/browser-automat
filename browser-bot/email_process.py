import os
import time
import logging
import pandas as pd
import re

from database.db import SessionLocal
from database.models import Profile
from sqlalchemy.sql.expression import func

from tenacity import retry, stop_after_attempt, wait_fixed

from utils import (
    ensure_screenshots_dir,
    rescue_from_spam_all_targets,
    setup_gologin,
    configure_browser,
    login_to_email,
    process_focused_and_other_tabs,
    log_unspammed_senders,
    delete_all_messages,
    process_focused_and_other_tabs_archive,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

GOLOGIN_TOKEN = os.environ.get("GOLOGIN_TOKEN")
if not GOLOGIN_TOKEN:
    raise ValueError("GOLOGIN_TOKEN is not set in the environment.")

HEADLESS = 0

JUNK = 1
UNJUNK = 0
DELETE = 0


def process_full_flow(driver, email):
    if JUNK:
        process_focused_and_other_tabs(driver, email)

    if UNJUNK:
        unspammed = rescue_from_spam_all_targets(driver, ['franco'])
        log_unspammed_senders(unspammed, email)
        process_focused_and_other_tabs_archive(driver, email)

    if DELETE:
        delete_all_messages(driver)


def handle_browser_session(profile_id, email, password):
    gl, driver = None, None
    try:
        gl, port = setup_gologin(profile_id)
        driver = configure_browser(port, HEADLESS)
        login_to_email(driver, email, password)
        process_full_flow(driver, email)
        return True
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"[CLEANUP] Closed browser for {email}.")
            except Exception as e:
                logger.warning(f"[CLEANUP] Failed to quit browser: {e}")
        if gl:
            try:
                gl.stop()
                logger.info(f"[CLEANUP] Stopped GoLogin profile for {email}.")
            except Exception as e:
                logger.warning(f"[CLEANUP] Failed to stop GoLogin profile: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def process_account(email: str, password: str, profile_id: str):
    logger.info(f"[START] Processing account: {email}")
    try:
        try:
            handle_browser_session(profile_id, email, password)
            logger.info(f"[DONE] Successfully processed account: {email}")
            with open("results.csv", "a") as f:
                f.write(f"{email},success\n")
            return
        except Exception as e:
            logger.warning(f"[WARN] Initial profile failed post-login flow for {email}: {e}")
            logger.info(f"[RETRY] Re-running {email} one more time with same profile")
            handle_browser_session(profile_id, email, password)
            logger.info(f"[RETRY SUCCESS] Second run worked for {email}")
            with open("results.csv", "a") as f:
                f.write(f"{email},success_after_retry\n")
            return
    except Exception as first_error:
        logger.error(f"[ERROR] Both attempts with original profile failed: {first_error}")
        db_retry = SessionLocal()
        try:
            alt_profiles = db_retry.query(Profile).order_by(
                func.random()).limit(2).all()
            alt_profiles = [p for p in alt_profiles if
                            p.profile_id != profile_id]

            if not alt_profiles:
                logger.warning(
                    f"[RETRY] No random profiles found in DB for retry")
            else:
                for i, alt_profile in enumerate(alt_profiles):
                    try:
                        logger.warning(
                            f"[RETRY] Attempt {i + 3} with random profile {alt_profile.profile_id}")
                        handle_browser_session(alt_profile.profile_id, email,
                                               password)
                        logger.info(
                            f"[RETRY SUCCESS] Retry {i + 3} worked for {email}")
                        with open("results.csv", "a") as f:
                            f.write(
                                f"{email},success_random_profile_{i + 1}\n")
                        return
                    except Exception as retry_error:
                        logger.error(
                            f"[RETRY FAIL] Attempt {i + 3} failed for {email}: {retry_error}")
        except Exception as retry_error:
            logger.error(f"[RETRY FAIL] Retry with random profile failed: {retry_error}")
        finally:
            db_retry.close()

    with open("results.csv", "a") as f:
        f.write(f"{email},error\n")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_email = re.sub(r'[^\w.-]', '_', email)
    try:
        os.makedirs("screenshots", exist_ok=True)
        logger.warning(f"[FAILURE] Screenshot would be saved at: screenshots/{safe_email}_error_{timestamp}.png")
    except Exception as screenshot_error:
        logger.warning(f"Failed to record screenshot path: {screenshot_error}")


def main():
    ensure_screenshots_dir()
    if JUNK:
        emails = pd.read_csv("emails/emails_to_junk.csv")
    elif UNJUNK:
        emails = pd.read_csv("emails/emails_to_unjunk.csv")
    elif DELETE:
        emails = pd.read_csv("emails/emails_to_delete.csv")
    else:
        logger.error("Nothing to do: JUNK, UNJUNK, DELETE are all disabled.")
        return

    log_file_path = "failed_accounts.log"
    db = SessionLocal()

    for _, row in emails.iterrows():
        email = row["Email"]

        profile = db.query(Profile).filter_by(email=email).first()
        if not profile:
            logger.warning(f"Email not found in DB: {email}")
            continue

        password = profile.password
        profile_id = profile.profile_id

        try:
            process_account(email, password, profile_id)
        except Exception as e:
            logger.error(f"[FAIL] Final failure for {email}: {e}")
            import traceback
            logger.debug(traceback.format_exc())

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"[{timestamp}] Failed after retries: {email}\n")

    db.close()


if __name__ == "__main__":
    main()