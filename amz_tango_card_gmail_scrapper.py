"""
Extract Microsoft Rewards Amazon Gift Cards from Gmail automatically.
"""

import platform
import imaplib
import email
import json
import random
import sys
from argparse import ArgumentParser
import time
import traceback

import ipapi

from termcolor import cprint

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


def argument_parser():
    """Gets arguments from command line (--headless, ...)"""

    parser = ArgumentParser(
        description="Amazon Tango Card Gmail Scrapper",
        allow_abbrev=False,
        usage="You may execute the program with the default configuration or use arguments to configure available options.",
    )

    parser.add_argument(
        "--headless",
        help="[Optional] Enable headless browser.",
        action="store_true",
        required=False,
    )

    arguments = parser.parse_args()

    return arguments


def get_lang_code():
    """Obtains language code of the user using ipapi.

    Returns:
        str: Language code of the user.
    """

    try:
        nfo = ipapi.location()
        lang = nfo["languages"].split(",")[0]
        return lang
    # ipapi may sometimes raise an exception due to its limitations, in that case, I default to en-US.
    except Exception:
        return "en-US"


def set_up_browser():
    """Sets up a Selenium chromium browser.

    Returns:
        WebDriver: Configured Selenium chromium browser.
    """

    arguments = argument_parser()

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 Edg/107.0.1418.24"
    options = Options()

    options.add_argument("user-agent=" + user_agent)
    options.add_argument("lang=" + get_lang_code())
    options.add_argument("--disable-blink-features=AutomationControlled")
    prefs = {
        "profile.default_content_setting_values.geolocation": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    if arguments.headless:
        options.add_argument("--headless")
    options.add_argument("log-level=3")
    options.add_argument("--start-maximized")
    if platform.system() == "Linux":
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    chrome_browser_obj = None
    try:
        chrome_browser_obj = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )
    except Exception:
        chrome_browser_obj = webdriver.Chrome(options=options)
    finally:
        return chrome_browser_obj


def get_account_credentials():
    """Obtains account's credentials from "account.json".

    Returns:
        list: A list containing account's credentials.
    """
    try:
        account = json.load(open("account.json", "r"))[0]
        cprint("[ACCOUNT LOADER] Account successfully loaded.", "green")
        return account
    except FileNotFoundError:
        with open("account.json", "w") as f:
            f.write(
                json.dumps(
                    [
                        {
                            "username": "email@gmail.com",
                            "password": "GoogleAppPassword",
                        }
                    ],
                    indent=2,
                )
            )
        cprint('[ACCOUNT LOADER] "account.json" not found, creating file...', "red")
        print(
            '[ACCOUNT LOADER] Please fill you account creadentials in "account.json" and rerun the script. Exiting...'
        )
        sys.exit()


def get_tango_credentials(username: str, password: str):
    """Obstains every tango credential from Microsoft emails in an account.

    Args:
        username (str): Account's Gmail email
        password (str): Account's Google App Password

    Returns:
        list: List containing scrapped tango credentials
    """
    # URL for IMAP connection
    imap_url = "imap.gmail.com"

    # Connection with Gmail using SSL
    mail = imaplib.IMAP4_SSL(imap_url)

    # Log in using credentials
    mail.login(username, password)

    # Select Inbox to fetch emails
    mail.select("Inbox")

    # Email search
    key = "FROM"
    value = "microsoftrewards@email.microsoftrewards.com"
    status, data = mail.search(None, key, value)

    # Get IDs of emails
    ids = data[0].split()

    # Capture all messages from emails
    messages = []
    for id in ids:
        status, data = mail.fetch(id, "(RFC822)")
        messages.append(data)

    # Get tango security codes and links from each message
    tango_credentials = []
    counter = 0
    for message in messages:
        for response_part in message:
            if isinstance(response_part, tuple):
                current_msg = email.message_from_bytes(response_part[1])

                # Get code and link from the body of the email
                for part in current_msg.walk():
                    text = part.get_payload()

                    security_code = text.split(
                        "</div><div class='tango-credential-value'>", 1
                    )[1].split("<", 1)[0]

                    link = text.split(
                        "</div><div class='tango-credential-key'><a href='", 1
                    )[1].split("'", 1)[0]

                    # Check required elements have been found
                    if security_code and link:
                        tango_credential = {
                            "security_code": security_code,
                            "link": link,
                        }

                        tango_credentials.append(tango_credential)

                        current_msg_id = ids[counter]
                        if isinstance(current_msg_id, bytes):
                            # If it's a bytes type, decode to str
                            current_msg_id = current_msg_id.decode()

                        # Move current email to trash
                        mail.store(current_msg_id, "+X-GM-LABELS", "\\Trash")
        counter += 1

    mail.close()
    mail.logout()
    return tango_credentials


def get_amazon_gift_card(browser: WebDriver, credential: dict):
    # Get to specific tango redeeming website
    browser.get(credential["link"])
    time.sleep(random.uniform(2, 3))

    print("[TANGO REDEEMER] Writing security code...")
    browser.find_element(By.ID, value="input-45").send_keys(credential["security_code"])
    time.sleep(random.uniform(1, 2))

    print("[TANGO REDEEMER] Getting Amazon Gift Card...")
    browser.find_element(
        By.XPATH,
        value="/html/body/div[1]/div/main/div/div/div/div/div[1]/div/div/div[2]/div[2]/div/div/form/div[2]/button",
    ).click()
    time.sleep(random.uniform(2, 3))

    # Check if card was correctly redeemed
    if browser.find_elements(
        By.XPATH,
        value="/html/body/div[1]/div[1]/main/div/div/div/div/div[1]/div/div[1]/div[2]/div[2]/div/div/div/div[1]/div/div[2]/span",
    ):
        code = browser.find_element(
            By.XPATH,
            value="/html/body/div[1]/div[1]/main/div/div/div/div/div[1]/div/div[1]/div[2]/div[2]/div/div/div/div[1]/div/div[2]/span",
        ).text
        cprint("[TANGO REDEEMER] Amazon Gift Card successfully obtained!", "green")
        return code
    else:
        cprint(
            "[TANGO REDEEMER] Credentials are not valid, Amazon Gift Card not obtained!",
            "red",
        )
        return ""


def store_code(code):
    with open("codes.txt", "a") as f:
        f.write(code + "\n")


def clean_stored_codes():
    with open("codes.txt", "w") as f:
        f.write("")


# Send email function (rework code storing)


def main():
    """
    Extract Microsoft Rewards Amazon Gift Cards from Gmail automatically.
    """

    account = get_account_credentials()
    tango_credentials = get_tango_credentials(account["username"], account["password"])

    if not tango_credentials:
        cprint("[TANGO SCRAPPER] No cards have been found, exiting...", "red")
        sys.exit()
    else:
        clean_stored_codes()
        for credential in tango_credentials:
            # Set up Selenium browser
            try:
                browser = set_up_browser()
            except Exception:
                print(traceback.format_exc())
                cprint("[BROWSER] Error trying to set up browser...", "red")
                sys.exit()

            code = get_amazon_gift_card(browser, credential)
            browser.quit()

            if code != "":
                print('[CODE STORER] Storing in "codes.txt" obtained code...')
                store_code(code)


if __name__ == "__main__":
    main()