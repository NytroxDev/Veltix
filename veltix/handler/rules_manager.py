from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ..internal.events import MessageEvent

if TYPE_CHECKING:
    from ..network.request import Response
    from ..server.client_info import ClientInfo
    from .request_handler import RequestHandler


@dataclass
class MessageContext:
    response: Response
    handler: RequestHandler
    client: Optional[ClientInfo] = None
    is_server: bool = False


class RulesManager:
    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def process(self, context: MessageContext) -> bool:
        for rule in self._rules:
            if rule.try_handle(context):
                context.handler.bus.debug(
                    f"{rule.__class__.__name__} handling message type {context.response.type}"
                )
                return True
        context.handler.bus.emit(MessageEvent.UNHANDLED, {
            "type": context.response.type,
            "length": len(context.response.content),
            "source": "server" if context.is_server else "client",
        })
        context.handler.bus.debug(f"No rule matched for message type {context.response.type}")
        return False

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)


class Rule(ABC):
    @abstractmethod
    def can_handle(self, context: MessageContext) -> bool: ...

    @abstractmethod
    def handle(self, context: MessageContext) -> None: ...

    def try_handle(self, context: MessageContext) -> bool:
        if self.can_handle(context):
            self.handle(context)
            return True
        return False
