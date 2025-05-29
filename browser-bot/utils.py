import os
import time
import random
import logging
import requests
import datetime
import csv

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException
)

from gologin import GoLogin

log_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)
load_dotenv()

GOLOGIN_TOKEN = os.environ.get("GOLOGIN_TOKEN")
if not GOLOGIN_TOKEN:
    raise ValueError("GOLOGIN_TOKEN is not set in the environment.")

def random_sleep() -> None:
    time.sleep(random.uniform(0.5, 2.0))

def ensure_screenshots_dir() -> None:
    os.makedirs("screenshots", exist_ok=True)

def verify_debugger(port: int, max_retries: int = 3) -> bool:
    url = f"http://127.0.0.1:{port}/json/version"
    for _ in range(max_retries):
        try:
            time.sleep(2)
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                return True
        except Exception:
            pass
    return False

def human_typing(element, text, delay_range=(0.05, 0.15)):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*delay_range))

def click_with_human_mouse(driver, element) -> None:
    try:
        WebDriverWait(driver, 5).until(
            lambda d: element.is_displayed() and element.is_enabled()
        )
        time.sleep(0.2)
        element.click()
        time.sleep(0.6)
    except Exception as e:
        logger.warning(f"Failed to click element: {e}")

def timestamped_name(prefix="screenshot"):
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"screenshots/{prefix}_{now}.png"

def setup_gologin(profile_id: str) -> (GoLogin, int):
    """
    Инициализация и запуск профиля GoLogin.
    """
    gl = GoLogin({
        "token": GOLOGIN_TOKEN,
        "profile_id": profile_id,
        "headless": True,
    })
    logger.info(f"[INFO] Starting GoLogin profile: {profile_id}")
    port = gl.start().split(":")[-1]
    logger.info(f"DevTools on port: {port}")

    if not verify_debugger(int(port)):
        raise Exception("DevTools debugger is not responding.")
    return gl, port

def configure_browser(port: int, headless: bool) -> webdriver.Chrome:
    """
    Конфигурирование Selenium WebDriver для работы с GoLogin.
    """
    options = Options()
    options.set_capability(
        "goog:chromeOptions",
        {"debuggerAddress": f"127.0.0.1:{port}"}
    )
    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--window-size=1280,720")
    options.add_argument("--lang=en-US")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_argument("--accept-lang=en-US,en;q=0.9")
    options.add_experimental_option(
        "excludeSwitches", ["enable-automation"]
    )
    options.add_experimental_option("useAutomationExtension", False)

    chromedriver_path = os.getenv("CHROMEDRIVER_PATH")

    if not chromedriver_path or not os.path.isfile(chromedriver_path):
        raise FileNotFoundError(
            f"Chromedriver not found at path: {chromedriver_path}")

    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {
            "source": (
                "Object.defineProperty(navigator, 'language', "
                "{get: () => 'en-US'});"
                "Object.defineProperty(navigator, 'languages', "
                "{get: () => ['en-US', 'en']});"
            )
        }
    )

    return driver

