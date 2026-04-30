from playwright.sync_api import sync_playwright
import time
import re

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"

def log(msg):
    print(msg, flush=True)

# -----------------------------
# 安定クリック（強制クリック）
# -----------------------------
def safe_click(page, selector, label):
    try:
        page.wait_for_selector(selector, timeout=15000, state="attached")
        page.click(selector, timeout=5000)
        log(f"➡ {label}")
        time.sleep(1)
    except:
        log(f"⚠ {label} click失敗 → JS強制実行")
        page.evaluate(f"""
            const el = document.querySelector("{selector}");
            if (el) el.click();
        """)
        time.sleep(1)

# -----------------------------
# ASP.NET PostBack
# -----------------------------
def postback(page, target):
    page.evaluate(f"""
        __doPostBack('{target}', '');
    """)

# -----------------------------
# ページ解析
# -----------------------------
def parse_page(page):
    cells = page.query_selector_all("a[id*='lnkKoma']")
    result = []

    for c in cells:
        text = c.inner_text().strip()
        m = re.search(r"(\\d+).*?(○|△|×)", text)
        if m:
            result.append(m.group(1) + m.group(2))

    return result

# -----------------------------
# メイン
# -----------------------------
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    log("[START] v7.1-stable")

    page.goto(URL)

    # --- ここが重要：IDベースで辿る ---
    safe_click(page, "#ucPCSideMenuBody_DataListBody_ctl02_ucPCSideMenuItem_dataListItem_ctl00_lnkBtnGoPage", "施設検索")
    safe_click(page, "#ucPCSideMenuBody_DataListBody_ctl03_ucPCSideMenuItem_dataListItem_ctl00_lnkBtnGoPage", "日時選択")

    # 空き照会へ
    page.evaluate("__doPostBack('ucPCSideMenuBody$DataListBody$ctl03$ucPCSideMenuItem$dataListItem$ctl00$lnkBtnGoPage','')")
    time.sleep(2)

    # 確定ボタン
    safe_click(page, "#ucTermSetting_btnForward", "確定")

    # ============================
    # 1ページ目
    # ============================
    log("📑 1ページ目")
    page.wait_for_selector("a[id*='lnkKoma']", timeout=15000)

    page1 = parse_page(page)
    log(f"1P: {page1}")

    # ============================
    # 次ページ（重要）
    # ============================
    log("⏭️ 次ページ")

    prev_html = page.content()

    postback(page, "dlRepeat2$ctl00$tpItem2$Migrated_lnkNextSpan")

    # DOM変化待ち
    for _ in range(20):
        time.sleep(0.5)
        if page.content() != prev_html:
            break

    # ============================
    # 2ページ目
    # ============================
    log("📑 2ページ目")

    try:
        page.wait_for_selector("form#Form1", timeout=5000)
    except:
        pass

    page2 = parse_page(page)
    log(f"2P: {page2}")

    browser.close()
