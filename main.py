import sys
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1563375363760070729/8yyUbn3Z6F8Mb0ALwPN3Mh29gZ0AHbLLjof5Cb9Bnx_8is5UMqnRdZeLJ3Jv7fPy3LGN"
ROLE_TAG = "@Bosses"

def main():
    print("Buscando dados diretamente do l2stuff.xyz...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # Acessa a página principal do l2stuff
        response = requests.get("https://l2stuff.xyz/", headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Erro ao acessar o site: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Procura pelas tabelas de raid do Chronos baseada na estrutura HTML fornecida
        fields = []
        
        # Seleciona todas as tabelas de listagem de raids
        tables = soup.find_all('table', class_='raid-list')
        
        for table in tables:
            # Pega o título da categoria (ex: Field Raids, Golem Raids, etc.)
            header_tr = table.find('thead')
            category_name = "Raid"
            if header_tr:
                th_elem = header_tr.find_all('th')
                if len(th_elem) > 1:
                    category_name = th_elem[1].get_text(strip=True)

            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                th_row = row.find('th', scope='row')
                
                if th_row and len(cols) >= 2:
                    boss_name = th_row.get_text(strip=True)
                    countdown = cols[0].get_text(strip=True)
                    time_val = cols[1].get_text(strip=True)
                    
                    # Filtra apenas se tiver dados válidos
                    if boss_name and countdown.startswith('T'):
                        icon = "🔴" if "T+" in countdown else "🟢"
                        fields.append({
                            "name": f"{icon} {boss_name} ({category_name})",
                            "value": f"⏳ Respawn: `{countdown}` | Previsto: `{time_val}`",
                            "inline": False
                        })

    except Exception as e:
        print(f"Erro ao processar o HTML: {e}")
        return

    if not fields:
        print("Nenhum boss extraído do HTML.")
        return

    # Limita aos primeiros 6 bosses para não estourar o limite do embed do Discord
    embed = {
        "title": "⏰ LEMBRETE DE BOSSES (Chronos)",
        "description": "Atualização automática de rotina.",
        "color": 10038562,
        "fields": fields[:6]
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
