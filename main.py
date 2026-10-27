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

    try:
        print("Conectando ao WebSocket...")
        ws = create_connection(ws_url, header=ws_headers, timeout=5)
        ws.settimeout(3)
        
        print("Lendo mensagens do servidor...")
        for i in range(10):
            try:
                msg = ws.recv()
                data = json.loads(msg)
                print(f"Mensagem {i+1} recebida.")
                
                if isinstance(data, dict):
                    if data.get("type") == "raidData":
                        raids_list = data.get("data", {}).get("raids", [])
                        if raids_list:
                            for r in raids_list:
                                raids_data[r["idx"]] = r
                            print("Dados de raids capturados com sucesso!")
                            break
                    elif "raids" in data:
                        raids_list = data.get("raids", [])
                        if raids_list:
                            for r in raids_list:
                                raids_data[r["idx"]] = r
                            print("Dados de raids capturados com sucesso!")
                            break
            except Exception:
                break
                
        ws.close()
    except Exception as e:
        print(f"Erro na conexão: {e}")
        return

    if not raids_data:
        print("Aviso: Nenhuma lista de raids foi encontrada nas mensagens.")
        return

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
    print("Status do envio para o Discord:", res.status_code)

if __name__ == "__main__":
    main()
