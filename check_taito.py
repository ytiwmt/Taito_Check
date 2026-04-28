import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v4.2-debug"

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
# 解析
# =========================
def extract_gym(text):
    if "体育館" not in text:
        return ""
    part = text.split("体育館", 1)[1]
    if "庭球場" in part:
        part = part.split("庭球場", 1)[0]
    return part


def parse(text):
    text = re.sub(r"\s+", " ", text)
    results = []
    current_month = None
    tokens = text.split()

    for i in range(len(tokens) - 1):
        t = tokens[i]
        n = tokens[i + 1]

        if t.isdigit() and 1 <= int(t) <= 12:
            current_month = t
            continue

        if t.isdigit() and n in ["○", "△"]:
            if current_month:
                results.append(f"{current_month}/{t} {n}")

    return results


# =========================
# デバッグ判定（重要）
# =========================
def debug_classify(body, parsed, label):
    has_ok = "○" in body
    has_mid = "△" in body
    has_num = any(str(i) in body for i in range(1, 32))

    log(f"===== {label} DEBUG =====")
    log(f"○: {has_ok} / △: {has_mid} / 日付: {has_num}")

    if not has_ok and not has_mid:
        log(f"{label}: ❌ 完全に空（データなし）")
        return "no_data"

    if parsed:
        log(f"{label}: 🟢 解析成功")
        return "ok"

    log(f"{label}: ⚠️ データあるが解析失敗")
    return "parse_failed"


# =========================
# 安全クリック
# =========================
def click(page, selector, label):
    try:
        el = page.locator(selector).first
        el.wait_for(state="attached", timeout=20000)
        el.click()
        page.wait_for_timeout(1200)
        log(f"➡ {label}")
    except Exception as e:
        log(f"❌ クリック失敗 {label}: {e}")
        raise


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
            body1 = page.inner_text("body")
            gym1 = extract_gym(body1)
            res1 = parse(gym1)

            status1 = debug_classify(body1, res1, "1ページ")

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
            body2 = page.inner_text("body")
            gym2 = extract_gym(body2)
            res2 = parse(gym2)

            status2 = debug_classify(body2, res2, "2ページ")

            # =========================
            # 結果統合
            # =========================
            all_results = res1 + res2
            final = sorted(set(all_results))

            log(f"📦 FINAL: {final}")

            if final:
                msg = "@everyone\n🏸 柳北スポーツプラザ\n"
                msg += "\n".join([f"🔴 {x}" for x in final])
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
