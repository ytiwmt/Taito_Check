import requests
import os
import re
import datetime
from playwright.sync_api import sync_playwright

VERSION = "v7.34-restart-for-next-month"

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
# 共通遷移
# =========================
def move_to_calendar(page):
    page.goto(BASE_URL)

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)

    # 公共施設予約メニュー
    page.locator("input[type='submit']", has_text="公共施設予約メニュー").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 空き照会
    page.locator("input[type='submit']", has_text="空き照会").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次頁
    page.locator("input[type='submit']", has_text="次頁").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 柳北
    page.locator("input[type='submit']", has_text="柳北").first.wait_for(timeout=30000)
    page.locator("input[type='submit']", has_text="柳北").first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次へ
    page.locator("input[name='ucPCFooter$btnForward']").first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # カレンダー
    page.locator("input[type='submit']", has_text="カレンダー").first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 1ヶ月
    page.locator("input[type='submit']", has_text="1ヶ月").first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次へ
    page.locator("input[name='ucPCFooter$btnForward']").first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)


# =========================
# 次期間へ
# =========================
def move_next_period(page):
    log("⏭️ 次期間へ移動")

    btn = page.locator("#btnNextPeriod")

    btn.wait_for(timeout=10000)

    before = page.locator("body").inner_text()[:500]

    btn.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(4000)

    after = page.locator("body").inner_text()[:500]

    if before != after:
        log("✅ ページ変化あり")
        return True

    log("⚠️ ページ変化なし")
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
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        final = []

        try:

            # =====================================
            # 1ページ目
            # =====================================
            move_to_calendar(page)

            log("📑 1ページ目")

            res1 = parse(page, "1P")

            log(f"1P: {res1}")

            analyze(res1, "1P")

            final.extend(res1)

            # =====================================
            # 2ページ目
            # =====================================
            # 同一セッション内で
            # btnNextPeriodだけ押す
            # =====================================

            if move_next_period(page):

                body = page.locator("body").inner_text()

                if "お探しのページを表示できません" in body:
                    log("❌ 不正遷移ページ")
                else:
                    log("📑 2ページ目")

                    res2 = parse(page, "2P")

                    log(f"2P: {res2}")

                    analyze(res2, "2P")

                    if res2:
                        final.extend(res2)
                    else:
                        log("⚠️ 2Pデータなし")

            # =====================================
            # 集約
            # =====================================
            final_unique = sorted(
                list(set(final)),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final_unique}")

            # 空きだけ通知
            avail = [
                x for x in final_unique
                if ("○" in x or "△" in x or "抽選" in x)
            ]

            if avail:

                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり [{VERSION}]\n"
                    f"{len(avail)}件\n"
                    f"```\n"
                    + "\n".join(avail)
                    + "\n```"
                )

            else:
                msg = f"🏸 空きなし [{VERSION}]"

            send(msg)

        except Exception as e:

            import traceback

            traceback.print_exc()

            log(f"🔥 ERROR: {e}")

            send(
                f"⚠️ エラー [{VERSION}]\n"
                f"{e}"
            )

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
