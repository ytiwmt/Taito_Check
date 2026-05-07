import os
import re
import requests
from playwright.sync_api import sync_playwright

VERSION = "v9.1-month-state-fixed"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# -------------------
# log
# -------------------
def log(msg):
    print(msg)


def send(msg):
    log("\n=== SEND ===")
    log(msg)
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# -------------------
# 共通クリック
# -------------------
def click(page, selector):
    el = page.locator(selector).first
    el.wait_for(state="visible", timeout=20000)
    el.scroll_into_view_if_needed()
    el.click()
    page.wait_for_timeout(1200)


# -------------------
# 抽出
# -------------------
def extract(page):
    links = page.locator("a[id*='lnkKoma']").all()
    res = []

    for l in links:
        try:
            t = l.inner_text().replace("\xa0", "").strip()
        except:
            continue

        m = re.search(r"(\d+)(○|△|×|抽選)", t)
        if m:
            res.append(f"{m.group(1)}{m.group(2)}")

    return res


# -------------------
# 初期導線
# -------------------
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


# -------------------
# メイン
# -------------------
def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # =========================
            # 初期化
            # =========================
            goto_calendar(page)

            # =========================
            # CURRENT
            # =========================
            current = extract(page)
            log(f"[CURRENT] {len(current)}件")

            # =========================
            # NEXT MONTH（ここが本体）
            # =========================
            log("⏭️ btnNextPeriod click")

            btn = page.locator("#btnNextPeriod")

            btn.wait_for(state="visible", timeout=20000)
            btn.click()

            # 重要：完全再描画待ち
            page.wait_for_timeout(3000)
            page.wait_for_selector("a[id*='lnkKoma']", timeout=20000)

            next_month = extract(page)
            log(f"[NEXT] {len(next_month)}件")

            # =========================
            # 統合
            # =========================
            final = sorted(set(current + next_month))

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
