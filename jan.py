import os
import re
import json
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

TOKEN = os.environ["8688494134:AAEFObEX1p4syZwUBPVe-iG5GXkWDj311CA"]
CHAT_ID = os.environ["8295417969"]

EXAMS = {
    "A1": "https://www.goethe.de/ins/in/en/spr/prf/gzsd1.cfm",
    "B1": "https://www.goethe.de/ins/in/en/spr/prf/gzb1.cfm",
}

STATE_FILE = "sent.json"

def telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    response = requests.post(
        url,
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

def find_booking(browser, level, exam_url):
    context = browser.new_context()
    page = context.new_page()

    try:
        response = page.goto(
            exam_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        if response and response.status >= 400:
            print(level, "Exam page HTTP error:", response.status)
            return None

        # یوازې د Book / Booking تڼۍ ولټوه
        links = page.locator("a").filter(
            has_text=re.compile(
                r"book your exam date|book exam|book now|booking|register for exam",
                re.I
            )
        )

        count = links.count()
        print(level, "Possible booking buttons:", count)

        for i in range(count):
            button = links.nth(i)

            try:
                if not button.is_visible():
                    continue

                old_url = page.url
                href = button.get_attribute("href") or ""

                print(level, "Clicking booking button...")

                destination = page

                # تڼۍ کېکاږه او نوې پاڼه ونیسه
                try:
                    with context.expect_page(timeout=10000) as new_page:
                        button.click(timeout=15000)

                    destination = new_page.value

                except PlaywrightTimeout:
                    # کېدای شي هماغه ټب کې پاڼه بدله شوې وي
                    destination = page

                try:
                    destination.wait_for_load_state(
                        "domcontentloaded",
                        timeout=30000
                    )
                except Exception:
                    pass

                destination.wait_for_timeout(4000)
                final_url = destination.url

                # که په هماغه ټب کې نه وي خلاص شوی،
                # د تڼۍ اصلي href په نوي ټب کې وازمویه
                if final_url == old_url and href:
                    from urllib.parse import urljoin
                    direct_href = urljoin(old_url, href)

                    if direct_href.startswith("https://"):
                        fallback = context.new_page()
                        fallback.goto(
                            direct_href,
                            wait_until="domcontentloaded",
                            timeout=30000
                        )
                        fallback.wait_for_timeout(3000)
                        final_url = fallback.url
                        destination = fallback

                if not final_url.startswith("https://"):
                    continue

                if final_url == exam_url or final_url == old_url:
                    continue

                body = destination.locator("body").inner_text().lower()

                # د تېروتنې پاڼه مه استوه
                error_words = [
                    "internal server error",
                    "access denied",
                    "page not found",
                    "temporarily unavailable"
                ]

                if any(word in body for word in error_words):
                    print(level, "Booking page returned an error.")
                    continue

                # د بکینګ پاڼې د محتوا لومړنی تایید
                booking_words = [
                    "booking", "registration", "register",
                    "exam date", "select date", "available dates",
                    "appointment", "candidate", "checkout"
                ]

                url_and_body = final_url.lower() + " " + body

                if any(word in url_and_body for word in booking_words):
                    return final_url

                print(level, "Destination not verified as booking page.")

            except Exception as error:
                print(level, "Button error:", error)

        return None

    except Exception as error:
        print(level, "Page error:", error)
        return None

    finally:
        context.close()

def main():
    state = load_state()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        try:
            for level, exam_url in EXAMS.items():
                print("Checking", level)

                link = find_booking(browser, level, exam_url)

                if not link:
                    print(level, "No verified booking page.")
                    continue

                if link in state["sent"]:
                    print("Already notified:", link)
                    continue

                telegram(
                    "🚨 Goethe India Booking Page Found!\n\n"
                    f"📘 Level: {level}\n"
                    "🌍 Country: India\n\n"
                    "👇 د خلاصې شوې بکینګ پاڼې لینک:\n"
                    f"{link}\n\n"
                    "په براوزر کې یې خلاص کړه او خپله ثبت‌نام بشپړه کړه."
                )

                state["sent"].append(link)
                save_state(state)

                print("Booking link sent to Telegram.")

        finally:
            browser.close()

if __name__ == "__main__":
    main() 
