import json
import socket
import sys
import os
from datetime import datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import requests
from websocket import create_connection

socket.setdefaulttimeout(4)
sys.stdout.reconfigure(line_buffering=True)

def main():
    print(f"[{datetime.now()}] 🔍 Varredura de Diagnóstico de Servidores iniciada...")
    ws_url = "wss://ws.raids.l2stuff.xyz/"
    ws_headers = {
        "Origin": "https://l2stuff.xyz",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    ws = None
    raw_data = None
    try:
        ws = create_connection(ws_url, header=ws_headers, timeout=4)
        ws.settimeout(4)
        for i in range(3):
            msg = ws.recv()
            if msg:
                parsed = json.loads(msg)
                if isinstance(parsed, dict):
                    raw_data = parsed
                    break
    except Exception as e:
        print(f"Aviso WebSocket: {e}")
    finally:
        if ws:
            try:
                ws.close()
            except:
                pass

    if not raw_data:
        print("Erro: Nenhum dado recebido do WebSocket.")
        return

    # Função para varrer e listar todos os servidores encontrados no JSON
    servers_found = {}
    def inspect_servers(obj):
        if isinstance(obj, dict):
            srv = obj.get("server", obj.get("server_id"))
            name = obj.get("name", obj.get("title"))
            if srv and name:
                if srv not in servers_found:
                    servers_found[srv] = []
                if name not in servers_found[srv]:
                    servers_found[srv].append(name)
            for v in obj.values():
                inspect_servers(v)
        elif isinstance(obj, list):
            for item in obj:
                inspect_servers(item)

    inspect_servers(raw_data)
    
    print("📋 Servidores e Bosses detectados na API:")
    for srv_id, bosses in servers_found.items():
        print(f"Server ID: [{srv_id}] -> Quantidade de bosses: {len(bosses)} (Ex: {bosses[:3]})")

if __name__ == "__main__":
    main()
