import requests
from playwright.sync_api import sync_playwright
import os
import datetime

VERSION = "v4.6-dom-sync"

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


# =========================
# ログ
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send_discord(msg):
    if not WEBHOOK_URL_Taito:
        log(f"通知なし: {msg}")
        return
    requests.post(WEBHOOK_URL_Taito, json={"content": msg})


# =========================
# ○△抽出（安定）
# =========================
def extract_marks(page):
    results = []

    for el in page.locator("a").all():
        text = el.inner_text().strip()

        if "○" in text:
            results.append("○")
        if "△" in text:
            results.append("△")

    return results


# =========================
# ★最重要：DOM差し替え待ち
# =========================
def wait_next_period(page):
    # table領域で差し替え監視（最も安定）
    old = page.locator("table").first.inner_html()

    page.evaluate("document.getElementById('btnNextPeriod')?.click()")

    try:
        page.wait_for_function(
            "old => document.querySelector('table')?.innerHTML !== old",
            old,
            timeout=15000
        )
        log("✅ 次ページ更新確認（table差し替え）")
    except Exception:
        log("⚠️ 更新未検知（続行）")


# =========================
# 安全クリック
# =========================
def click(page, selector, label):
    el = page.locator(selector).first
    el.wait_for(state="attached", timeout=20000)
    el.click()
    page.wait_for_timeout(1200)
    log(f"➡ {label}")


# =========================
# メイン
# =========================
def run_check():
    with sync_playwright() as p:
        log(f"🚀 Playwright {VERSION}")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            log(f"🔗 アクセス: {BASE_URL}")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # -------------------------
            # 遷移
            # -------------------------
            click(page, "input[value='公共施設予約メニュー']", "公共施設予約メニュー")
            click(page, "input[name='rbtnYoyaku']", "空き照会")
            click(page, "input[value='次頁']", "次頁")
            click(page, "input[value='柳北スポーツプラザ']", "施設")

            click(page, "input[name='ucPCFooter$btnForward']", "進む")
            click(page, "input[name='rbCalendar'][value='カレンダー']", "カレンダー")
            click(page, "input[name='rbtnMonth'][value='1ヶ月']", "1ヶ月")
            click(page, "input[name='ucPCFooter$btnForward']", "確定")

            page.wait_for_timeout(1500)

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ目")
            marks1 = extract_marks(page)
            log(f"1ページ: {marks1}")

            # =========================
            # 2ページ
            # =========================
            log("⏭️ 次の期間")
            wait_next_period(page)

            page.wait_for_timeout(1000)

            log("📑 2ページ目")
            marks2 = extract_marks(page)
            log(f"2ページ: {marks2}")

            # =========================
            # 結果
            # =========================
            final = sorted(set(marks1 + marks2))
            log(f"📦 FINAL: {final}")

            msg = "@everyone\n🏸 柳北スポーツプラザ\n" + ("\n".join(final) if final else "空きなし")
            send_discord(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            log("🔒 終了")
            browser.close()


if __name__ == "__main__":
    run_check()
