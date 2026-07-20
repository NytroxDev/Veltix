from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..network.response import Response
    from ..server.client_info import ClientInfo
    from .request_handler import RequestHandler


@dataclass
class MessageContext:
    """Context object passed through the rule chain during message processing.

    Attributes:
        response: The received message.
        handler: The request handler owning the routes and executor.
        client: The sending client (server-side only, ``None`` on client).
        is_server: True if the message is being processed by a server.
    """

    response: Response
    handler: RequestHandler
    client: Optional[ClientInfo] = None
    is_server: bool = False


class RulesManager:
    """Ordered chain of :class:`Rule` instances that process incoming messages.

    Rules are evaluated in insertion order; the first rule whose
    ``can_handle`` returns ``True`` gets to handle the message.
    """

    def __init__(self) -> None:
        """Initialise an empty rule chain."""
        self._rules: list[Rule] = []

    def process(self, context: MessageContext) -> bool:
        """Run the rule chain on *context* until one rule handles the message.

        Args:
            context: The message context to process.

        Returns:
            True if a rule handled the message, False if none matched.
        """
        for rule in self._rules:
            if rule.try_handle(context):
                context.handler.bus.debug(
                    f"{rule.__class__.__name__} handling message type {context.response.type}"
                )
                return True
        context.handler.bus.debug(f"No rule matched for message type {context.response.type}")
        return False

    def add_rule(self, rule: Rule) -> None:
        """Append a rule to the end of the chain.

        Args:
            rule: The rule to add.
        """
        self._rules.append(rule)


class Rule(ABC):
    """Base class for message-processing rules.

    Subclasses implement :meth:`can_handle` to decide whether they apply
    and :meth:`handle` to execute the corresponding logic.
    """

    @abstractmethod
    def can_handle(self, context: MessageContext) -> bool:
        """Return True if this rule should handle the given message.

        Args:
            context: The message context to evaluate.

        Returns:
            True if this rule can handle the message.
        """
        ...

    @abstractmethod
    def handle(self, context: MessageContext) -> None:
        """Execute this rule's logic for the given message.

        Args:
            context: The message context to handle.
        """
        ...

    def try_handle(self, context: MessageContext) -> bool:
        """Evaluate and, if applicable, handle the message.

        Args:
            context: The message context to process.

        Returns:
            True if the rule handled the message, False otherwise.
        """
        if self.can_handle(context):
            self.handle(context)
            return True
        return False
