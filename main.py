import json
import socket
import sys
import requests
from websocket import create_connection

socket.setdefaulttimeout(4)
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def main():
    print("Iniciando captura correta dos bosses...")
    raids_list = []
    
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    ws = None
    try:
        ws = create_connection(ws_url, header=ws_headers, timeout=4)
        ws.settimeout(4)
        
        for i in range(4):
            msg = ws.recv()
            if not msg:
                continue
            
            data = json.loads(msg)
            if isinstance(data, dict):
                # Procura diretamente onde o site armazena os raids do chronos ou na lista geral
                root = data.get("data", data)
                if "chronos" in root and isinstance(root["chronos"], dict):
                    raids_list = root["chronos"].get("raids", [])
                elif "raids" in root and isinstance(root["raids"], list):
                    raids_list = root["raids"]
                else:
                    # Varre recursivamente se necessário
                    def extract_all(obj):
                        if isinstance(obj, dict):
                            if "idx" in obj and "name" in obj:
                                raids_list.append(obj)
                            for v in obj.values():
                                extract_all(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                extract_all(item)
                    extract_all(data)
            
            if raids_list:
                break
    except Exception as e:
        print(f"Erro na conexão: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    if not raids_list:
        print("Nenhum boss encontrado.")
        return

    # Filtra rigorosamente pelo servidor Chronos (server 15) e remove itens inválidos
    chronos = [r for r in raids_list if str(r.get("server", "15")) == "15" and r.get("name")]
    
    # Ordena pelo countdown (priorizando os mais próximos)
    chronos.sort(key=lambda x: x.get("_countdown", x.get("countdown", "ZZZ")))

    fields = []
    for r in chronos[:6]:
        name = r.get("name", "Unknown Boss")
        cd = r.get("_countdown", r.get("countdown", "N/A"))
        tm = r.get("_time", r.get("time", "N/A"))
        
        # Formatação do ícone baseada no status do countdown
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
        "fields": fields
    }

    payload = {
        "content": f"{ROLE_TAG} **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["roles"]}
    }

    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio: {res.status_code}")

if __name__ == "__main__":
    main()
