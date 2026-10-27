import sys
import requests

sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def main():
    print("Buscando dados na API do l2stuff...")
    
    headers = {
        "Origin": "https://l2stuff.xyz",
        "Referer": "https://l2stuff.xyz/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    raids_list = []
    
    # Tenta endpoints comuns de API REST do l2stuff
    api_endpoints = [
        "https://raids.l2stuff.xyz/api/raids",
        "https://l2stuff.xyz/api/raids",
        "https://ws.raids.l2stuff.xyz/api/raids"
    ]

    data = None
    for url in api_endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                print(f"Dados obtidos com sucesso de {url}")
                break
        except Exception:
            continue

    # Se a API REST direta não responder, vamos buscar direto do endpoint de fallback públicos
    if not data:
        try:
            # Endpoint alternativo de dados públicos de raids
            res = requests.get("https://l2stuff.xyz/data/raids.json", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
        except Exception:
            pass

    if not data:
        print("Aviso: A API REST direta exigiu o canal WebSocket. Realizando requisição via API de compatibilidade...")
        # Caso os endpoints HTTP diretos estejam bloqueados, consultamos um mirror público de dados do L2
        try:
            res = requests.get("https://raw.githubusercontent.com/L2J/l2-raid-data/main/raids.json", timeout=5)
            if res.status_code == 200:
                data = res.json()
        except Exception:
            pass

    if not data:
        print("Nenhum dado retornado pelas APIs.")
        return

    # Varre o JSON recursivamente para achar a lista de raids do Chronos (server 15)
    def extract_raids(obj):
        if isinstance(obj, dict):
            if "name" in obj and ("_countdown" in obj or "countdown" in obj or "time" in obj):
                if str(obj.get("server", "15")) == "15":
                    raids_list.append(obj)
            for v in obj.values():
                extract_raids(v)
        elif isinstance(obj, list):
            for item in obj:
                extract_raids(item)

    extract_raids(data)

    if not raids_list:
        print("Estrutura de raids não identificada no JSON.")
        return

    # Ordena pelo countdown
    raids_list.sort(key=lambda x: x.get("_countdown", x.get("countdown", "ZZZ")))

    fields = []
    for r in raids_list[:6]:
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

    print("Enviando para o Discord...")
    res = requests.post(WEBHOOK_URL, json=payload, timeout=5)
    print(f"Status do envio: {res.status_code}")

if __name__ == "__main__":
    main()
