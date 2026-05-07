import requests
import os
import re
import datetime
from playwright.sync_api import sync_playwright

VERSION = "v8-fixed-restart-model"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


def send(msg):
    log("送信内容:\n" + msg)
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# -----------------------
# 抽出（固定）
# -----------------------
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


# -----------------------
# 1回の完全フロー
# -----------------------
def run_cycle(page, label):

    log(f"=== {label} ===")

    page.goto(BASE_URL)
    page.wait_for_timeout(2000)

    page.locator("input[value='公共施設予約メニュー']").click()
    page.locator("input[value^='空き照会']").click()
    page.locator("input[value='次頁']").click()

    page.locator("input[value*='柳北']").first.click()

    page.locator("input[name='ucPCFooter$btnForward']").click()

    page.locator("input[value='カレンダー']").click()
    page.locator("input[value='1ヶ月']").click()

    page.locator("input[name='ucPCFooter$btnForward']").click()

    page.wait_for_timeout(3000)

    page.wait_for_selector("a[id*='lnkKoma']", timeout=20000)

    data = extract(page)

    log(f"[{label}] 件数: {len(data)}")

    return data


# -----------------------
# メイン
# -----------------------
def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1回目（現在月）
            data1 = run_cycle(page, "CURRENT")

            # 2回目（重要：完全再アクセス）
            data2 = run_cycle(page, "NEXT_MONTH")

            final = sorted(set(data1 + data2))

            log(f"FINAL: {final}")

            if final:
                msg = "@everyone\n🏸 空きあり\n" + "\n".join(final)
            else:
                msg = "空きなし"

            send(msg)

        except Exception as e:
            log(f"ERROR: {e}")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
