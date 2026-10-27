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

def parse_time_and_countdown(ts, raw_cd=None):
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            val = int(ts)
            if val > 10000000000:
                val_sec = val / 1000
            else:
                val_sec = val
            
            target_dt = datetime.fromtimestamp(val_sec)
            now_dt = datetime.now()
            diff_seconds = int((target_dt - now_dt).total_seconds())
            
            if diff_seconds >= 0:
                hours = diff_seconds // 3600
                minutes = (diff_seconds % 3600) // 60
                seconds = diff_seconds % 60
                cd = f"T-{hours:02d}:{minutes:02d}:{seconds:02d}"
                total_mins = hours * 60 + minutes + (1 if seconds > 0 else 0)
                is_passed = False
            else:
                diff_seconds = abs(diff_seconds)
                hours = diff_seconds // 3600
                minutes = (diff_seconds % 3600) // 60
                seconds = diff_seconds % 60
                cd = f"T+{hours:02d}:{minutes:02d}:{seconds:02d}"
                total_mins = -(hours * 60 + minutes + (1 if seconds > 0 else 0))
                is_passed = True
            
            return cd, target_dt.strftime("%d/%m/%Y %H:%M"), total_mins, is_passed, val_sec
    except:
        pass
    
    if raw_cd and isinstance(raw_cd, str) and "T" in raw_cd:
        is_passed = "T+" in raw_cd
        clean = raw_cd.replace("T-", "").replace("T+", "").strip()
        parts = clean.split(":")
        if len(parts) == 3:
            try:
                h, m, s = map(int, parts)
                total_mins = h * 60 + m
                if is_passed:
                    total_mins = -total_mins
                return raw_cd, "Horário sob consulta", total_mins, is_passed, 0
            except:
                pass

    return "N/A", "Horário sob consulta", 999999, False, 0

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
        
        cd, tm_formatted, total_mins, is_passed, timestamp_sec = parse_time_and_countdown(raw_tm, raw_cd)
        
        if name not in unique_bosses:
            unique_bosses[name] = {
                "name": name,
                "cd": cd,
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
                    "cd": cd,
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

    # 1. Envio do resumo geral (deploy e atualizações de 20 em 20 min)
    fields = []
    for r in bosses_clean[:10]:
        icon = "🔴" if r["passed"] else "🟢"
        fields.append({
            "name": f"{icon} {r['name']}",
            "value": f"⏳ Respawn: `{r['cd']}` | Previsto: `{r['tm']}`",
            "inline": False
        })

    embed = {
        "title": "⏰ LEMBRETE DE BOSSES (Chronos)",
        "description": "Atualização automática de rotina.",
        "color": 10038562,
        "fields": fields
    }

    payload_summary = {
        "content": f"{ROLE_TAG} **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]}
    }

    print("Enviando resumo geral para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload_summary, timeout=5)
    print(f"Status do envio geral: {res.status_code}")

    # 2. Alerta individual de 5 minutos exato
    state = load_state()
    state_updated = False

    for boss in bosses_clean:
        name = boss["name"]
        mins = boss["mins"]
        tm_formatted = boss["tm"]

        if 0 <= mins <= 5 and not boss["passed"]:
            alert_key = f"5min_{tm_formatted}"
            if state.get(name) == alert_key:
                continue

            payload_urgent = {
                "content": f"{ROLE_TAG} 🚨 **Último aviso: boss {name} nascendo em 5 minutos!** (Previsão: `{tm_formatted}`)",
                "allowed_mentions": {"parse": ["roles"]}
            }

            print(f"Enviando alerta de 5 minutos para: {name}")
            res_u = requests.post(WEBHOOK_URL, json=payload_urgent, timeout=5)
            print(f"Status do alerta de 5 min: {res_u.status_code}")

            state[name] = alert_key
            state_updated = True

    if state_updated:
        save_state(state)
        git_commit_state()

if __name__ == "__main__":
    main()
