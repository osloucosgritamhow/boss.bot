import json
import socket
import sys
import requests
from websocket import create_connection

socket.setdefaulttimeout(3)
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def main():
    print("Iniciando varredura limpa do WebSocket...")
    raids_data = {}
    
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    ws = None
    try:
        print("Conectando ao WebSocket...")
        ws = create_connection(ws_url, header=ws_headers, timeout=3)
        ws.settimeout(3)
        
        print("Aguardando pacote de dados...")
        # Tenta ler as primeiras mensagens até achar a estrutura de raids
        for i in range(5):
            msg = ws.recv()
            if not msg:
                continue
            
            data = json.loads(msg)
            print(f"Mensagem {i+1} recebida do servidor.")
            
            # O payload costuma vir em data -> raids ou dentro de chaves específicas por servidor
            if isinstance(data, dict):
                # Varre se existe a chave 'data' ou se os raids estão direto
                root_container = data.get("data", data)
                
                # Se o payload contém dicionário de servidores ou lista direta de raids
                if "raids" in root_container:
                    r_list = root_container["raids"]
                    for r in r_list:
                        raids_data[r.get("idx")] = r
                elif "chronos" in root_container:
                    r_list = root_container["chronos"].get("raids", [])
                    for r in r_list:
                        raids_data[r.get("idx")] = r
                
                # Se achou algum raid, interrompe a leitura
                if raids_data:
                    print("Pacote de raids identificado com sucesso!")
                    break
                    
    except Exception as e:
        print(f"Aviso na execução do WebSocket: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    # Fallback se os dados vierem em outro formato de chave aninhada
    if not raids_data:
        print("Nenhum dado capturado na estrutura padrão. Encerrando com segurança.")
        return

    print(f"Total de raids brutos capturados: {len(raids_data)}")
    
    # Filtra estritamente pelo servidor Chronos (server == 15 ou string '15')
    chronos = [r for r in raids_data.values() if str(r.get("server", "15")) == "15"]
    
    # Ordena pelo countdown / tempo
    chronos.sort(key=lambda x: x.get("_countdown", x.get("time", "")))

    if not chronos:
        print("Nenhum boss do servidor Chronos encontrado no lote.")
        return

    fields = []
    for r in chronos[:5]:
        cd = r.get("_countdown", r.get("countdown", "N/A"))
        tm = r.get("_time", r.get("time", "N/A"))
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

    print("Enviando dados para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio para o Discord: {res.status_code}")

if __name__ == "__main__":
    main()
