import json
import os
import requests
from websocket import create_connection

WEBHOOK_URL = 'https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN'
ROLE_TAG = "@Bosses"

def main():
    print("Iniciando o bot de Raid Bosses...")
    raids_data = {}
    
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"Conectando em: {ws_url}")
    try:
        ws = create_connection(ws_url, header=ws_headers, timeout=10)
        print("Conexão WebSocket estabelecida com sucesso!")
    except Exception as e:
        print("Erro crítico ao conectar no WebSocket:", e)
        return

    try:
        print("Aguardando dados do WebSocket...")
        ws.settimeout(10)
        for i in range(5):
            try:
                msg = ws.recv()
                print(f"Mensagem {i+1} recebida.")
                data = json.loads(msg)
                if isinstance(data, dict):
                    if data.get("type") == "raidData":
                        for r in data.get("data", {}).get("raids", []):
                            raids_data[r["idx"]] = r
                        break
                    elif "raids" in data:
                        for r in data.get("raids", []):
                            raids_data[r["idx"]] = r
                        break
            except Exception as inner_e:
                print(f"Tentativa {i+1} falhou ou timeout: {inner_e}")
                break
        ws.close()
    except Exception as e:
        print("Erro ao processar mensagens do WebSocket:", e)
        return

    if not raids_data:
        print("Aviso: Nenhum dado de raid foi capturado.")
        return

    print(f"Total de raids capturados: {len(raids_data)}")
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

    print("Enviando dados para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload)
    print("Status do envio para o Discord:", res.status_code)

if __name__ == "__main__":
    main()
