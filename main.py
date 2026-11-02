"""Raid alerts for Render cron. Use --dry-run to inspect without posting."""
import argparse
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from websocket import create_connection

UTC = timezone.utc
DISPLAY_TZ = ZoneInfo('America/Sao_Paulo')
SERVERS = {
    'chronos': ('WEBHOOK_CHRONOS', 'ROLE_ID_CHRONOS', '1285763435107319829'),
    'naia': ('WEBHOOK_NAIA', 'ROLE_ID_NAIA', '1328384446109323380'),
}
LOG = logging.getLogger('raids')


def fetch_snapshot():
    """Only accept the complete message, not a ping or partial update."""
    ws = create_connection('wss://ws.raids.l2stuff.xyz/',
                           origin='https://l2stuff.xyz', timeout=15)
    try:
        deadline = time.monotonic() + 30
        for _ in range(30):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ws.settimeout(min(remaining, 15))
            message = ws.recv()
            if not message:
                raise RuntimeError('WebSocket encerrado antes dos dados completos')
            try:
                data = json.loads(message)
            except (ValueError, TypeError):
                continue
            if isinstance(data, dict) and data.get('m') == 'all':
                snapshot = data.get('d')
                if not isinstance(snapshot, dict):
                    raise ValueError('Snapshot sem objeto d')
                for server in SERVERS:
                    if not isinstance(snapshot.get(server), dict) or not isinstance(snapshot[server].get('raids'), list):
                        raise ValueError(f'Snapshot sem lista raids de {server}')
                return snapshot
        raise RuntimeError('Snapshot m=all não recebido')
    finally:
        ws.close()


def spawn_time(raid, now, grace_seconds=0):
    """Fixed rules use UTC, as in the website; variable raids use epoch time."""
    earliest = now - timedelta(seconds=grace_seconds)
    if raid.get('fixedDuration', 0) > 0:
        if raid.get('fixedList'):
            candidates = []
            # JavaScript: Sunday=0. Python: Monday=0.
            for entry in raid['fixedList']:
                day, hour = int(entry[0]), int(entry[1])
                if not 0 <= day <= 6 or not 0 <= hour <= 23:
                    raise ValueError('Agenda semanal inválida')
                days = ((day - 1) % 7 - now.weekday()) % 7
                target = (now + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
                if target < earliest:
                    target += timedelta(days=7)
                candidates.append(target)
            return min(candidates)
        hour = int(raid['hour'])
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        return target + timedelta(days=1) if target < earliest else target
    value = float(raid['time'])
    if not math.isfinite(value) or value <= 0:
        raise ValueError('Timestamp inválido')
    return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, UTC)


def upcoming(snapshot, server, now):
    # Never traverse another server or fall back to a global search.
    seen = set()
    for raid in snapshot[server]['raids']:
        try:
            name = raid['name']
            if not isinstance(name, str) or not name.strip():
                raise ValueError('Nome inválido')
            target = spawn_time(raid, now, grace_seconds=120)
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            LOG.warning('[%s] Registro ignorado: %s', server, exc)
            continue
        identity = (name, target.timestamp())
        if target > now - timedelta(seconds=120) and identity not in seen:
            seen.add(identity)
            yield name, target


def alert_minutes(seconds, window=120):
    # Half-open windows: a job every 120 seconds has no 20-second gap.
    if -window < seconds <= 0:
        return 0
    for minutes in (10, 5):
        if minutes * 60 - window < seconds <= minutes * 60:
            return minutes
    return None


def payload_for(server, name, target, minutes, role):
    formatted_time = target.astimezone(DISPLAY_TZ).strftime("%d/%m/%Y %H:%M")
    name = name.replace('@', '@\u200b')[:200]
    if minutes == 0:
        return {
            'content': f'<@&{role}>',
            'allowed_mentions': {'parse': [], 'roles': [role]},
            'embeds': [{
                'title': f'⏳ BOSS: {name.upper()} ACABOU DE NASCER!',
                'description': f'**Horário de Spawn:** `{target.astimezone(DISPLAY_TZ):%d/%m/%Y %H:%M}`',
                'color': 15158332,
                'footer': {'text': 'AOG • RAID ALERT SYSTEM'},
            }],
        }
    return {
        'content': f'<@&{role}> **{name}** ({formatted_time}) nasce em {minutes} minutos.',
        'allowed_mentions': {'parse': [], 'roles': [role]},
        'embeds': [{
            'title': f'⏳ BOSS: {name.upper()} - {minutes} MINUTOS',
            'description': f'**Horário de Spawn:** `{formatted_time}`',
            'color': 16763904 if minutes == 10 else 15158332,
            'footer': {'text': 'AOG • RAID ALERT SYSTEM'},
        }],
    }


