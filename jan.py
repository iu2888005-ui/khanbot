import os
import re
import json
import time
import requests
from urllib.parse import urlparse, urljoin
from playwright.sync_api import sync_playwright

TOKEN = os.environ["8688494134:AAEFObEX1p4syZwUBPVe-iG5GXkWDj311CA"]
CHAT_ID = os.environ["8295417969"]

STATE_FILE = "sent.json"

EXAMS = {
    "A1": "https://www.goethe.de/ins/in/en/spr/prf/gzsd1.cfm",
    "B1": "https://www.goethe.de/ins/in/en/spr/prf/gzb1.cfm",
}

PATTERN = re.compile(
    r"\b(book|booking|register|registration|reserve)\b",
    re.I
)

def telegram(message):
    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "disable_web_page_preview": False
        },
        timeout=30
    )
    response.raise_for_status()

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"sent": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def find_booking(page, context, level, exam_url):
    page.goto(
        exam_url,
        wait_until="domcontentloaded",
        timeout=60000
    )
    page.wait_for_timeout(5000)

    candidates = page.locator("a, button").all()

    for candidate in candidates:
        try:
            if not candidate.is_visible():
                continue

            if not candidate.is_enabled():
                continue

            label = (
                candidate.inner_text()
                or candidate.get_attribute("aria-label")
                or ""
            ).strip()

            if not PATTERN.search(label):
                continue

            href = candidate.get_attribute("href") or ""

            if href.startswith(("javascript:", "mailto:")):
                continue

            print(f"{level}: candidate found: {label}")

            old_url = page.url
            old_pages = list(context.pages)

            try:
                candidate.click(timeout=15000)
            except Exception as e:
                print("Click failed:", e)
                continue

            page.wait_for_timeout(6000)

            new_pages = [
                p for p in context.pages
                if p not in old_pages
            ]

            if new_pages:
                destination = new_pages[-1]
                try:
                    destination.wait_for_load_state(
                        "domcontentloaded",
                        timeout=20000
                    )
                except Exception:
                    pass
                final_url = destination.url
            else:
                final_url = page.url

            # د هماغې پاڼې URL مه استوه
            if final_url == old_url or final_url == exam_url:
                continue

            parsed = urlparse(final_url)

            if parsed.scheme != "https":
                continue

            # یوازې د Book کلیک وروسته نوی URL
            # او د ثبت‌نام اړوند مسیر تایید کړه
            path = (
                parsed.path + " " + parsed.query
            ).lower()

            if not any(word in path for word in [
                "book", "register", "registration",
                "exam", "appointment", "shop", "checkout"
            ]):
                # که نوی URL د بل ډومېن وي، بیا هم یې
                # یوازې هغه وخت ومنه چې د کلیک له لارې راغلی وي.
                if parsed.netloc == urlparse(exam_url).netloc:
                    continue

            return final_url

        except Exception as e:
            print("Candidate error:", e)

    return None

def main():
    state = load_state()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for level, exam_url in EXAMS.items():
            try:
                link = find_booking(
                    page, context, level, exam_url
                )

                if not link:
                    print(level, "No confirmed booking URL.")
                    continue

                if link in state["sent"]:
                    print("Already sent:", link)
                    continue

                telegram(
                    "🚨 Goethe India Booking page link\n\n"
                    f"📘 Level: {level}\n"
                    "🌍 Country: India\n\n"
                    "👇 د براوزر لپاره لینک:\n"
                    f"{link}\n\n"
                    "خپله فورمه خلاصه او ثبت‌نام بشپړ کړه."
                )

                state["sent"].append(link)
                save_state(state)

                print("Telegram link sent:", link)

            except Exception as e:
                print(level, "Error:", str(e))

        browser.close()

if __name__ == "__main__":
    main() 
