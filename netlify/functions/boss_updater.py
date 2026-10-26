import json
import os
import requests
from websocket import create_connection

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://discord.com/api/webhooks/1563256850504482939/G-rDLNKBVhjVhl_sNst-cDDIJqaO_dJLJzJ9fWFaL5bOGZ2PApeDnoxNs7JlED__NHrV")
ROLE_TAG = "@Bosses"

def handler(event, context):
    raids_data = {}
    
    try:
        ws = create_connection(
            "wss://l2stuff.xyz/ws",
            header={"Origin": "https://l2stuff.xyz"},
            timeout=10
        )
        for _ in range(3):
            msg = ws.recv()
            data = json.loads(msg)
            if data.get("type") == "raidData":
                for r in data.get("data", {}).get("raids", []):
                    raids_data[r["idx"]] = r
                break
        ws.close()
    except Exception as e:
        print("Erro ao conectar no WebSocket:", e)

    if not raids_data:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Não foi possível coletar os dados do WebSocket."})
        }

    chronos = [r for r in raids_data.values() if str(r.get("server")) == "15"]
    chronos.sort(key=lambda x: x.get("_countdown", ""))

    fields = []
    top_bosses = chronos[:5]
    for r in top_bosses:
        cd = r.get("_countdown", "N/A")
        tm = r.get("_time", "N/A")
        name = r.get("name", "Unknown Boss")
        icon = "🔴" if "T+" in str(cd) else "🟢"
        
        fields.append({
            "name": f"{icon} {name}",
            "value": f"⏳ Respawn: `{cd}` | Previsto: `{tm}`",
            "inline": False
        })

    embed = {
        "title": "⏰ LEMBRETE DE BOSSES (Chronos)",
        "description": "Atualização automática de rotina (a cada 20 min).",
        "color": 10038562,
        "fields": fields,
        "footer": {"text": "Fonte: l2stuff.xyz • Netlify Functions"}
    }

    payload = {
        "content": f"{ROLE_TAG} **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]}
    }

    res = requests.post(WEBHOOK_URL, json=payload)

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Lembrete enviado com sucesso!", "status": res.status_code})
    }