class AlertState:
    """Optional persistent Redis REST store; JSON fallback for local use."""
    def __init__(self):
        self.url = os.getenv('UPSTASH_REDIS_REST_URL', '').rstrip('/')
        self.token = os.getenv('UPSTASH_REDIS_REST_TOKEN', '')
        if bool(self.url) != bool(self.token):
            raise ValueError('Configure ambas as variáveis UPSTASH_REDIS_REST_*')
        self.path = Path(os.getenv('ALERT_STATE_FILE', 'sent_alerts.json'))
        self.data = {}
        if not self.url:
            LOG.warning('Estado em arquivo local: no Render Cron ele não persiste entre execuções. Use Redis REST para deduplicação durável.')
            if self.path.exists():
                self.data = json.loads(self.path.read_text())
            cutoff = time.time() - 8 * 86400
            self.data = {k: v for k, v in self.data.items() if isinstance(v, (int, float)) and v > cutoff}

    def command(self, *args):
        response = requests.post(self.url, headers={'Authorization': f'Bearer {self.token}'}, json=list(args), timeout=10)
        if not response.ok:
            raise RuntimeError(f'Falha no estado Redis: HTTP {response.status_code}')
        result = response.json()
        if 'error' in result:
            raise RuntimeError('Redis rejeitou comando de estado')
        return result['result']

    def contains(self, key):
        return bool(self.command('EXISTS', key)) if self.url else key in self.data

    def mark(self, key):
        if self.url:
            self.command('SET', key, 'sent', 'EX', 8 * 86400)
        else:
            self.data[key] = time.time()
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.data))
            temporary.replace(self.path)


def post_discord(url, payload):
    # Log status only: exception strings can contain the secret webhook URL.
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 429:
            LOG.error('Discord limitou envios (HTTP 429); alerta não marcado como enviado')
            return False
        if not 200 <= response.status_code < 300:
            LOG.error('Discord rejeitou envio: HTTP %s', response.status_code)
            return False
        return True
    except requests.RequestException as exc:
        LOG.error('Falha de conexão com Discord: %s', type(exc).__name__)
        return False


def run(snapshot, now, dry_run=False):
    configs = {}
    if not dry_run:
        for server, (webhook_env, role_env, default_role) in SERVERS.items():
            url = os.getenv(webhook_env, '')
            role = os.getenv(role_env, default_role)
            if not url.startswith('https://discord.com/api/webhooks/') or not role.isdigit():
                raise ValueError(f'Configure {webhook_env} e um ID numérico em {role_env}')
            configs[server] = (url, role)
    state = None if dry_run else AlertState()
    failed = False
    for server in SERVERS:
        raids = list(upcoming(snapshot, server, now))
        LOG.info('[%s] %d bosses para monitorar', server, len(raids))
        for name, target in raids:
            seconds = (target - now).total_seconds()
            minutes = alert_minutes(seconds)
            if dry_run:
                LOG.info('[%s] %s | Brasil %s | faltam %.1f min | alerta=%s', server, name,
                         target.astimezone(DISPLAY_TZ).strftime('%d/%m/%Y %H:%M'), seconds / 60, minutes)
                continue
            if minutes is None:
                continue
            key = 'raid-alert:' + hashlib.sha256(f'{server}|{name}|{target.timestamp()}|{minutes}'.encode()).hexdigest()
            if state.contains(key):
                LOG.info('[%s] Alerta já enviado: %s (%dm)', server, name, minutes)
                continue
            url, role = configs[server]
            if post_discord(url, payload_for(server, name, target, minutes, role)):
                state.mark(key)
                LOG.info('[%s] Enviado: %s (%dm)', server, name, minutes)
            else:
                failed = True
    if failed:
        raise RuntimeError('Um ou mais alertas falharam; consulte os status acima')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Consulta e calcula sem enviar ao Discord')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    try:
        snapshot = fetch_snapshot()
        run(snapshot, datetime.now(UTC), dry_run=args.dry_run)
    except Exception as exc:
        # Avoid exposing credential-bearing URLs in requests/websocket exceptions.
        LOG.error('Execução falhou (%s). Verifique conexão, dados e variáveis de ambiente.', type(exc).__name__)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
