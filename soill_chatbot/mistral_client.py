"""Mistral SDK imports compatible with mistralai 1.x and 2.x."""

from __future__ import annotations

try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral

try:
    from mistralai.models import AssistantMessage, SystemMessage, UserMessage
except ImportError:
    from mistralai.client.models.assistantmessage import AssistantMessage
    from mistralai.client.models.systemmessage import SystemMessage
    from mistralai.client.models.usermessage import UserMessage

__all__ = ['Mistral', 'AssistantMessage', 'SystemMessage', 'UserMessage']
