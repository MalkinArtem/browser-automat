
def mark_emails_as_spam_headless(driver) -> None:
    processed_ids = set()

    try:
        while True:
            time.sleep(3)

            try:
                emails = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((
                        By.XPATH,
                        "//div[contains(@data-convid, '') and @role='option']"
                    ))
                )
            except Exception:
                logger.warning("No emails found on page.")
                break

            visible_emails = [el for el in emails if el.is_displayed()]
            new_emails = [el for el in visible_emails if el.get_attribute("data-convid") not in processed_ids]

            if not new_emails:
                logger.info("No unprocessed visible emails.")
                break

            email_element = new_emails[0]
            email_id = email_element.get_attribute("data-convid")
            processed_ids.add(email_id)

            logger.info(f"Processing email: {email_id}")

            try:
                WebDriverWait(driver, 3).until_not(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
                )
            except:
                logger.warning("Modal dialog still open")

            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_element)
                random_sleep()
                click_with_human_mouse(driver, email_element)
            except Exception as e:
                logger.warning(f"Failed to click email: {e}")
                continue

            random_sleep()

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']"))
                )
            except:
                logger.warning("Email content not loaded.")
                continue

            ActionChains(driver).send_keys("j").perform()
            random_sleep()

            report_clicked = False
            for attempt in range(2):
                try:
                    report_btn = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Report']"))
                    )
                    click_with_human_mouse(driver, report_btn)
                    logger.info("Clicked 'Report'")
                    random_sleep()
                    report_clicked = True

                    try:
                        ok_btn = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='OK']"))
                        )
                        click_with_human_mouse(driver, ok_btn)
                        logger.info("Clicked 'OK' after report")
                    except:
                        logger.info("No OK button appeared after report")
                    break

                except Exception as e:
                    logger.warning(f"Report click failed (attempt {attempt+1}): {e}")
                    if attempt == 0:
                        time.sleep(1)
            if not report_clicked:
                logger.info("No 'Report' button found — skipping.")
    except Exception as e:
        logger.error(f"Exception in process_emails: {repr(e)}")