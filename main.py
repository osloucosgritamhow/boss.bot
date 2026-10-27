import json
import sys
import requests
from websocket import create_connection

sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def main():
    print("Conectando ao WebSocket oficial do l2stuff...")
    
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    raw_data = None
    ws = None
    try:
        ws = create_connection(ws_url, header=ws_headers, timeout=5)
        ws.settimeout(4)
        
        # Lê as mensagens iniciais da stream até capturar o payload de raids
        for i in range(5):
            msg = ws.recv()
            if not msg:
                continue
            
            parsed = json.loads(msg)
            # Verifica se o pacote contém dados de raids ou estrutura de servidores
            if isinstance(parsed, dict) and (("raids" in parsed) or ("data" in parsed) or ("chronos" in parsed)):
                raw_data = parsed
                print(f"Pacote de dados capturado na mensagem {i+1}!")
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
        print("Nenhum dado capturado do WebSocket.")
        return

    # Extração recursiva de todos os bosses da estrutura recebida
    raids_list = []
    def extract_raids(obj):
        if isinstance(obj, dict):
            # Identifica se o objeto é um boss válido pelo nome e countdown/tempo
            if "name" in obj and ("_countdown" in obj or "countdown" in obj or "_time" in obj or "time" in obj):
                raids_list.append(obj)
            for v in obj.values():
                extract_raids(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_raids(item)

    extract_raids(raw_data)

    if not raids_list:
        print("Nenhum boss extraído do JSON.")
        return

    # Filtra estritamente pelo servidor Chronos (server '15')
    chronos_bosses = [r for r in raids_list if str(r.get("server", "15")) == "15"]
    if not chronos_bosses:
        chronos_bosses = raids_list

    # Ordena pelo countdown mais próximo
    chronos_bosses.sort(key=lambda x: x.get("_countdown", x.get("countdown", "ZZZ")))

    fields = []
    for r in chronos_bosses[:6]:
        name = r.get("name", "Unknown Boss")
        cd = r.get("_countdown", r.get("countdown", "N/A"))
        tm = r.get("_time", r.get("time", "N/A"))
        
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

    print("Enviando dados para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio para o Discord: {res.status_code}")

if __name__ == "__main__":
    main()
