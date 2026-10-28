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

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "<@&1285763435107319829>"
STATE_FILE = "sent_alerts.json"

# Cronograma fixo categorizado e blindado
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

def is_valid_boss_name(name):
    if not name or not isinstance(name, str):
        return False
    name_clean = name.strip()
    name_lower = name_clean.lower()
    
    # Barreiras rígidas contra qualquer propaganda ou texto injetado
    blacklist = ["t.me", "telegram", "http", "www", "channel", "premium", "join", "bot", "tools", "dm at", "@", "profit", "tucos"]
    if any(b in name_lower for b in blacklist):
        return False
    
    # Nomes de boss reais são curtos e não possuem frases longas ou caracteres inválidos
    if len(name_clean) > 35 or len(name_clean) < 3:
        return False
    
    if "/" in name_clean or "." in name_clean or "?" in name_clean or "!" in name_clean:
        return False
        
    return True

def parse_time_and_countdown(ts, raw_cd=None):
    tz = ZoneInfo("America/Sao_Paulo")
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            val = int(ts)
            if val > 10000000000:
                val_sec = val / 1000
            else:
                val_sec = val
            
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
    
    if raw_cd and isinstance(raw_cd, str) and "T" in raw_cd:
        is_passed = "T+" in raw_cd
        clean = raw_cd.replace("T-", "").replace("T+", "").strip()
        if is_passed:
            return f"Já nasceu há {clean}", "Horário sob consulta", -999, True, 0, -9999
        else:
            return f"Nasce em {clean}", "Horário sob consulta", 999, False, 0, 9999

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

def main():
    print(f"[{datetime.now()}] Varredura com filtro estricto de nomes iniciada...")
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
                # Extrai apenas se tiver estrutura de boss válida
                name = obj.get("name", obj.get("title"))
                if name and is_valid_boss_name(name) and ("_time" in obj or "time" in obj or "_countdown" in obj or "countdown" in obj):
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
        if not is_valid_boss_name(name):
            continue
        
        if any(f["name"].lower() in name.lower() for f in FIXED_BOSSES):
            continue
        
        raw_cd = r.get("_countdown", r.get("countdown"))
        raw_tm = r.get("_time", r.get("time", r.get("respawn_time")))
        
        cd_text, tm_formatted, total_mins, is_passed, timestamp_sec, diff_seconds = parse_time_and_countdown(raw_tm, raw_cd)
        
        if name not in unique_bosses:
            unique_bosses[name] = {
                "name": name,
                "category": "FIELD RAIDS",
                "cd": cd_text,
                "tm": tm_formatted,
                "mins": total_mins,
                "passed": is_passed,
                "timestamp": timestamp_sec,
                "diff_secs": diff_seconds
            }
        else:
            existing = unique_bosses[name]
            if timestamp_sec > 0 and (existing["timestamp"] == 0 or timestamp_sec < existing["timestamp"]):
                unique_bosses[name] = {
                    "name": name,
                    "category": "FIELD RAIDS",
                    "cd": cd_text,
                    "tm": tm_formatted,
                    "mins": total_mins,
                    "passed": is_passed,
                    "timestamp": timestamp_sec,
                    "diff_secs": diff_seconds
                }

    bosses_clean = list(unique_bosses.values())
    fixed_clean = get_fixed_bosses_list()
    bosses_clean.extend(fixed_clean)
    bosses_clean.sort(key=lambda x: abs(x["mins"]) if x["mins"] != 999999 else 999999)

    if not bosses_clean:
        print("Nenhum boss processado neste ciclo.")
        return

    state = load_state()
    state_updated = False

    # Alerta de 5 minutos exato (0 a 300 segundos)
    for r in bosses_clean:
        name = r["name"]
        diff_secs = r["diff_secs"]
        tm_formatted = r["tm"]
        passed = r["passed"]

        if 0 <= diff_secs <= 300 and not passed:
            alert_key = f"alert_5min_{tm_formatted}"
            if state.get(name) == alert_key:
                continue
            
            embed_urgent = {
                "title": "🚨 AOG | ALERTA DE JANELA DE BOSS",
                "description": f"O boss vai nascer em breve!\n\n🎯 **Boss:** `{name.upper()}`\n⏳ **Previsão exata:** `{tm_formatted}`",
                "color": 15158332,
                "footer": {"text": "AOG • RAID ALERT SYSTEM | Horário de Brasília"}
            }
            payload_urgent = {
                "content": f"{ROLE_TAG} **Atenção clã! O boss {name} nasce exatamente às {tm_formatted} (Faltam 5 minutos)!**",
                "allowed_mentions": {"parse": ["roles"]},
                "embeds": [embed_urgent]
            }
            print(f"Disparando alerta de 5 min para {name} com nascimento às {tm_formatted}")
            requests.post(WEBHOOK_URL, json=payload_urgent, timeout=5)
            
            state[name] = alert_key
            state_updated = True

    if state_updated:
        save_state(state)

    # Painel Consolidado de Status
    fields = []
    for r in bosses_clean[:6]:
        icon = "🔴" if r["passed"] else "🟢"
        fields.append({
            "name": f"{icon} [{r['category']}] {r['name']}",
            "value": f"> ⏳ **Tempo até o spawn:** `{r['cd'].replace('Nasce em ', '')}`\n> 📅 **Nascimento Estimado:** `{r['tm']}`",
            "inline": False
        })

    embed_dashboard = {
        "title": "⚔️ AOG | RAID BOSS ALERT",
        "description": "Painel de controle atualizado do servidor Chronos.",
        "color": 3447003,
        "fields": fields,
        "footer": {"text": "AOG • RAID ALERT SYSTEM | Horário de Brasília"}
    }

    payload_dashboard = {
        "content": f"{ROLE_TAG} **Atualização do Painel de Raids:**",
        "allowed_mentions": {"parse": ["roles"]},
        "embeds": [embed_dashboard],
        "flags": 4  # SUPPRESS_EMBEDS: Bloqueia qualquer link externo
    }

    print("Enviando painel tático limpo...")
    requests.post(WEBHOOK_URL, json=payload_dashboard, timeout=5)

if __name__ == "__main__":
    main()
