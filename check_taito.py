import os
import re
import datetime
import requests
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

START_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


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
# UI安定待ち（本質）
# =========================
def wait_ui(page, selector):
    page.wait_for_function(
        """(sel) => {
            const el = document.querySelector(sel);
            return el && el.offsetParent !== null;
        }""",
        selector,
        timeout=30000
    )


# =========================
# 安定クリック
# =========================
def click(page, selector, label):
    log(f"➡ {label}")

    wait_ui(page, selector)

    el = page.locator(selector).first
    el.scroll_into_view_if_needed()
    el.click()

    page.wait_for_timeout(1200)


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


# =========================
# メイン
# =========================
def run_check():
    log("🚀 Playwright v8.2（UI特化安定版）")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = browser.new_page()

        try:
            # =========================
            # 入口
            # =========================
            log(f"🌐 入口: {START_URL}")
            page.goto(START_URL, wait_until="domcontentloaded")

            page.wait_for_timeout(2000)

            # ★ hidden完全無視でUIだけ待つ
            wait_ui(page, "input[value='公共施設予約メニュー']")

            # =========================
            # 遷移
            # =========================
            click(page, "input[name='rbtnYoyaku']", "空き照会メニュー")
            click(page, "input[value='次頁']", "次頁")
            click(page, "input[value='柳北スポーツプラザ']", "施設選択")

            click(page, "input[name='ucPCFooter$btnForward']", "進む")

            # =========================
            # 設定
            # =========================
            click(page, "input[name='rbCalendar'][value='カレンダー']", "カレンダー")
            click(page, "input[name='rbtnMonth'][value='1ヶ月']", "1ヶ月")

            click(page, "input[name='ucPCFooter$btnForward']", "確定")

            page.wait_for_timeout(1500)

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ")
            body1 = page.inner_text("body")
            res1 = parse(extract_gym(body1))
            log(f"1ページ: {res1}")

            # =========================
            # 次ページ
            # =========================
            page.evaluate("__doPostBack('btnNextPeriod','')")
            page.wait_for_timeout(2000)

            # =========================
            # 2ページ
            # =========================
            log("📑 2ページ")
            body2 = page.inner_text("body")
            res2 = parse(extract_gym(body2))
            log(f"2ページ: {res2}")

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
