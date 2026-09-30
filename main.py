import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks, HTTPException
from playwright.async_api import async_playwright


app = FastAPI(title="GSRTC Scraper Service")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SCREENSHOT_PATH = "screenshot.png"


class SearchRequest(BaseModel):
    source: str = "NAVSARI"
    destination: str = "SURAT"


def send_to_telegram(image_path: str, caption: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Skipping Telegram upload.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as img:
            response = requests.post(
                url,
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                },
                files={"photo": img},
                timeout=30,
            )
        if response.ok:
            print("Successfully sent screenshot to Telegram!")
        else:
            print(f"Failed to send to Telegram: {response.text}")
    except Exception as e:
        print(f"Error dispatching to Telegram: {e}")


async def run_agent(source: str = "NAVSARI", destination: str = "SURAT"):
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    date_display = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    print(f"Starting GSRTC search ({source} -> {destination}) at {date_display}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1366, "height": 1800},
            timezone_id="Asia/Kolkata",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        try:
            # 1. Open GSRTC portal
            await page.goto(
                "https://gsrtc.in/site/", timeout=60000, wait_until="domcontentloaded"
            )
            await page.wait_for_timeout(3000)

            # Dismiss promotional modal/popup if present
            for close_selector in [
                ".close",
                ".btn-close",
                "#closeModal",
                "button[aria-label='Close']",
            ]:
                close_btn = page.locator(close_selector).first
                if await close_btn.is_visible():
                    await close_btn.click()
                    await page.wait_for_timeout(500)

            # 2. Enter Source
            from_input = page.locator(
                "input[placeholder*='From'], #matchFromPlace"
            ).first
            await from_input.click()
            await from_input.fill(source)
            await page.wait_for_timeout(1200)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")

            # 3. Enter Destination
            to_input = page.locator("input[placeholder*='To'], #matchToPlace").first
            await to_input.click()
            await to_input.fill(destination)
            await page.wait_for_timeout(1200)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")

            # 4. Click Search
            search_btn = page.locator(
                "button:has-text('Search'), input[value*='Search']"
            ).first
            await search_btn.click()

            # 5. Wait for results to render and capture screenshot
            await page.wait_for_timeout(7000)
            await page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print("Captured search results screenshot.")

            caption = (
                f"🚌 *GSRTC Bus Schedule: {source} → {destination}*\n"
                f"📅 *Captured:* {date_display}"
            )
            send_to_telegram(SCREENSHOT_PATH, caption)

        except Exception as e:
            print(f"Error encountered: {e}")
            await page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            error_caption = (
                f"⚠️ *GSRTC Agent Warning ({source} → {destination})*\n"
                f"📅 {date_display}\n"
                f"Could not complete full form flow, attached current screen state.\n"
                f"`{str(e)[:120]}`"
            )
            send_to_telegram(SCREENSHOT_PATH, error_caption)

        finally:
            await browser.close()


@app.post("/scrape-gsrtc")
async def trigger_gsrtc_scrape(
    request: Optional[SearchRequest] = None, background_tasks: BackgroundTasks = None
):
    source = request.source if request else "NAVSARI"
    dest = request.destination if request else "SURAT"

    # Runs as a background task to prevent the HTTP client connection from timing out
    background_tasks.add_task(run_agent, source, dest)

    return {
        "status": "queued",
        "message": f"Scrape task initiated for {source} -> {dest}.",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok"}
