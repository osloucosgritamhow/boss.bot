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
    print("Iniciando captura otimizada...")
    raids_data = []
    
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    ws = None
    try:
        print("Conectando ao WebSocket...")
        ws = create_connection(ws_url, header=ws_headers, timeout=4)
        ws.settimeout(4)
        
        print("Lendo pacotes do servidor...")
        for i in range(4):
            msg = ws.recv()
            if not msg:
                continue
            
            data = json.loads(msg)
            print(f"Mensagem {i+1} processada.")
            
            # Função recursiva para buscar qualquer lista de raids dentro do JSON
            def find_raids(obj):
                if isinstance(obj, dict):
                    if "raids" in obj and isinstance(obj["raids"], list):
                        raids_data.extend(obj["raids"])
                    for k, v in obj.items():
                        find_raids(v)
                elif isinstance(obj, list):
                    for item in obj:
                        find_raids(item)

            find_raids(data)
            if raids_data:
                print(f"Encontrados {len(raids_data)} raids nos pacotes!")
                break
                
    except Exception as e:
        print(f"Aviso na leitura: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    if not raids_data:
        print("Nenhum dado de raid capturado.")
        return

    # Filtra por Chronos (servidor 15 ou string relacionada)
    chronos = [r for r in raids_data if str(r.get("server", "15")) == "15"]
    
    if not chronos:
        # Se o filtro estrito não achar, usa todos os capturados para garantir envio
        chronos = raids_data

    chronos.sort(key=lambda x: x.get("_countdown", x.get("countdown", "")))

    fields = []
    for r in chronos[:5]:
        cd = r.get("_countdown", r.get("countdown", "N/A"))
        tm = r.get("_time", r.get("time", "N/A"))
        name = r.get("name", r.get("title", "Unknown Boss"))
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

    print("Enviando dados para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio para o Discord: {res.status_code}")

if __name__ == "__main__":
    main()
