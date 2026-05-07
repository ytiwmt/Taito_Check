import requests
import os
import re
import datetime
from playwright.sync_api import sync_playwright

VERSION = "v7.35-request-debug"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# =========================
# LOG
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    log(f"送信内容:\n{msg}")

    if WEBHOOK_URL:
        try:
            requests.post(
                WEBHOOK_URL,
                json={"content": msg},
                timeout=10
            )
        except Exception as e:
            log(f"❌ Webhook失敗: {e}")


# =========================
# REQUEST DEBUG
# =========================
def setup_request_debug(page):

    def on_request(req):
        try:
            print("\n================ REQUEST ================")
            print("METHOD:", req.method)
            print("URL:", req.url)

            if req.post_data:
                print("POST DATA:")
                print(req.post_data[:5000])

        except Exception as e:
            print("REQUEST DEBUG ERROR:", e)

    page.on("request", on_request)


# =========================
# PARSE
# =========================
def parse(page, label):

    results = []

    links = page.locator("a[id*='lnkKoma']").all()

    log(f"[{label}] link数: {len(links)}")

    for l in links:

        try:
            txt = l.inner_text()

            txt = txt.replace("\xa0", "")
            txt = txt.replace(" ", "")
            txt = txt.strip()

        except:
            continue

        m = re.search(r"(\d+)(○|△|×|抽選)", txt)

        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    log(f"[{label}] 抽出件数: {len(results)}")

    return results


def analyze(results, label):

    ok = [x for x in results if "○" in x or "△" in x]
    lot = [x for x in results if "抽選" in x]
    ng = [x for x in results if "×" in x]

    log(f"{label}: ○△={len(ok)} / 抽選={len(lot)} / ×={len(ng)}")


# =========================
# hidden field dump
# =========================
def dump_hidden(page, title):

    print(f"\n========== HIDDEN DUMP : {title} ==========")

    hidden = page.locator("input[type='hidden']").all()

    for h in hidden:

        try:
            name = h.get_attribute("name")
            value = h.get_attribute("value")

            if value:
                value = value[:300]

            print(name, "=", value)

        except:
            pass


# =========================
# 共通遷移
# =========================
def move_to_calendar(page):

    page.goto(BASE_URL)

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)

    # 公共施設予約メニュー
    page.locator(
        "input[type='submit']",
        has_text="公共施設予約メニュー"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 空き照会
    page.locator(
        "input[type='submit']",
        has_text="空き照会"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次頁
    page.locator(
        "input[type='submit']",
        has_text="次頁"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 柳北
    page.locator(
        "input[type='submit']",
        has_text="柳北"
    ).first.wait_for(timeout=30000)

    page.locator(
        "input[type='submit']",
        has_text="柳北"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # カレンダー
    page.locator(
        "input[type='submit']",
        has_text="カレンダー"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 1ヶ月
    page.locator(
        "input[type='submit']",
        has_text="1ヶ月"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)


# =========================
# 次ページ
# =========================
def move_next_period(page):

    log("⏭️ 次ページ（通信解析モード）")

    dump_hidden(page, "BEFORE CLICK")

    before_body = page.locator("body").inner_text()[:500]

    try:

        btn = page.locator("#btnNextPeriod")

        btn.wait_for(timeout=10000)

        log("btnNextPeriod click 実行")

        btn.click()

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        dump_hidden(page, "AFTER CLICK")

        after_body = page.locator("body").inner_text()[:500]

        print("\n========== BODY BEFORE ==========")
        print(before_body)

        print("\n========== BODY AFTER ==========")
        print(after_body)

        if "お探しのページを表示できません" in after_body:
            log("❌ 不正遷移ページ")
            return False

        return True

    except Exception as e:

        log(f"❌ 遷移例外: {e}")
        return False


# =========================
# MAIN
# =========================
def run():

    with sync_playwright() as p:

        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1280,
                "height": 800
            }
        )

        page = context.new_page()

        setup_request_debug(page)

        final = []

        try:

            # =====================================
            # 1ページ目
            # =====================================
            move_to_calendar(page)

            dump_hidden(page, "1PAGE")

            log("📑 1ページ目")

            res1 = parse(page, "1P")

            log(f"1P: {res1}")

            analyze(res1, "1P")

            final.extend(res1)

            # =====================================
            # 次ページ
            # =====================================
            ok = move_next_period(page)

            if ok:

                log("📑 2ページ目")

                res2 = parse(page, "2P")

                log(f"2P: {res2}")

                analyze(res2, "2P")

                final.extend(res2)

            else:
                log("⚠️ 2ページ取得失敗")

            # =====================================
            # FINAL
            # =====================================
            final_unique = sorted(
                list(set(final)),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final_unique}")

            avail = [
                x for x in final_unique
                if (
                    "○" in x
                    or "△" in x
                    or "抽選" in x
                )
            ]

            if avail:

                msg = (
                    f"🏸 空きあり\n"
                    f"```\n"
                    + "\n".join(avail)
                    + "\n```"
                )

            else:
                msg = "🏸 空きなし"

            send(msg)

        except Exception as e:

            import traceback

            traceback.print_exc()

            log(f"🔥 ERROR: {e}")

            send(f"⚠️ ERROR\n{e}")

        finally:

            log("🔒 END")

            browser.close()


if __name__ == "__main__":
    run()
