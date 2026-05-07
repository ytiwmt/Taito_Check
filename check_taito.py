import os
import re
import time
import requests
from playwright.sync_api import sync_playwright

VERSION = "v9.2-dom-change-safe"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# --------------------
# log
# --------------------
def log(msg):
    print(msg)


def send(msg):
    log("\n=== SEND ===")
    log(msg)

    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": msg})
        except:
            pass


# --------------------
# click helper
# --------------------
def click(page, selector):
    el = page.locator(selector).first
    el.wait_for(state="visible", timeout=20000)
    el.scroll_into_view_if_needed()
    el.click()
    page.wait_for_timeout(1000)


# --------------------
# extract
# --------------------
def extract(page):
    links = page.locator("a[id*='lnkKoma']").all()
    result = []

    for l in links:
        try:
            t = l.inner_text().replace("\xa0", "").strip()
        except:
            continue

        m = re.search(r"(\d+)(○|△|×|抽選)", t)
        if m:
            result.append(f"{m.group(1)}{m.group(2)}")

    return result


# --------------------
# 初期導線
# --------------------
def goto_calendar(page):

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    click(page, "input[value='公共施設予約メニュー']")
    click(page, "input[value*='空き照会']")
    click(page, "input[value='次頁']")
    click(page, "input[value*='柳北']")

    click(page, "input[name='ucPCFooter$btnForward']")
    click(page, "input[value='カレンダー']")
    click(page, "input[value='1ヶ月']")
    click(page, "input[name='ucPCFooter$btnForward']")

    page.wait_for_selector("a[id*='lnkKoma']", timeout=20000)


# --------------------
# 月遷移（ここが核心）
# --------------------
def next_month(page):

    log("⏭️ btnNextPeriod click")

    before = page.content()

    page.locator("#btnNextPeriod").click()

    # ★ここが重要（DOM差分待ち）
    page.wait_for_function(
        """prev => document.body.innerHTML !== prev""",
        arg=before,
        timeout=20000
    )

    # 追加安定待ち
    page.wait_for_timeout(1500)


# --------------------
# main
# --------------------
def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # =====================
            # 初期セット
            # =====================
            goto_calendar(page)

            # =====================
            # CURRENT
            # =====================
            current = extract(page)
            log(f"[CURRENT] {len(current)}件")

            # =====================
            # NEXT MONTH
            # =====================
            next_month(page)

            next_data = extract(page)
            log(f"[NEXT] {len(next_data)}件")

            # =====================
            # 結果
            # =====================
            final = sorted(set(current + next_data))

            log(f"FINAL: {final}")

            if final:
                msg = "@everyone\n🏸 柳北スポーツプラザ 空き情報\n" + "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send(msg)

        except Exception as e:
            log(f"ERROR: {e}")
            page.screenshot(path="error.png", full_page=True)

        finally:
            browser.close()


if __name__ == "__main__":
    run()
