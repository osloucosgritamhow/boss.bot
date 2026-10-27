import json
import requests
from websocket import create_connection

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def main():
    print("Iniciando execução...")
    raids_data = {}
    
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    ws = None
    try:
        print("Conectando ao WebSocket (timeout de 3s)...")
        ws = create_connection(ws_url, header=ws_headers, timeout=3)
        ws.settimeout(3)
        
        print("Lendo dados...")
        msg = ws.recv()
        if msg:
            data = json.loads(msg)
            if isinstance(data, dict):
                raids_list = data.get("data", {}).get("raids", []) or data.get("raids", [])
                for r in raids_list:
                    raids_data[r["idx"]] = r
    except Exception as e:
        print(f"Aviso na leitura: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    if not raids_data:
        print("Nenhum dado capturado nesta execução.")
        return

    print(f"Processando {len(raids_data)} raids...")
    chronos = [r for r in raids_data.values() if str(r.get("server")) == "15"]
    chronos.sort(key=lambda x: x.get("_countdown", ""))

    fields = []
    for r in chronos[:5]:
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
        "description": "Atualização automática de rotina.",
        "color": 10038562,
        "fields": fields,
        "footer": {"text": "Fonte: l2stuff.xyz • GitHub Actions"}
    }

    payload = {
        "content": f"{ROLE_TAG} **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]}
    }

    print("Enviando para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio para o Discord: {res.status_code}")

if __name__ == "__main__":
    main()
