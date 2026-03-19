import time
import random
from datetime import datetime
from check_taito import run_check, send_discord  # send_discord使える前提

INTERVAL = 60  # 基本間隔（秒）

while True:
    now = datetime.now()
    print(f"[{now}] Loop start")

    try:
        run_check()
    except Exception as e:
        print(f"[{now}] Loop error:", e)

        # エラー通知（重要）
        try:
            send_discord(f"⚠️ Taitoチェックエラー\n{e}")
        except:
            pass

    print(f"[{datetime.now()}] Loop end\n")

    # ランダム揺らぎ（Bot対策）
    sleep_time = INTERVAL + random.randint(-10, 10)
    time.sleep(max(30, sleep_time))