def login_to_email(driver, email, password, max_attempts=3):
    """
    Выполняет вход в учетную запись пользователя через Outlook.
    Если возникает ошибка — повторяет попытку входа (до max_attempts раз).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"[{email}] Login attempt {attempt}")
            wait = WebDriverWait(driver, 40)
            driver.get("https://outlook.live.com/owa/?lang=en-us")
            logger.info("Opened Outlook")

            try:
                wait.until(lambda d: d.execute_script(
                    "return document.readyState") == "complete")
                logger.info("Page DOM fully loaded.")
            except TimeoutException:
                logger.warning("Page took too long to load completely.")

            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                logger.info("Page body is present.")
            except TimeoutException:
                raise Exception("Page body did not appear in time.")

            try:
                cookie_btn = wait.until(EC.element_to_be_clickable((
                    By.XPATH, "//button[contains(text(), 'Accept')]")))
                click_with_human_mouse(driver, cookie_btn)
                logger.info("Accepted cookies.")
            except Exception:
                logger.info("Cookie button not found or not clickable.")

            selectors = [
                "//a[contains(text(), 'Sign in')]",
                "//a[contains(@class, 'signInLink')]",
                "//a[@data-task='signin']",
                "//span[contains(text(), 'Sign in')]/parent::*",
                "//div[contains(@class, 'SignIn')]//a",
                "//a[@role='button' and contains(., 'Sign in')]",
                "//a[@aria-label='Sign in']",
            ]

            found = False
            for selector in selectors:
                try:
                    for el in driver.find_elements(By.XPATH, selector):
                        if el.is_displayed():
                            click_with_human_mouse(driver, el)
                            logger.info(f"Clicked 'Sign in' using selector: {selector}")
                            found = True
                            break
                    if found:
                        break
                except Exception:
                    logger.info(f"Error interacting with selector: {selector}")
            if not found:
                raise Exception("Sign in button not found or not clickable")

            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)
            logger.info(f"Page loaded: {driver.current_url}")

            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(5)

            email_input = None
            for by, selector in [
                (By.NAME, "loginfmt"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.XPATH, "//input[@type='email' or @name='loginfmt']")
            ]:
                try:
                    email_input = wait.until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    if email_input.is_displayed():
                        click_with_human_mouse(driver, email_input)
                        email_input.clear()
                        human_typing(email_input, email)
                        logger.info(f"Entered email: {email}")
                        break
                except Exception as e:
                    logger.info(
                        f"Error interacting with email input field ({selector}): {e}")
            if not email_input:
                raise Exception("Email input field not found")

            clicked = False
            for by, selector in [
                (By.ID, "idSIButton9"),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Next')]")
            ]:
                try:
                    btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    click_with_human_mouse(driver, btn)
                    clicked = True
                    break
                except Exception:
                    continue

            if not clicked:
                raise Exception("Next button not found or not clickable")

            time.sleep(7)
            password_input = wait.until(
                EC.presence_of_element_located((By.NAME, "passwd"))
            )
            human_typing(password_input, password)
            logger.info("Entered password")

            btn_si = wait.until(
                EC.element_to_be_clickable((By.ID, "idSIButton9"))
            )
            click_with_human_mouse(driver, btn_si)
            time.sleep(15)

            try:
                logger.info("Try to click Yes button after password step")
                confirm_next_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((
                        By.ID, "idSubmit_ProofUp_Redirect"
                    ))
                )
                click_with_human_mouse(driver, confirm_next_btn)
                logger.info("Clicked confirmation 'Yes' (idSubmit_ProofUp_Redirect)")
                random_sleep()

                logger.info("Waiting for potential confirmation step after password...")
                time.sleep(7)
                try:
                    skip_setup_btn = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((
                            By.XPATH, "//button[normalize-space()='Skip setup']"
                        ))
                    )
                    click_with_human_mouse(driver, skip_setup_btn)
                    logger.info("Clicked 'Skip setup' button")
                    random_sleep()
                except Exception:
                    logger.info("No 'Skip setup' button appeared")
            except Exception as e:
                logger.info("No confirmation 'Yes' button appeared after password step")
                logger.debug(f"Exception detail: {e}")

            time.sleep(7)
            btn_si = wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
            click_with_human_mouse(driver, btn_si)
            time.sleep(10)
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            time.sleep(10)
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            logger.info("Try to pressed 'Enter' to choose an account.")
            time.sleep(5)
            try:
                skip_setup_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH, "//button[normalize-space()='Skip setup']"
                    ))
                )
                click_with_human_mouse(driver, skip_setup_btn)
                logger.info("Clicked 'Skip setup' button")
                random_sleep()
            except Exception:
                logger.info("No 'Skip setup' button appeared")
            time.sleep(10)
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            logger.info("Try to pressed 'Enter' to choose an account.")
            try:
                skip_setup_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH, "//button[normalize-space()='Skip setup']"
                    ))
                )
                click_with_human_mouse(driver, skip_setup_btn)
                logger.info("Clicked 'Skip setup' button")
                random_sleep()
                time.sleep(10)
                ActionChains(driver).send_keys(Keys.ENTER).perform()
                logger.info("Try to pressed 'Enter' to choose an account.")
            except Exception:
                logger.info("No 'Skip setup' button appeared")

            WebDriverWait(driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
            )
            logger.info(f"[{email}] Logged in and inbox loaded.")
            return

        except Exception as e:
            logger.warning(f"[{email}] Login attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                logger.info("Retrying login...")
                time.sleep(5)
            else:
                logger.error(f"[{email}] All login attempts failed.")
                raise

def mark_visible_emails_as_spam(driver) -> None:
    processed_ids = set()

    while True:
        time.sleep(3)
        try:
            emails = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((
                    By.XPATH,
                    "//div[@role='option' and @data-convid]"
                ))
            )
        except Exception:
            logger.warning("No emails found on page.")
            break

        visible_emails = []
        for el in emails:
            try:
                if el.is_displayed():
                    visible_emails.append(el)
            except:
                continue

        new_emails = []
        for el in visible_emails:
            try:
                convo_id = el.get_attribute("data-convid")
                if convo_id and convo_id not in processed_ids:
                    new_emails.append(el)
            except:
                continue

        if not new_emails:
            logger.info("No unprocessed visible emails.")
            break

        for email_element in new_emails:
            try:
                email_id = email_element.get_attribute("data-convid")
                processed_ids.add(email_id)
                logger.info(f"Processing email: {email_id}")

                try:
                    WebDriverWait(driver, 3).until_not(
                        EC.presence_of_element_located((
                            By.XPATH, "//div[@role='dialog']"
                        ))
                    )
                except:
                    logger.warning("Modal dialog still open")

                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    email_element
                )
                random_sleep()
                click_with_human_mouse(driver, email_element)
                random_sleep()

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, "[role='main']"
                    ))
                )

                ActionChains(driver).send_keys("j").perform()
                logger.info("Pressed 'j'")
                random_sleep()

                report_clicked = False
                for attempt in range(2):
                    try:
                        report_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((
                                By.XPATH,
                                "//button[normalize-space()='Report']"
                            ))
                        )
                        click_with_human_mouse(driver, report_btn)
                        logger.info("Clicked 'Report'")
                        random_sleep()
                        report_clicked = True

                        try:
                            ok_btn = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((
                                    By.XPATH,
                                    "//button[normalize-space()='OK']"
                                ))
                            )
                            click_with_human_mouse(driver, ok_btn)
                            logger.info("Clicked 'OK' after report")
                        except:
                            logger.info("No OK button appeared after report")
                        break
                    except Exception as e:
                        logger.warning(
                            f"Report click failed (attempt {attempt + 1}): {e}"
                        )
                        if attempt == 0:
                            time.sleep(1)

                if not report_clicked:
                    logger.info("No 'Report' button found — skipping.")

                try:
                    WebDriverWait(driver, 5).until_not(
                        EC.presence_of_element_located((
                            By.XPATH,
                            f"//div[@role='option' and "
                            f"@data-convid='{email_id}']"
                        ))
                    )
                    logger.info(f"[OK] Email {email_id} disappeared from DOM.")
                except:
                    logger.warning(
                        f"Email {email_id} is still in DOM."
                    )

                break

            except Exception as e:
                logger.warning(
                    f"Error while processing email element: {e}"
                )
                continue

def process_focused_and_other_tabs(driver, email):
    """
    Обрабатывает вкладки Focused и Other в Outlook.
    """
    logger.info(f"[{email}] Processing Focused tab.")
    mark_visible_emails_as_spam(driver)
    random_sleep()

    try:
        logger.info(f"[{email}]  Switching to Other tab.")
        other_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space()='Other']"))
        )
        click_with_human_mouse(driver, other_tab)
        random_sleep()
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                "return document.readyState") == "complete"
        )
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
        )
        logger.info(f"[{email}] Logged in and inbox loaded.")
        mark_visible_emails_as_spam(driver)
    except Exception as e:
        logger.info(f"[{email}] 'Other' tab not processed: {e}")

def process_focused_and_other_tabs_archive(driver, email):
    """
    Обрабатывает вкладки Focused и Other в Outlook.
    """
    inbox_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//span[normalize-space()='Inbox']"))
    )
    click_with_human_mouse(driver, inbox_btn)
    logger.info(f"[{email}] Inbox loaded.")
    logger.info(f"[{email}] Processing Focused tab.")
    process_archive(driver)
    random_sleep()

    try:
        logger.info(f"[{email}]  Switching to Other tab.")
        other_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space()='Other']"))
        )
        click_with_human_mouse(driver, other_tab)
        random_sleep()
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                "return document.readyState") == "complete"
        )
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
        )
        logger.info(f"[{email}] Logged in and inbox loaded.")
        process_archive(driver)
    except Exception as e:
        logger.info(f"[{email}] 'Other' tab not processed: {e}")

def process_archive(driver) -> None:
    try:
        logger.info("Waiting for email list to appear...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@role='listbox']")
            )
        )

        actions = ActionChains(driver)
        actions.key_down(Keys.CONTROL).send_keys("a").key_up(
            Keys.CONTROL
        )
        actions.send_keys("e").perform()
        logger.info("Pressed Ctrl+A and E to archive visible emails.")

        time.sleep(10)

        while True:
            try:
                emails = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located(
                        (
                            By.XPATH,
                            "//div[@role='option' and @data-convid]"
                        )
                    )
                )
                visible_emails = [
                    el for el in emails if el.is_displayed()
                ]
            except Exception:
                logger.info("No emails found, archive complete.")
                break

            if not visible_emails:
                logger.info("No visible emails left — finished.")
                break

            logger.info(
                f"{len(visible_emails)} emails still visible — "
                "starting manual archive flow"
            )

            try:
                first_email = visible_emails[0]
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    first_email
                )
                time.sleep(0.5)
                click_with_human_mouse(driver, first_email)
                logger.info("Clicked first visible email.")
            except Exception as e:
                logger.warning(f"Failed to click email: {e}")
                break

            for _ in range(30):
                ActionChains(driver).send_keys("e").perform()
                time.sleep(0.5)

            logger.info("Sent multiple 'E' keys to archive batch.")
            time.sleep(2)

        try:
            ok_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[normalize-space()='OK']")
                )
            )
            click_with_human_mouse(driver, ok_btn)
            logger.info("Clicked 'OK' after archive.")
        except:
            logger.info("No OK button appeared after archive.")

    except Exception as e:
        logger.error(f"Exception in process_archive: {repr(e)}")

def delete_all_messages(driver) -> None:
    try:
        logger.info("Locating 'Inbox' folder...")
        inbox_folder = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[@role='treeitem' and .//span[text()='Inbox']]"
            ))
        )
        ActionChains(driver).move_to_element(inbox_folder).context_click(inbox_folder).perform()
        logger.info("Right-clicked 'Inbox' folder")

        logger.info("Waiting for 'Empty' menu item...")
        empty_item = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[@role='menuitem' and .//span[text()='Empty']]"
            ))
        )
        empty_item.click()
        logger.info("Clicked 'Empty' in folder menu")

        logger.info("Waiting for 'Delete all' confirmation...")
        for attempt in range(2):
            try:
                confirm_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[normalize-space()='Delete all']"
                    ))
                )
                confirm_btn.click()
                logger.info("Clicked 'Delete all' to confirm empty folder")
                time.sleep(20)
                break
            except StaleElementReferenceException:
                logger.warning("Stale element on 'Delete all', retrying...")
                time.sleep(1)
        else:
            raise Exception("Failed to click 'Delete all' after retries.")

        time.sleep(3)

    except TimeoutException as e:
        logger.error(f"[Timeout] Element not found in time: {e}")
        driver.save_screenshot("screenshots/empty_timeout.png")
        raise

    except Exception as e:
        logger.error(f"[Error] Unexpected error in delete_all_messages: {e}")
        driver.save_screenshot("screenshots/empty_generic_error.png")
        raise

def rescue_from_spam_all_targets(driver, target_domains: list) -> list:
    unspammed_senders = []
    try:
        print("[INFO] Scanning Junk folder once for all matching senders...")
        junk_folder = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Junk Email']"))
        )
        click_with_human_mouse(driver, junk_folder)
        random_sleep()

        processed_ids = set()
        scroll_attempts = 0
        max_scrolls = 5

        while True:
            emails = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((
                    By.XPATH, "//div[contains(@data-convid, '') and @role='option']"
                ))
            )
            found = False

            for email_element in emails:
                try:
                    email_id = email_element.get_attribute("data-convid")
                    if not email_id or email_id in processed_ids:
                        continue

                    processed_ids.add(email_id)

                    sender_elem = email_element.find_element(
                        By.XPATH, ".//span[@title]"
                    )
                    sender = sender_elem.get_attribute("title")
                    if not sender or not any(domain.lower() in sender.lower() for domain in target_domains):
                        continue

                    print(f"[INFO] Found junk email from: {sender}")

                    click_with_human_mouse(driver, email_element)
                    random_sleep()

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
                    )
                    random_sleep()

                    try:
                        dropdown_arrow = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//button[contains(@class, 'splitMenuButton') and @aria-label='Expand to see more report options']"
                            ))
                        )
                        click_with_human_mouse(driver, dropdown_arrow)
                        time.sleep(1)

                        not_junk_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//*[(@role='menuitem' or @role='option') and contains(., 'Not junk')]"
                            ))
                        )
                        click_with_human_mouse(driver, not_junk_btn)
                        print("[INFO] Marked as 'Not junk'")
                        unspammed_senders.append(sender)
                        try:
                            confirm_btn = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH,
                                    "//button[normalize-space()='Report']"
                                ))
                            )
                            click_with_human_mouse(driver, confirm_btn)
                            print("[INFO] Confirmed 'Not junk' with 'Report'")
                        except Exception:
                            print("[INFO] No confirmation step required.")
                    except Exception as e:
                        print(f"[WARN] Failed to mark as not junk: {e}")

                    found = True
                    break

                except Exception as e:
                    print(f"[WARN] Skipping email due to error: {e}")
                    continue

            if not found:
                if scroll_attempts < max_scrolls:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", emails[-1])
                        time.sleep(2)
                        scroll_attempts += 1
                        continue
                    except Exception:
                        break
                else:
                    print("[INFO] No more matching emails found.")
                    break

    except Exception as e:
        print(f"[ERROR] Failed in rescue_from_spam_all_targets: {e}")
    return unspammed_senders

def archive_inbox_emails_by_domain(driver, target_domains: list):
    def _archive_visible_emails():
        processed_ids = set()

        while True:
            time.sleep(3)
            try:
                emails = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH, "//div[@role='option' and @data-convid]"
                    ))
                )
            except Exception:
                print("[WARN] No emails found.")
                break

            visible_emails = [el for el in emails if el.is_displayed()]
            new_emails = [el for el in visible_emails if el.get_attribute("data-convid") not in processed_ids]

            if not new_emails:
                print("[INFO] No unprocessed visible emails.")
                break

            for email_element in new_emails:
                email_id = email_element.get_attribute("data-convid")
                processed_ids.add(email_id)

                try:
                    sender_elem = email_element.find_element(By.XPATH, ".//span[@title]")
                    sender = sender_elem.get_attribute("title")
                    if not sender or not any(domain.lower() in sender.lower() for domain in target_domains):
                        continue

                    print(f"[INFO] Archiving email from: {sender}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_element)
                    random_sleep()
                    click_with_human_mouse(driver, email_element)
                except Exception as e:
                    print(f"[WARN] Failed to click email: {e}")
                    continue

                random_sleep()

                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
                    )
                except:
                    print("[WARN] Email content not loaded.")
                    continue

                driver.execute_script("document.querySelector('body').focus();")
                ActionChains(driver).send_keys(Keys.ENTER).pause(0.5).send_keys("e").perform()
                print("[INFO] Archived message with 'Enter' + 'E'")
                random_sleep()

                try:
                    WebDriverWait(driver, 5).until_not(
                        EC.presence_of_element_located((
                            By.XPATH, f"//div[@role='option' and @data-convid='{email_id}']"
                        ))
                    )
                    print(f"[OK] Email {email_id} исчез.")
                except:
                    print(f"[WARN] Email {email_id} всё ещё в DOM.")

    def _switch_to_tab(tab_name):
        try:
            print(f"[INFO] Switching to '{tab_name}' tab...")
            tab_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//button[normalize-space()='{tab_name}']"))
            )
            click_with_human_mouse(driver, tab_btn)
            random_sleep()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
            )
            print(f"[INFO] Scanning '{tab_name}' tab...")
            return True
        except Exception as e:
            print(f"[INFO] '{tab_name}' tab not available or failed: {e}")
            return False

    try:
        print("[INFO] Scanning Inbox (Focused tab)...")
        inbox_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Inbox']"))
        )
        click_with_human_mouse(driver, inbox_btn)
        random_sleep()

        _archive_visible_emails()

        if _switch_to_tab("Other"):
            _archive_visible_emails()

    except Exception as e:
        print(f"[ERROR] Failed in archive_inbox_emails_by_domain: {e}")

def log_unspammed_senders(senders: list, account_email: str):
    if not senders:
        print("[INFO] No senders to log.")
        return

    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"unspammed_{account_email}_{timestamp_str}.csv"

    os.makedirs("logs", exist_ok=True)
    filepath = os.path.join("logs", filename)

    with open(filepath, mode="w", newline='', encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["account", "sender"])
        for sender in senders:
            writer.writerow([account_email, sender])

    print(f"[INFO] Unspammed log saved to: {filepath}")

