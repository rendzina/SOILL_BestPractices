"""Derive visitor metadata from Chainlit session / WSGI environ (for logging)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ClientMetadata:
    """Identifiers for a chat client (browser session or CLI)."""

    thread_id: str
    session_id: str
    visitor_fingerprint: str
    client_ip: str
    user_agent: str
    client_type: str

    @staticmethod
    def anonymous() -> ClientMetadata:
        return ClientMetadata(
            thread_id='anonymous',
            session_id='anonymous',
            visitor_fingerprint=_hash_parts('unknown', 'unknown'),
            client_ip='',
            user_agent='',
            client_type='unknown',
        )


def _hash_parts(*parts: str) -> str:
    payload = '|'.join((part or '').strip() for part in parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _client_ip(environ: dict[str, Any]) -> str:
    forwarded = environ.get('HTTP_X_FORWARDED_FOR') or environ.get('X-Forwarded-For')
    if forwarded:
        return str(forwarded).split(',')[0].strip()
    for key in ('REMOTE_ADDR', 'HTTP_X_REAL_IP', 'CLIENT_IP'):
        value = environ.get(key)
        if value:
            return str(value).strip()
    return ''


def _user_agent(environ: dict[str, Any]) -> str:
    return str(environ.get('HTTP_USER_AGENT') or '')[:512]


def metadata_from_environ(
    *,
    thread_id: str,
    session_id: str,
    environ: Optional[dict[str, Any]],
    client_type: str = 'webapp',
) -> ClientMetadata:
    """Build metadata from WSGI environ (IP, User-Agent) and Chainlit session ids."""
    env = environ or {}
    ip = _client_ip(env)
    ua = _user_agent(env)
    return ClientMetadata(
        thread_id=thread_id or session_id or 'anonymous',
        session_id=session_id or thread_id or 'anonymous',
        visitor_fingerprint=_hash_parts(ip, ua),
        client_ip=ip,
        user_agent=ua,
        client_type=client_type or 'webapp',
    )


def metadata_from_chainlit() -> ClientMetadata:
    """Read client metadata from the active Chainlit request context."""
    try:
        from chainlit.context import context

        ctx = context.get()
        session = ctx.session
        thread_id = str(getattr(session, 'thread_id', '') or getattr(session, 'id', ''))
        session_id = str(getattr(session, 'id', '') or thread_id)
        environ = getattr(session, 'environ', None)
        client_type = str(getattr(session, 'client_type', 'webapp') or 'webapp')
        return metadata_from_environ(
            thread_id=thread_id,
            session_id=session_id,
            environ=environ if isinstance(environ, dict) else None,
            client_type=client_type,
        )
    except Exception:
        return ClientMetadata.anonymous()


def metadata_for_cli() -> ClientMetadata:
    """Stable metadata for the terminal chat interface."""
    return ClientMetadata(
        thread_id='cli-local',
        session_id='cli-local',
        visitor_fingerprint=_hash_parts('cli', 'cli'),
        client_ip='',
        user_agent='SOILL-chat-cli',
        client_type='cli',
    )
