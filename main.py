import json
import socket
import sys
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
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

def parse_time_and_countdown(ts, raw_cd=None):
    tz = ZoneInfo("America/Sao_Paulo")
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            val = int(ts)
            if val > 10000000000:
                val_sec = val / 1000
            else:
                val_sec = val
            
            # Converte o timestamp UTC do site para o Horário de Brasília
            target_dt = datetime.fromtimestamp(val_sec, tz=ZoneInfo("UTC")).astimezone(tz)
            now_dt = datetime.now(tz)
            
            diff_seconds = int((target_dt - now_dt).total_seconds())
            
            if diff_seconds >= 0:
                hours = diff_seconds // 3600
                minutes = (diff_seconds % 3600) // 60
                seconds = diff_seconds % 60
                cd_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                cd_text = f"O boss nasce em {cd_time}"
                total_mins = hours * 60 + minutes + (1 if seconds > 0 else 0)
                is_passed = False
            else:
                diff_seconds = abs(diff_seconds)
                hours = diff_seconds // 3600
                minutes = (diff_seconds % 3600) // 60
                seconds = diff_seconds % 60
                cd_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                cd_text = f"O boss já nasceu há {cd_time}"
                total_mins = -(hours * 60 + minutes + (1 if seconds > 0 else 0))
                is_passed = True
            
            return cd_text, target_dt.strftime("%d/%m/%Y %H:%M"), total_mins, is_passed, val_sec
    except:
        pass
    
    if raw_cd and isinstance(raw_cd, str) and "T" in raw_cd:
        is_passed = "T+" in raw_cd
        clean = raw_cd.replace("T-", "").replace("T+", "").strip()
        if is_passed:
            return f"O boss já nasceu há {clean}", "Horário sob consulta", -999, True, 0
        else:
            return f"O boss nasce em {clean}", "Horário sob consulta", 999, False, 0

    return "O boss nasce em N/A", "Horário sob consulta", 999999, False, 0

def main():
    print("Conectando ao WebSocket para varredura completa...")
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
            if ("name" in obj or "title" in obj) and ("_time" in obj or "time" in obj or "_countdown" in obj or "countdown" in obj):
                raids_list.append(obj)
            for v in obj.values():
                extract_raids(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_raids(item)

    extract_raids(raw_data)

    chronos_bosses = [r for r in raids_list if str(r.get("server", "15")) == "15"]
    if not chronos_bosses:
        chronos_bosses = raids_list

    unique_bosses = {}
    for r in chronos_bosses:
        name = r.get("name", r.get("title"))
        if not name:
            continue
        
        raw_cd = r.get("_countdown", r.get("countdown"))
        raw_tm = r.get("_time", r.get("time", r.get("respawn_time")))
        
        cd_text, tm_formatted, total_mins, is_passed, timestamp_sec = parse_time_and_countdown(raw_tm, raw_cd)
        
        if name not in unique_bosses:
            unique_bosses[name] = {
                "name": name,
                "cd": cd_text,
                "tm": tm_formatted,
                "mins": total_mins,
                "passed": is_passed,
                "timestamp": timestamp_sec
            }
        else:
            existing = unique_bosses[name]
            if timestamp_sec > 0 and (existing["timestamp"] == 0 or timestamp_sec < existing["timestamp"]):
                unique_bosses[name] = {
                    "name": name,
                    "cd": cd_text,
                    "tm": tm_formatted,
                    "mins": total_mins,
                    "passed": is_passed,
                    "timestamp": timestamp_sec
                }

    bosses_clean = list(unique_bosses.values())
    bosses_clean.sort(key=lambda x: abs(x["mins"]) if x["mins"] != 999999 else 999999)

    if not bosses_clean:
        print("Nenhum boss processado.")
        return

    state = load_state()
    state_updated = False

    for r in bosses_clean[:6]:
        name = r["name"]
        mins = r["mins"]
        cd = r["cd"]
        tm_formatted = r["tm"]
        passed = r["passed"]

        if 0 <= mins <= 5 and not passed:
            alert_key = f"5min_{tm_formatted}"
            if state.get(name) == alert_key:
                pass
            else:
                payload_urgent = {
                    "content": f"{ROLE_TAG} 🚨 **Último aviso: boss {name} nascendo em 5 minutos!** (Previsão: `{tm_formatted}`)",
                    "allowed_mentions": {"parse": ["roles"]}
                }
                print(f"Enviando alerta urgente de 5 min para: {name}")
                requests.post(WEBHOOK_URL, json=payload_urgent, timeout=5)
                
                state[name] = alert_key
                state_updated = True
                continue

        icon = "🔴" if passed else "🟢"
        embed = {
            "title": f"⚔️ AOG | RAID ALERT: {name.upper()}",
            "description": f"⏳ **{cd}**\n📅 **Previsão:** `{tm_formatted}`",
            "color": 15158332 if passed else 3066993
        }

        payload_individual = {
            "content": f"{ROLE_TAG} **Atualização de Boss:** `{name}`",
            "embeds": [embed],
            "allowed_mentions": {"parse": ["roles"]}
        }

        print(f"Enviando notificação individual para: {name}")
        requests.post(WEBHOOK_URL, json=payload_individual, timeout=5)

    if state_updated:
        save_state(state)
        git_commit_state()

if __name__ == "__main__":
    main()
