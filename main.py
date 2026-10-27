import json
import os
import requests
from websocket import create_connection

WEBHOOK_URL = 'https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN'
ROLE_TAG = "@Bosses"

def main():
    raids_data = {}
    session = requests.Session()
    
    # 1. Acessa a página principal primeiro para capturar cookies e simular um navegador real
    print("Acessando a página principal para obter sessão...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://l2stuff.xyz/"
        }
        session.get("https://l2stuff.xyz/", headers=headers, timeout=10)
    except Exception as e:
        print("Aviso ao carregar página principal:", e)

    # Extrai os cookies obtidos na sessão HTTP para passar ao WebSocket
    cookie_jar = session.cookies.get_dict()
    cookie_string = "; ".join([f"{k}={v}" for k, v in cookie_jar.items()])

    # 2. Tenta conectar ao WebSocket usando os cookies de sessão e headers completos
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookie_string
    }

    urls_to_try = [
        "wss://l2stuff.xyz/ws",
        "wss://l2stuff.xyz/socket.io/?EIO=4&transport=websocket"
    ]

    ws = None
    for ws_url in urls_to_try:
        try:
            print(f"Tentando conectar em: {ws_url}")
            ws = create_connection(ws_url, header=ws_headers, timeout=10)
            break
        except Exception as e:
            print(f"Falha na URL {ws_url}: {e}")

    if not ws:
        print("Erro crítico: Não foi possível estabelecer conexão WebSocket.")
        return

    try:
        for _ in range(3):
            msg = ws.recv()
            data = json.loads(msg)
            if data.get("type") == "raidData":
                for r in data.get("data", {}).get("raids", []):
                    raids_data[r["idx"]] = r
                break
        ws.close()
    except Exception as e:
        print("Erro ao receber dados do WebSocket:", e)
        return

    if not raids_data:
        print("Não foi possível coletar os dados do WebSocket (dados vazios).")
        return

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
        "footer": {"text": "Fonte: l2stuff.xyz • GitHub Actions"}
    }

    payload = {
        "content": f"{ROLE_TAG} **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]}
    }

    res = requests.post(WEBHOOK_URL, json=payload)
    print("Status do envio para o Discord:", res.status_code)

if __name__ == "__main__":
    main()
