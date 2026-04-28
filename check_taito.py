import requests
from playwright.sync_api import sync_playwright
import os
import datetime

VERSION = "v4.3-dom"

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send_discord(msg):
    if not WEBHOOK_URL_Taito:
        log(f"通知なし: {msg}")
        return
    requests.post(WEBHOOK_URL_Taito, json={"content": msg})


# =========================
# DOMベース抽出（核心）
# =========================
def extract_marks(page):
    results = []

    # ○ と △ をDOMから直接取得
    marks = page.locator("text=○, text=△")
    count = marks.count()

    for i in range(count):
        txt = marks.nth(i).inner_text().strip()
        if txt in ["○", "△"]:
            results.append(txt)

    return results


# =========================
# デバッグ判定
# =========================
def classify(body_marks, parsed, label):
    has_data = len(body_marks) > 0

    log(f"===== {label} DEBUG =====")
    log(f"DOM ○/△件数: {len(body_marks)}")

    if not has_data:
        log(f"{label}: ❌ データなし（本当に空）")
        return "no_data"

    if parsed:
        log(f"{label}: 🟢 解析成功")
        return "ok"

    log(f"{label}: ⚠️ DOMありだが解析失敗（異常）")
    return "parse_failed"


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
            classify(marks1, marks1, "1ページ")

            # =========================
            # 次ページ
            # =========================
            log("⏭️ 次の期間")

            page.evaluate("document.getElementById('btnNextPeriod')?.click()")
            page.wait_for_timeout(2000)

            # =========================
            # 2ページ
            # =========================
            log("📑 2ページ目")
            marks2 = extract_marks(page)
            classify(marks2, marks2, "2ページ")

            # =========================
            # 結果
            # =========================
            all_marks = marks1 + marks2
            final = sorted(set(all_marks))

            log(f"📦 FINAL: {final}")

            if final:
                msg = "@everyone\n🏸 柳北スポーツプラザ\n" + "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send_discord(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            log("🔒 終了")
            browser.close()


if __name__ == "__main__":
    run_check()
