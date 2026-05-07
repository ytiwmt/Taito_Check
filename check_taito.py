import os
import re
import time
import requests
from playwright.sync_api import sync_playwright

VERSION = "v9.0-stable-reset"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# ----------------------
# log
# ----------------------
def log(msg):
    print(msg)


def send(msg):
    log("\n=== SEND ===")
    log(msg)

    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# ----------------------
# 安定クリック
# ----------------------
def click(page, selector, timeout=15000):
    el = page.locator(selector).first
    el.wait_for(state="visible", timeout=timeout)
    el.scroll_into_view_if_needed()
    el.click()
    page.wait_for_timeout(1200)


# ----------------------
# 初期化（重要）
# ----------------------
def goto_start(page):
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)


# ----------------------
# 抽出ロジック
# ----------------------
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


# ----------------------
# 1回フロー（完全再構築）
# ----------------------
def run_cycle(page, label):

    log(f"\n=== {label} ===")

    goto_start(page)

    # メニュー遷移
    click(page, "input[value='公共施設予約メニュー']")
    click(page, "input[value*='空き照会']")
    click(page, "input[value='次頁']")

    # 施設
    click(page, "input[value*='柳北']")

    # カレンダー設定
    click(page, "input[name='ucPCFooter$btnForward']")
    click(page, "input[value='カレンダー']")
    click(page, "input[value='1ヶ月']")
    click(page, "input[name='ucPCFooter$btnForward']")

    # 画面安定待ち
    page.wait_for_timeout(3000)

    # 表示確認
    page.wait_for_selector("a[id*='lnkKoma']", timeout=20000)

    data = extract(page)

    log(f"[{label}] 件数: {len(data)}")

    return data


# ----------------------
# メイン
# ----------------------
def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # 1回目（現在月）
            data1 = run_cycle(page, "CURRENT")

            # 2回目（完全リセットして再取得）
            data2 = run_cycle(page, "NEXT_MONTH")

            # 統合
            final = sorted(set(data1 + data2))

            log(f"\nFINAL: {final}")

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
