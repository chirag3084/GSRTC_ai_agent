import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCREENSHOT_PATH = "screenshot.png"

def send_to_telegram(image_path: str, caption: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Skipping Telegram upload.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as img:
        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
            files={"photo": img},
            timeout=30
        )
    if response.ok:
        print("Successfully sent screenshot to Telegram!")
    else:
        print(f"Failed to send to Telegram: {response.text}")

def run_agent():
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    date_display = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    print(f"Starting GSRTC search at {date_display}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 1800},
            timezone_id="Asia/Kolkata",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. Open GSRTC portal
            page.goto("https://gsrtc.in/site/", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Dismiss promotional modal/popup if present
            for close_selector in [".close", ".btn-close", "#closeModal", "button[aria-label='Close']"]:
                if page.locator(close_selector).first.is_visible():
                    page.locator(close_selector).first.click()
                    page.wait_for_timeout(500)

            # 2. Enter Source: NAVSARI
            from_input = page.locator("input[placeholder*='From'], #matchFromPlace").first
            from_input.click()
            from_input.fill("NAVSARI")
            page.wait_for_timeout(1200)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")

            # 3. Enter Destination: SURAT
            to_input = page.locator("input[placeholder*='To'], #matchToPlace").first
            to_input.click()
            to_input.fill("SURAT")
            page.wait_for_timeout(1200)
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")

            # 4. Select Today's Date & Click Search
            search_btn = page.locator("button:has-text('Search'), input[value*='Search']").first
            search_btn.click()

            # 5. Wait for results to render and capture screenshot
            page.wait_for_timeout(7000)
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print("Captured search results screenshot.")

            caption = (
                f"🚌 *GSRTC Bus Schedule: Navsari → Surat*\n"
                f"📅 *Captured:* {date_display}"
            )
            send_to_telegram(SCREENSHOT_PATH, caption)

        except Exception as e:
            print(f"Error encountered: {e}")
            # Still take a diagnostic screenshot so you can see where the page got stuck
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            error_caption = (
                f"⚠️ *GSRTC Agent Warning (Navsari → Surat)*\n"
                f"📅 {date_display}\n"
                f"Could not complete full form flow, attached current screen state.\n"
                f"`{str(e)[:120]}`"
            )
            send_to_telegram(SCREENSHOT_PATH, error_caption)
            sys.exit(1)

        finally:
            browser.close()

if __name__ == "__main__":
    run_agent()
