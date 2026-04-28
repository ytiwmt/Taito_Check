import os
import re
import datetime
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send_discord(msg):
    if not WEBHOOK_URL:
        log(msg)
        return
    requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# 安定クリック（最重要修正）
# =========================
def safe_click(page, selector, label, timeout=15000):
    try:
        log(f"➡ {label}")

        el = page.locator(selector).first

        # 表示待ち
        el.wait_for(state="visible", timeout=timeout)

        # 安定化待機（JSバインド待ち）
        page.wait_for_timeout(600)

        # スクロール
        el.scroll_into_view_if_needed()

        # クリック
        el.click(timeout=timeout)

        # 反映待ち（これ重要）
        page.wait_for_timeout(1200)

    except PWTimeout:
        raise Exception(f"クリック失敗: {label}")


# =========================
# JS遷移（次ページ安定化）
# =========================
def js_postback(page, target):
    log(f"JS POSTBACK: {target}")
    page.evaluate(f"__doPostBack('{target}','')")
    page.wait_for_timeout(1500)


# =========================
# 解析ロジック
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


def analyze(text, results, label):
    if "不正な遷移" in text:
        log(f"{label}: ❌ エラー")
        return "error"

    if not results:
        log(f"{label}: 🟡 空きなし")
        return "empty"

    log(f"{label}: 🟢 {results}")
    return "ok"


# =========================
# メイン
# =========================
def run_check():
    log("🚀 Playwright v7.1 安定版")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = browser.new_page()

        try:
            log(f"🌐 アクセス: {URL}")
            page.goto(URL, wait_until="domcontentloaded")

            page.wait_for_timeout(1000)

            # -------------------------
            # 遷移（安定クリック）
            # -------------------------
            safe_click(page, "input[name='rbtnYoyaku']", "空き照会メニュー")
            safe_click(page, "input[value='次頁']", "次頁")
            safe_click(page, "input[value='柳北スポーツプラザ']", "施設選択")

            safe_click(page, "input[name='ucPCFooter$btnForward']", "進む")

            # -------------------------
            # カレンダー設定
            # -------------------------
            safe_click(page, "input[name='rbCalendar'][value='カレンダー']", "カレンダー")
            safe_click(page, "input[name='rbtnMonth'][value='1ヶ月']", "1ヶ月")

            safe_click(page, "input[name='ucPCFooter$btnForward']", "確定")

            page.wait_for_timeout(1500)

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ")
            body1 = page.inner_text("body")
            res1 = parse(extract_gym(body1))
            analyze(body1, res1, "1ページ")

            # =========================
            # 次ページ
            # =========================
            js_postback(page, "btnNextPeriod")

            log("📑 2ページ")
            body2 = page.inner_text("body")
            res2 = parse(extract_gym(body2))
            analyze(body2, res2, "2ページ")

            # =========================
            # 結果
            # =========================
            final = sorted(set(res1 + res2))
            log(f"📦 FINAL: {final}")

            send_discord(
                "@everyone\n🏸 柳北スポーツプラザ\n" +
                ("\n".join(final) if final else "空きなし")
            )

        except Exception as e:
            log(f"🔥 エラー: {e}")

        finally:
            log("🔒 終了")
            browser.close()


if __name__ == "__main__":
    run_check()
