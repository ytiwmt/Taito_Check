from playwright.sync_api import sync_playwright
import re
import time

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def parse_page(page, label):
    result = []

    # ---------------------------
    # ① hidden inputから取得（本命）
    # ---------------------------
    hidden = page.eval_on_selector_all(
        "input[id*='lnkKoma']",
        "els => els.map(e => e.value)"
    )

    for v in hidden:
        if not v:
            continue
        text = v.replace("&nbsp;", "").strip()

        # 例: "28  ×"
        m = re.match(r"(\\d+)\\s*([○△×])", text)
        if m:
            result.append(f"{m.group(1)}{m.group(2)}")

    # ---------------------------
    # ② aタグ（○△だけ補完）
    # ---------------------------
    links = page.eval_on_selector_all(
        "a[id*='lnkKoma']",
        "els => els.map(e => e.innerText)"
    )

    for t in links:
        m = re.match(r"(\\d+).*([○△])", t)
        if m:
            result.append(f"{m.group(1)}{m.group(2)}")

    # 重複除去
    result = sorted(set(result), key=lambda x: (int(re.match(r"\\d+", x).group()), x))

    # ステータス判定
    if not hidden:
        status = "PARSE_FAILED"
    elif any("○" in x or "△" in x for x in result):
        status = "AVAILABLE"
    else:
        status = "FULL"

    log(f"{label}: {result}")
    log(f"{label}: {status}")

    return result, status


def goto_next(page):
    log("⏭️ 次ページ")

    # ASP.NET postback直接叩く
    target = page.eval_on_selector(
        "input[id*='lnkNextSpan']",
        "el => el.id.replace('h_', '')"
    )

    log(f"➡ POSTBACK TARGET: {target}")

    page.evaluate(f"__doPostBack('{target}', '')")

    # 更新待ち
    page.wait_for_timeout(1500)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    log("🚀 v6.3-hidden-final")
    page.goto(URL)

    # 遷移操作（省略せず確実に）
    page.click("text=公共施設予約メニュー")
    page.click("text=空き照会")
    page.click("text=次頁")
    page.click("text=施設")
    page.click("text=進む")
    page.click("text=カレンダー")
    page.click("text=1ヶ月")
    page.click("text=確定")

    page.wait_for_timeout(2000)

    log("📑 1ページ目")
    r1, s1 = parse_page(page, "1P")

    goto_next(page)

    log("📑 2ページ目")
    r2, s2 = parse_page(page, "2P")

    final = sorted(set(r1 + r2))
    log(f"📦 FINAL: {final}")

    browser.close()
    log("🔒 END")
