import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v7.33-btnNextPeriod-real-click"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# =========================
# ログ
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
# 解析
# =========================
def parse(page, label):
    results = []

    links = page.locator("a[id*='lnkKoma']").all()

    log(f"[{label}] link数: {len(links)}")

    for l in links:
        try:
            txt = l.inner_text()

            txt = (
                txt
                .replace("\xa0", "")
                .replace(" ", "")
                .replace("\n", "")
                .strip()
            )

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

    log(
        f"{label}: "
        f"○△={len(ok)} / "
        f"抽選={len(lot)} / "
        f"×={len(ng)}"
    )


# =========================
# 次ページ
# =========================
def go_next(page):
    log("⏭️ 次ページ（btnNextPeriod本押し）")

    try:
        before = page.locator("a[id*='lnkKoma']").count()

        log(f"遷移前リンク数: {before}")

        # ボタン存在確認
        page.locator("#btnNextPeriod").wait_for(timeout=10000)

        # ★本物のボタン押下
        page.locator("#btnNextPeriod").click(force=True)

        # ASP.NET描画待ち
        page.wait_for_timeout(5000)

        after = page.locator("a[id*='lnkKoma']").count()

        log(f"遷移後リンク数: {after}")

        # デバッグ
        body = page.inner_text("body")[:1500]

        log(f"BODY先頭:\n{body}")

        if after <= 0:
            log("❌ lnkKoma消失")
            return False

        if before == after:
            log("⚠️ link数変化なし")

        log("✅ 2ページ取得成功")

        return True

    except Exception as e:
        log(f"❌ 遷移失敗: {e}")
        return False


# =========================
# メイン
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
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        final = []

        try:
            # =========================
            # 初期アクセス
            # =========================
            page.goto(BASE_URL)

            page.wait_for_load_state("networkidle")

            # 公共施設予約メニュー
            page.locator(
                "input[type='submit']",
                has_text="公共施設予約メニュー"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # 空き照会
            page.locator(
                "input[type='submit']",
                has_text="空き照会"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # 次頁
            page.locator(
                "input[type='submit']",
                has_text="次頁"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # 柳北
            page.locator(
                "input[type='submit']",
                has_text="柳北"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # 次へ
            page.locator(
                "input[name='ucPCFooter$btnForward']"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # カレンダー
            page.locator(
                "input[type='submit']",
                has_text="カレンダー"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # 1ヶ月
            page.locator(
                "input[type='submit']",
                has_text="1ヶ月"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # 次へ
            page.locator(
                "input[name='ucPCFooter$btnForward']"
            ).first.click()

            page.wait_for_load_state("networkidle")

            # =========================
            # 1ページ目
            # =========================
            log("📑 1ページ目")

            res1 = parse(page, "1P")

            analyze(res1, "1P")

            final.extend(res1)

            # =========================
            # 2ページ目
            # =========================
            if go_next(page):

                log("📑 2ページ目")

                res2 = parse(page, "2P")

                analyze(res2, "2P")

                final.extend(res2)

            else:
                log("⚠️ 2ページ取得失敗")

            # =========================
            # 集約
            # =========================
            final_unique = sorted(
                list(set(final)),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final_unique}")

            # =========================
            # 通知
            # =========================
            has_open = any(
                ("○" in x or "△" in x)
                for x in final_unique
            )

            if has_open:

                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり [{VERSION}]\n"
                    f"{len(final_unique)}件\n"
                    f"```\n"
                    + "\n".join(final_unique)
                    + "\n```"
                )

            else:
                msg = f"🏸 空きなし [{VERSION}]"

            send(msg)

        except Exception as e:

            log(f"🔥 ERROR: {e}")

            send(
                f"⚠️ エラー [{VERSION}]\n{e}"
            )

        finally:

            log("🔒 END")

            browser.close()


if __name__ == "__main__":
    run()
