def run_check():
    headless = os.getenv("GITHUB_ACTIONS") == "true"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            print("アクセス")
            page.goto(BASE_URL)
            page.wait_for_timeout(3000)

            # ===== 通常遷移 =====
            page.locator("input[type='submit']", has_text="公共施設予約メニュー").click()
            page.wait_for_timeout(2000)

            page.locator("input[type='submit']", has_text="空き照会").click()
            page.wait_for_timeout(2000)

            page.locator("input[type='submit']", has_text="次頁").click()
            page.wait_for_timeout(3000)

            page.locator("input[type='submit']", has_text="柳北").click()
            page.wait_for_timeout(2000)

            page.locator("input[name='ucPCFooter$btnForward']").click()
            page.wait_for_timeout(2000)

            page.locator("input[type='submit']", has_text="カレンダー").click()
            page.wait_for_timeout(2000)

            page.locator("input[type='submit']", has_text="1ヶ月").click()
            page.wait_for_timeout(2000)

            page.locator("input[name='ucPCFooter$btnForward']").click()
            page.wait_for_timeout(3000)

            # 体育館クリック
            page.locator("span:has-text('体育館')").click()
            page.wait_for_timeout(3000)

            all_vacant_info = []

            def scan(label):
                print(f"スキャン: {label}")
                tables = page.locator("table").all()

                for tbl in tables:
                    if "体育館" not in tbl.inner_text():
                        continue

                    for cell in tbl.locator("td").all():
                        txt = cell.inner_text().strip()
                        if txt in ["○", "△"]:
                            row = cell.locator("xpath=..").inner_text()
                            all_vacant_info.append(" ".join(row.split()))

            # =========================
            # ① 1ページ目
            # =========================
            scan("現在")

            # =========================
            # ② 次期間（ここだけ追加）
            # =========================
            btn = page.locator("#btnNextPeriod")

            if btn.count() > 0:
                print("次期間クリック")

                before = page.inner_text("body")

                btn.click()
                page.wait_for_timeout(3000)

                after = page.inner_text("body")

                if before != after:
                    scan("次期間")
                else:
                    print("変化なし（= 次ページなし or 同一表示）")

            # =========================
            # 集約
            # =========================
            final = list(dict.fromkeys(all_vacant_info))

            if final:
                msg = "🏸 空きあり\n\n" + "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send_discord(msg)

        except Exception as e:
            print("エラー:", e)

        finally:
            browser.close()
