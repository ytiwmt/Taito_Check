import requests
import os
import re
import time
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

VERSION = "v8.1-next-period-stable"


# =====================================
# utility
# =====================================

def log(msg):
    print(msg, flush=True)


def send_discord(msg):
    print("\n=== SEND ===")
    print(msg)

    if not WEBHOOK_URL:
        return

    try:
        requests.post(
            WEBHOOK_URL,
            json={"content": msg},
            timeout=20
        )
    except Exception as e:
        print(e)


# =====================================
# parse
# =====================================

def parse_links(page, label):
    results = []

    links = page.locator("a[id*='lnkKoma']").all()

    log(f"[{label}] link数: {len(links)}")

    for link in links:
        try:
            txt = (
                link.inner_text()
                .replace("\xa0", "")
                .replace(" ", "")
                .strip()
            )

            m = re.search(r"(\d+)(○|△|×|抽選)", txt)

            if m:
                results.append(
                    f"{m.group(1)}{m.group(2)}"
                )

        except:
            pass

    log(f"[{label}] 件数: {len(results)}")

    return results


# =====================================
# navigation
# =====================================

def open_calendar(page):
    """
    柳北スポーツプラザ → カレンダー → 1ヶ月
    """

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # 公共施設予約メニュー
    page.locator(
        "input[value='公共施設予約メニュー']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 空き照会
    page.locator(
        "input[value*='空き照会']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 次頁
    page.locator(
        "input[value='次頁']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)

    # 柳北
    page.locator(
        "input[value*='柳北']"
    ).first.wait_for(timeout=30000)

    page.locator(
        "input[value*='柳北']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # カレンダー
    page.locator(
        "input[value='カレンダー']"
    ).first.click()

    page.wait_for_timeout(1000)

    # 1ヶ月
    page.locator(
        "input[value='1ヶ月']"
    ).first.click()

    page.wait_for_timeout(1000)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)

    # 体育館ページ確認
    page.wait_for_selector(
        "a[id*='lnkKoma']",
        timeout=30000
    )


def go_next_period(page):
    """
    次の期間を表示 >
    """

    log("⏭️ btnNextPeriod click")

    before = page.locator(
        "a[id*='lnkKoma']"
    ).count()

    log(f"before links: {before}")

    page.locator(
        "#btnNextPeriod"
    ).click(force=True)

    # ASP.NET が重いのでかなり待つ
    page.wait_for_timeout(8000)

    try:
        page.wait_for_selector(
            "a[id*='lnkKoma']",
            timeout=15000
        )
    except:
        pass

    after = page.locator(
        "a[id*='lnkKoma']"
    ).count()

    log(f"after links: {after}")

    body = page.inner_text("body")[:500]

    log("=== BODY HEAD ===")
    log(body)

    return after > 0


# =====================================
# main
# =====================================

def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        context = browser.new_context(
            viewport={
                "width": 1400,
                "height": 1200
            }
        )

        page = context.new_page()

        final = []

        try:

            # =================================
            # CURRENT
            # =================================

            log("=== CURRENT ===")

            open_calendar(page)

            current = parse_links(
                page,
                "CURRENT"
            )

            final.extend(current)

            # =================================
            # NEXT
            # =================================

            log("=== NEXT ===")

            ok = go_next_period(page)

            if ok:

                next_data = parse_links(
                    page,
                    "NEXT"
                )

                final.extend(next_data)

            else:
                log("❌ 次ページ取得失敗")

            # =================================
            # FINAL
            # =================================

            final = sorted(
                list(set(final)),
                key=lambda x: int(
                    re.sub(r"\D", "", x)
                )
            )

            log(f"FINAL: {final}")

            if final:

                msg = (
                    "@everyone\n"
                    "🏸 柳北スポーツプラザ 空き情報\n"
                    + "\n".join(final)
                )

            else:
                msg = "空きなし"

            send_discord(msg)

        except Exception as e:

            log(f"ERROR: {e}")

            try:
                page.screenshot(
                    path="debug.png",
                    full_page=True
                )
            except:
                pass

            send_discord(
                f"⚠️ ERROR\n{e}"
            )

        finally:
            browser.close()


if __name__ == "__main__":
    run()
