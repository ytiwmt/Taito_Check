import os
import re
import time
import datetime
import requests
from playwright.sync_api import sync_playwright

VERSION = "state-machine-v1"

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"
WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")


# -----------------------
# log
# -----------------------
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# -----------------------
# 抽出（リンクベース）
# -----------------------
def extract(page):
    results = []

    for el in page.locator("a").all():
        try:
            text = el.inner_text().strip()
            m = re.search(r'(\d{1,2}).*(○|△|×)', text)
            if m:
                results.append(f"{m.group(1)}{m.group(2)}")
        except:
            continue

    return results


# -----------------------
# 状態判定
# -----------------------
def classify(results):
    if results is None:
        return "PARSE_FAILED"

    if len(results) == 0:
        return "PARSE_FAILED"

    ok = any("○" in r or "△" in r for r in results)
    ng = any("×" in r for r in results)

    if ok:
        return "AVAILABLE"

    if ng and not ok:
        return "EMPTY_OK"

    return "PARSE_FAILED"


# -----------------------
# DOM変化待ち（核心）
# -----------------------
def wait_dom_change(page, old, timeout=10000):
    try:
        page.wait_for_function(
            """(old) => {
                const now = Array.from(document.querySelectorAll('a'))
                    .map(e => e.innerText);
                return JSON.stringify(now) !== JSON.stringify(old);
            }""",
            old,
            timeout=timeout
        )
        return True
    except:
        return False


# -----------------------
# 安全クリック
# -----------------------
def safe_click(page, selector):
    for i in range(3):
        try:
            page.click(selector)
            return True
        except:
            time.sleep(0.5)
    return False


# -----------------------
# メイン
# -----------------------
def run():
    with sync_playwright() as p:
        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(URL)
            page.wait_for_url("**Wg_ModeSelect.aspx**")

            # -------------------
            # 画面遷移
            # -------------------
            safe_click(page, "input[value='公共施設予約メニュー']")
            safe_click(page, "input[value^='1. 空き照会']")
            safe_click(page, "input[value='次頁']")
            safe_click(page, "input[value='柳北スポーツプラザ']")
            safe_click(page, "input[name='ucPCFooter$btnForward']")

            safe_click(page, "input[name='rbCalendar'][value='カレンダー']")
            safe_click(page, "input[name='rbtnMonth'][value='1ヶ月']")
            safe_click(page, "input[name='ucPCFooter$btnForward']")

            # -------------------
            # 1ページ目
            # -------------------
            log("📑 1ページ目")

            res1 = extract(page)
            log(f"1P: {res1}")
            status1 = classify(res1)
            log(f"1P STATUS: {status1}")

            # スナップショット
            old = page.locator("a").all_inner_texts()

            # -------------------
            # 次ページ
            # -------------------
            log("⏭️ 次ページ")

            page.evaluate("""
                document.getElementById('btnNextPeriod').click()
            """)

            # ★ここが核心（DOM変化待ち）
            ok = wait_dom_change(page, old)

            if not ok:
                log("⚠️ 更新検知失敗 → 再試行")

                for retry in range(2):
                    page.evaluate("""
                        document.getElementById('btnNextPeriod').click()
                    """)
                    if wait_dom_change(page, old, timeout=5000):
                        break

            # -------------------
            # 2ページ目
            # -------------------
            log("📑 2ページ目")

            res2 = extract(page)
            log(f"2P: {res2}")

            status2 = classify(res2)
            log(f"2P STATUS: {status2}")

            # -------------------
            # 結果統合
            # -------------------
            final = sorted(set(res1 + res2))

            log(f"📦 FINAL: {final}")

            if final:
                send("🏸 空きあり\n" + "\n".join(final))
            else:
                send("空きなし")

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
