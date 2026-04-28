import os
import re
import time
import datetime
import requests
from playwright.sync_api import sync_playwright

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"
WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def extract(page):
    results = []

    for el in page.locator("a").all():
        try:
            t = el.inner_text().strip()
            m = re.search(r'(\d{1,2}).*(○|△|×)', t)
            if m:
                results.append(f"{m.group(1)}{m.group(2)}")
        except:
            pass

    return results


def wait_links(page, old, timeout=10000):
    page.wait_for_function(
        """(old) => {
            const now = Array.from(document.querySelectorAll('a'))
                .map(e => e.innerText);
            return JSON.stringify(now) !== JSON.stringify(old);
        }""",
        old,
        timeout=timeout
    )


def safe_click_text(page, text):
    locator = page.locator(f"text={text}")
    locator.first.wait_for(timeout=5000)
    locator.first.click()


def run():
    with sync_playwright() as p:
        log("🚀 start")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(URL)
            page.wait_for_url("**Wg_ModeSelect.aspx**")

            # -------------------
            # 画面遷移（安定版）
            # -------------------
            safe_click_text(page, "公共施設予約メニュー")
            safe_click_text(page, "1. 空き照会")
            safe_click_text(page, "次頁")
            safe_click_text(page, "柳北スポーツプラザ")

            page.click("input[name='ucPCFooter$btnForward']")

            safe_click_text(page, "カレンダー")
            safe_click_text(page, "1ヶ月")

            page.click("input[name='ucPCFooter$btnForward']")

            # -------------------
            # 1ページ目
            # -------------------
            log("📑 1P")

            res1 = extract(page)
            log(res1)

            old = page.locator("a").all_inner_texts()

            # -------------------
            # 次ページ（ここ修正）
            # -------------------
            log("⏭️ next")

            # ボタン待ち
            next_btn = page.locator("text=次へ >>").first
            next_btn.wait_for(timeout=10000)
            next_btn.click()

            # DOM更新待ち
            wait_links(page, old)

            # -------------------
            # 2ページ目
            # -------------------
            log("📑 2P")

            res2 = extract(page)
            log(res2)

            final = sorted(set(res1 + res2))
            log(f"FINAL: {final}")

        except Exception as e:
            log(f"ERROR: {e}")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
