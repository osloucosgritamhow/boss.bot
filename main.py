import json
import socket
import sys
from datetime import datetime
import requests
from websocket import create_connection

socket.setdefaulttimeout(4)
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def format_time_and_countdown(ts):
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
            else:
                diff_seconds = abs(diff_seconds)
                hours = diff_seconds // 3600
                minutes = (diff_seconds % 3600) // 60
                seconds = diff_seconds % 60
                cd = f"T+{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            return cd, target_dt.strftime("%d/%m/%Y %H:%M"), val_sec
    except:
        pass
    return "N/A", str(ts), 0

def main():
    print("Conectando ao WebSocket...")
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
        print(f"Erro na conexão: {e}")
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
            if "name" in obj and ("_time" in obj or "time" in obj or "respawn_time" in obj):
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
        name = r.get("name")
        if not name:
            continue
        tm_raw = r.get("_time", r.get("time", r.get("respawn_time", 0)))
        cd, tm_formatted, timestamp_sec = format_time_and_countdown(tm_raw)
        
        if name not in unique_bosses:
            unique_bosses[name] = {
                "name": name,
                "cd": cd,
                "tm": tm_formatted,
                "timestamp": timestamp_sec
            }
        else:
            existing = unique_bosses[name]
            if timestamp_sec > 0 and (existing["timestamp"] == 0 or timestamp_sec < existing["timestamp"]):
                unique_bosses[name] = {
                    "name": name,
                    "cd": cd,
                    "tm": tm_formatted,
                    "timestamp": timestamp_sec
                }

    bosses_clean = list(unique_bosses.values())
    bosses_clean.sort(key=lambda x: x["timestamp"] if x["timestamp"] > 0 else float('inf'))

    fields = []
    for r in bosses_clean[:6]:
        name = r["name"]
        cd = r["cd"]
        tm_formatted = r["tm"]
        
        icon = "🔴" if "T+" in str(cd) else "🟢"
        fields.append({
            "name": f"{icon} {name}",
            "value": f"⏳ Respawn: `{cd}` | Previsto: `{tm_formatted}`",
            "inline": False
        })

    embed = {
        "title": "⏰ LEMBRETE DE BOSSES (Chronos)",
        "description": "Atualização automática de rotina.",
        "color": 10038562,
        "fields": fields
    }

    payload = {
        "content": f"{ROLE_TAG} **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]}
    }

    print("Enviando para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio: {res.status_code}")

if __name__ == "__main__":
    main()
