import json
import socket
import sys
import os
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import requests
from websocket import create_connection

socket.setdefaulttimeout(4)
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1564794001704615966/95X7TnqSNCxFv_2hPEehIQV4BV_WxoZKvCKVMlusjf9NnJu1oKQGtmrr4t7hNaCOfd5a"
ROLE_TAG = "<@&1285763435107319829>"
STATE_FILE = "sent_alerts.json"

# Cronograma fixo categorizado
FIXED_BOSSES = [
    {"name": "Stakato Queen", "category": "SWAMP RAIDS", "times": [dtime(10, 0), dtime(13, 0), dtime(17, 0)]},
    {"name": "Mega Chaos Golem", "category": "PLUNDEROUS RAIDS", "times": [dtime(10, 0), dtime(13, 0), dtime(17, 0)]},
    {"name": "Chaos Golem", "category": "GOLEM RAIDS", "times": [dtime(11, 0), dtime(15, 0)]},
]

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

def parse_time_and_countdown(ts, raw_cd=None):
    tz = ZoneInfo("America/Sao_Paulo")
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            val = int(ts)
            val_sec = val / 1000 if val > 10000000000 else val
            
            target_dt = datetime.fromtimestamp(val_sec, tz=ZoneInfo("UTC")).astimezone(tz)
            now_dt = datetime.now(tz)
            
            diff_seconds = int((target_dt - now_dt).total_seconds())
            
            if diff_seconds >= 0:
                hours = diff_seconds // 3600
                minutes = (diff_seconds % 3600) // 60
                seconds = diff_seconds % 60
                cd_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                cd_text = f"Nasce em {cd_time}"
                total_mins = hours * 60 + minutes + (1 if seconds > 0 else 0)
                is_passed = False
            else:
                diff_sec_abs = abs(diff_seconds)
                hours = diff_sec_abs // 3600
                minutes = (diff_sec_abs % 3600) // 60
                seconds = diff_sec_abs % 60
                cd_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                cd_text = f"Já nasceu há {cd_time}"
                total_mins = -(hours * 60 + minutes + (1 if seconds > 0 else 0))
                is_passed = True
            
            return cd_text, target_dt.strftime("%d/%m/%Y %H:%M"), total_mins, is_passed, val_sec, diff_seconds
    except:
        pass

    return "Nasce em N/A", "Horário sob consulta", 999999, False, 0, 99999

def get_fixed_bosses_list():
    tz = ZoneInfo("America/Sao_Paulo")
    now = datetime.now(tz)
    fixed_list = []

    for item in FIXED_BOSSES:
        name = item["name"]
        category = item["category"]
        for t in item["times"]:
            target_dt = datetime.combine(now.date(), t, tzinfo=tz)
            if target_dt < now:
                target_dt += timedelta(days=1)
            
            diff_seconds = int((target_dt - now).total_seconds())
            hours = diff_seconds // 3600
            minutes = (diff_seconds % 3600) // 60
            seconds = diff_seconds % 60
            
            cd_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            cd_text = f"Nasce em {cd_time}"
            total_mins = hours * 60 + minutes + (1 if seconds > 0 else 0)
            
            fixed_list.append({
                "name": name,
                "category": category,
                "cd": cd_text,
                "tm": target_dt.strftime("%d/%m/%Y %H:%M"),
                "mins": total_mins,
                "passed": False,
                "timestamp": target_dt.timestamp(),
                "diff_secs": diff_seconds
            })
            
    return fixed_list

def safe_discord_post(payload):
    payload_str = str(payload).lower()
    if "t.me" in payload_str or "telegram" in payload_str or "dm at" in payload_str or "a-tools" in payload_str:
        print("⚠️ Alerta de segurança: Propaganda detectada e bloqueada!")
        return
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Discord Response Status: {resp.status_code}")

def main():
    print(f"[{datetime.now()}] Varredura silenciosa iniciada (dual alert 10m/5m)...")
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
        print(f"Aviso WebSocket: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    raids_list = []
    if raw_data:
        def extract_raids(obj):
            if isinstance(obj, dict):
                obj_str = str(obj).lower()
                if "t.me" in obj_str or "telegram" in obj_str or "dm at" in obj_str:
                    return
                
                name = obj.get("name", obj.get("title"))
                if name and ("_time" in obj or "time" in obj or "_countdown" in obj or "countdown" in obj):
                    raids_list.append(obj)
                for v in obj.values():
                    extract_raids(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_raids(item)

        extract_raids(raw_data)

    chronos_bosses = [r for r in raids_list if str(r.get("server", "15")) == "15"]
    if not chronos_bosses and raids_list:
        chronos_bosses = raids_list

    unique_bosses = {}
    for r in chronos_bosses:
        name = r.get("name", r.get("title"))
        if not name:
            continue
        
        name_str = str(name).strip()
        if any(bad in name_str.lower() for bad in ["t.me", "telegram", "http", "profit"]):
            continue
        
        if any(f["name"].lower() in name_str.lower() for f in FIXED_BOSSES):
            continue
        
        raw_cd = r.get("_countdown", r.get("countdown"))
        raw_tm = r.get("_time", r.get("time", r.get("respawn_time")))
        
        cd_text, tm_formatted, total_mins, is_passed, timestamp_sec, diff_seconds = parse_time_and_countdown(raw_tm, raw_cd)
        
        if name_str not in unique_bosses:
            unique
