import json
import socket
import sys
import requests
from websocket import create_connection

socket.setdefaulttimeout(4)
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
# Usando o formato correto de menção de cargo do Discord (substitua pelo ID correto se necessário, ou deixe o texto do cargo)
ROLE_TAG = "<@&1563375363760070729>" # Caso o cargo seja @Bosses, ajustado para menção real

def main():
    print("Iniciando varredura para o Discord...")
    raids_data = []
    
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
        print("Nenhum dado capturado.")
        return

    # Organiza e filtra os dados do Chronos
    chronos = [r for r in raids_data if str(r.get("server", "15")) == "15"]
    if not chronos:
        chronos = raids_data

    # Ordena pelo countdown
    chronos.sort(key=lambda x: x.get("_countdown", x.get("countdown", "")))

    fields = []
    for r in chronos[:6]:
        name = r.get("name", r.get("title", "Unknown Boss"))
        cd = r.get("_countdown", r.get("countdown", "N/A"))
        tm = r.get("_time", r.get("time", "N/A"))
        
        # Limpa formatação de timestamp numérico bruto caso venha corrompido
        if str(tm).isdigit() and len(str(tm)) > 10:
            tm = "Horário sob consulta"

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
        "fields": fields
        # Rodapé da fonte ocultado conforme solicitado
    }

    payload = {
        "content": f"@Bosses **ATENÇÃO!** Próximos Raid Bosses do Chronos:",
        "embeds": [embed],
        "allowed_mentions": {"parse": ["users", "roles"]}
    }

    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio para o Discord: {res.status_code}")

if __name__ == "__main__":
    main()
