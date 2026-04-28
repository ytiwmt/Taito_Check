import os
import re
import datetime
import requests
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# =========================
# ログ
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send_discord(msg):
    if not WEBHOOK_URL:
        log(msg)
        return
    requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# 画面安定待ち（重要）
# =========================
def wait_stable(page):
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(800)
    page.wait_for_function(
        "() => document.readyState === 'complete'"
    )
    page.wait_for_timeout(800)


# =========================
# 安定クリック（完全版）
# =========================
def safe_click(page, selector, label):
    log(f"➡ {label}")

    el = page.locator(selector).first

    # DOM存在
    el.wait_for(state="attached", timeout=20000)

    # 表示待ち
    el.wait_for(state="visible", timeout=20000)

    # 画面安定待ち（ここが重要）
    wait_stable(page)

    # スクロール
    el.scroll_into_view_if_needed()

    # クリック
    el.click(timeout=20000)

    # 遷移後安定待ち
    wait_stable(page)


# =========================
# JS遷移
# =========================
def js_postback(page, target):
    log(f"JS POSTBACK: {target}")
    page.evaluate(f"__doPostBack('{target}','')")
    wait_stable(page)


# =========================
# 解析（そのまま）
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
    res = []
    cur = None
    tokens = text.split()

    for i in range(len(tokens) - 1):
        t = tokens[i]
        n = tokens[i + 1]

        if t.isdigit() and 1 <= int(t) <= 12:
            cur = t
            continue

        if t.isdigit() and n in ["○", "△"]:
            if cur:
                res.append(f"{cur}/{t} {n}")

    return res


def analyze(text, results, label):
    if not results:
        log(f"{label}: 🟡 空きなし")
        return "empty"

    log(f"{label}: 🟢 {results}")
    return "ok"


# =========================
# メイン
# =========================
def run_check():
    log("🚀 Playwright v7.2 安定最終寄せ")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = browser.new_page()

        try:
            log(f"🌐 アクセス: {URL}")
            page.goto(URL, wait_until="domcontentloaded")

            wait_stable(page)

            # =========================
            # 遷移
            # =========================
            safe_click(page, "input[name='rbtnYoyaku']", "空き照会メニュー")
            safe_click(page, "input[value='次頁']", "次頁")
            safe_click(page, "input[value='柳北スポーツプラザ']", "施設選択")

            safe_click(page, "input[name='ucPCFooter$btnForward']", "進む")

            # =========================
            # 設定
            # =========================
            safe_click(page, "input[name='rbCalendar'][value='カレンダー']", "カレンダー")
            safe_click(page, "input[name='rbtnMonth'][value='1ヶ月']", "1ヶ月")

            safe_click(page, "input[name='ucPCFooter$btnForward']", "確定")

            wait_stable(page)

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
