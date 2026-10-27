import json
import socket
import sys
import os
import subprocess
from datetime import datetime
import requests
from websocket import create_connection

socket.setdefaulttimeout(4)
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"
STATE_FILE = "sent_alerts.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except:
            pass

def git_commit_state():
    try:
        subprocess.run(["git", "config", "--global", "user.name", "AOG Bot"], capture_output=True)
        subprocess.run(["git", "config", "--global", "user.email", "bot@aog.internal"], capture_output=True)
        subprocess.run(["git", "add", STATE_FILE], capture_output=True)
        subprocess.run(["git", "commit", "-m", "update boss alert state [skip ci]"], capture_output=True)
        subprocess.run(["git", "push"], capture_output=True)
    except:
        pass

def parse_countdown_to_minutes(cd_str):
    try:
        if not cd_str or "N/A" in cd_str:
            return 999999, False
        
        is_passed = "T+" in cd_str
        clean_str = cd_str.replace("T-", "").replace("T+", "").strip()
        parts = clean_str.split(":")
        
        if len(parts) == 3:
            h, m, s = map(int, parts)
            total_minutes = h * 60 + m + (1 if s > 0 else 0)
            return (-total_minutes if is_passed else total_minutes), is_passed
    except:
        pass
    return 999999, False

def format_time(ts):
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            val = int(ts)
            if val > 10000000000:
                val = val / 1000
            dt = datetime.fromtimestamp(val)
            return dt.strftime("%d/%m/%Y %H:%M")
    except:
        pass
    return str(ts)

def main():
    print("Iniciando varredura completa de bosses (Field, Golems, Swamp, Plunderous)...")
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    ws = None
    raw_data = None
    try:
        ws = create_connection(ws_url, header=ws_headers, timeout=4)
        ws.settimeout(4)
        for i in range(3):
            msg = ws.recv()
            if msg:
                parsed = json.loads(msg)
                if isinstance(parsed, dict):
                    raw_data = parsed
                    break
    except Exception as e:
        print(f"Erro na conexão WebSocket: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    if not raw_data:
        print("Nenhum dado capturado.")
        return

    raids_list = []
    def extract_raids(obj):
        if isinstance(obj, dict):
            if "name" in obj and ("_countdown" in obj or "countdown" in obj or "_time" in obj or "time" in obj):
                raids_list.append(obj)
            for v in obj.values():
                extract_raids(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_raids(item)

    extract_raids(raw_data)

    # Filtra rigorosamente pelo Chronos (server 15)
    chronos_bosses = [r for r in raids_list if str(r.get("server", "15")) == "15"]
    if not chronos_bosses:
        chronos_bosses = raids_list

    # Consolida bosses únicos mantendo o menor tempo/countdown
    unique_bosses = {}
    for r in chronos_bosses:
        name = r.get("name")
        if not name:
            continue
        
        cd = r.get("_countdown", r.get("countdown", "N/A"))
        tm = r.get("_time", r.get("time", r.get("respawn_time", "N/A")))
        tm_formatted = format_time(tm)
        
        mins, is_passed = parse_countdown_to_minutes(cd)
        
        if name not in unique_bosses:
            unique_bosses[name] = {"name": name, "cd": cd, "tm": tm_formatted, "mins": mins, "passed": is_passed}
        else:
            if abs(mins) < abs(unique_bosses[name]["mins"]):
                unique_bosses[name] = {"name": name, "cd": cd, "tm": tm_formatted, "mins": mins, "passed": is_passed}

    state = load_state()
    state_updated = False
    now_str = datetime.now().strftime("%Y-%m-%d")

    for name, boss in unique_bosses.items():
        mins = boss["mins"]
        cd = boss["cd"]
        tm_formatted = boss["tm"]
        
        # Define as janelas de alerta:
        # - Alerta de 20 min (entra na janela de 20 min ou menos)
        # - Alerta de 5 min (entra na janela de 5 min ou menos, ou já nasceu T+)
        is_urgent = mins <= 5 or boss["passed"]
        is_normal = mins <= 20 and not is_urgent

        alert_type = None
        if is_urgent:
            alert_type = f"urgent_{tm_formatted}"
        elif is_normal:
            alert_type = f"normal_{tm_formatted}"

        if alert_type:
            # Verifica se já mandamos esse alerta específico para este respawn
            if state.get(name) == alert_type:
                continue

            # Monta a notificação individual limpa e clara
            if boss["passed"]:
                status_txt = f"🔴 **O boss já nasceu / expirou!** (`{cd}`)"
            elif mins <= 5:
                status_txt = f"🚨 **ATENÇÃO MÁXIMA! Nascerá em até 05:00 min!** (`{cd}`)"
            else:
                status_txt = f"⏳ **Alerta de rotina: Nascerá em breve.** (`{cd}`)"

            embed = {
                "title": f"⚔️ AOG | RAID ALERT: {name.upper()}",
                "description": f"{status_txt}\n\n📅 **Horário Previsto:** `{tm_formatted}`",
                "color": 15158332 if is_urgent else 3066993
            }

            payload = {
                "content": f"{ROLE_TAG} **Alerta de Raid Boss:** `{name}`",
                "embeds": [embed],
                "allowed_mentions": {"parse": ["roles"]}
            }

            print(f"Enviando notificação individual para: {name} ({cd})")
            res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
            print(f"Status do envio: {res.status_code}")

            state[name] = alert_type
            state_updated = True

    if state_updated:
        save_state(state)
        git_commit_state()

if __name__ == "__main__":
    main()
