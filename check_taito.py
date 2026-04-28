import os
import re
import datetime
import requests
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


# =========================
# log
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# 安定クリック（これが核）
# =========================
def click(page, selector, label):
    log(f"➡ {label}")

    el = page.locator(selector)

    # ★ visibleだけ対象（hidden完全排除）
    el = el.filter(has_not=page.locator("[type='hidden']"))

    el.first.wait_for(state="visible", timeout=30000)
    el.first.click()

    page.wait_for_timeout(1200)


# =========================
# 解析
# =========================
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
def run():
    log("🚀 Playwright v9.0（簡素安定版）")

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
            log(f"🌐 {URL}")
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # ★重要：visibleだけで判定
            page.wait_for_selector(
                "input[value='公共施設予約メニュー']",
                state="visible",
                timeout=30000
            )

            # =========================
            # 遷移（固定パス）
            # =========================
            click(page, "input[name='rbtnYoyaku']", "空き照会")
            click(page, "input[value='次頁']", "次頁")
            click(page, "input[value='柳北スポーツプラザ']", "施設")

            click(page, "input[name='ucPCFooter$btnForward']", "進む")

            # =========================
            # 設定
            # =========================
            click(page, "input[name='rbCalendar'][value='カレンダー']", "カレンダー")
            click(page, "input[name='rbtnMonth'][value='1ヶ月']", "1ヶ月")

            click(page, "input[name='ucPCFooter$btnForward']", "確定")

            page.wait_for_timeout(1500)

            # =========================
            # 取得
            # =========================
            body = page.inner_text("body")
            result = parse(body)

            log(f"📦 RESULT: {result}")

            send("🏸 柳北スポーツプラザ\n" + ("\n".join(result) if result else "空きなし"))

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            browser.close()
            log("🔒 終了")


if __name__ == "__main__":
    run()
