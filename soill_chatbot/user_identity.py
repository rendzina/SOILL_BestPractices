"""
Derive client metadata from Chainlit session or WSGI environ (for conversation logging).

Chainlit 2.x: use get_context().session — not context.get() (that API does not exist).
visitor_fingerprint is SHA-256(client_ip|user_agent) for coarse analytics only;
chat history is keyed by thread_id, not by fingerprint.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


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
        """Fallback when Chainlit context is unavailable (e.g. outside a handler)."""
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
        from chainlit.context import get_context

        session = get_context().session
        thread_id = str(session.thread_id or session.id)
        session_id = str(session.id or thread_id)
        environ = session.environ
        client_type = str(session.client_type or 'webapp')
        return metadata_from_environ(
            thread_id=thread_id,
            session_id=session_id,
            environ=environ if isinstance(environ, dict) else None,
            client_type=client_type,
        )
    except Exception as exc:
        logger.warning('Could not read Chainlit session metadata: %s', exc)
        return ClientMetadata.anonymous()


def metadata_to_dict(meta: ClientMetadata) -> dict[str, str]:
    """Serialise for Chainlit user_session (JSON-friendly)."""
    return asdict(meta)


def coerce_client_metadata(
    value: Union[ClientMetadata, dict[str, Any], None],
) -> ClientMetadata:
    """Normalise metadata from user_session or logging callers."""
    if value is None:
        return ClientMetadata.anonymous()
    if isinstance(value, ClientMetadata):
        return value
    if isinstance(value, dict):
        return ClientMetadata(
            thread_id=str(value.get('thread_id') or value.get('session_id') or 'anonymous'),
            session_id=str(value.get('session_id') or value.get('thread_id') or 'anonymous'),
            visitor_fingerprint=str(
                value.get('visitor_fingerprint') or _hash_parts('unknown', 'unknown')
            ),
            client_ip=str(value.get('client_ip') or ''),
            user_agent=str(value.get('user_agent') or ''),
            client_type=str(value.get('client_type') or 'webapp'),
        )
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
