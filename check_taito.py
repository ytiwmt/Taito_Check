from playwright.sync_api import sync_playwright
import re
import time

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

# -----------------------------
# 安定クリック
# -----------------------------
def safe_click(page, selector, name):
    page.wait_for_selector(selector, timeout=10000)
    page.click(selector)
    log(f"➡ {name}")
    page.wait_for_timeout(800)

# -----------------------------
# パース（hidden主体）
# -----------------------------
def parse_page(page, label):
    result = []

    # hidden（完全データ）
    hidden = page.eval_on_selector_all(
        "input[id*='lnkKoma']",
        "els => els.map(e => e.value)"
    )

    for v in hidden:
        if not v:
            continue
        text = v.replace("&nbsp;", "").strip()
        m = re.match(r"(\\d+)\\s*([○△×])", text)
        if m:
            result.append(f"{m.group(1)}{m.group(2)}")

    # aタグ（○△補助）
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

# -----------------------------
# 次ページ（postback直叩き）
# -----------------------------
def goto_next(page):
    log("⏭️ 次ページ")

    target = page.eval_on_selector(
        "input[id*='lnkNextSpan']",
        "el => el.id.replace('h_', '')"
    )

    if not target:
        log("⚠️ 次ページリンクなし")
        return False

    log(f"➡ POSTBACK TARGET: {target}")

    page.evaluate(f"__doPostBack('{target}', '')")

    # DOM更新待ち（重要）
    page.wait_for_timeout(2000)
    return True


# =============================
# メイン
# =============================
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    log("🚀 v7.0-stable")

    page.goto(URL)

    # -------------------------
    # 遷移（完全安定版）
    # -------------------------
    safe_click(page, "a:has-text('公共施設予約メニュー')", "公共施設予約メニュー")
    safe_click(page, "a:has-text('空き照会')", "空き照会")
    safe_click(page, "a:has-text('次頁')", "次頁")
    safe_click(page, "a:has-text('施設')", "施設")
    safe_click(page, "a:has-text('進む')", "進む")
    safe_click(page, "a:has-text('カレンダー')", "カレンダー")
    safe_click(page, "a:has-text('1ヶ月')", "1ヶ月")

    page.wait_for_selector("input[value='確定']")
    page.click("input[value='確定']")
    log("➡ 確定")

    page.wait_for_timeout(2000)

    # -------------------------
    # 1ページ目
    # -------------------------
    log("📑 1ページ目")
    r1, s1 = parse_page(page, "1P")

    # -------------------------
    # 2ページ目
    # -------------------------
    if goto_next(page):
        log("📑 2ページ目")
        r2, s2 = parse_page(page, "2P")
    else:
        r2, s2 = [], "NO_NEXT"

    # -------------------------
    # 結果
    # -------------------------
    final = sorted(set(r1 + r2))
    log(f"📦 FINAL: {final}")

    browser.close()
    log("🔒 END")
