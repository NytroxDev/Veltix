"""Direct unit tests for Rule classes, RulesManager, and ALL_RULES."""

import socket
from unittest.mock import MagicMock

from veltix.handler.rules import (
    ALL_RULES,
    OnRecvRule,
    PendingRequestRule,
    PingRule,
    RouteRule,
    UnhandledRule,
)
from veltix.handler.rules_manager import MessageContext, RulesManager
from veltix.network.request import Response
from veltix.network.system_types import PING
from veltix.network.types import MessageType


def make_context(
    msg_type=None,
    content=b"",
    is_server=False,
    has_route=False,
    has_on_recv=False,
    handler=None,
    request_id=b"\x00" * 4,
):
    """Helper to create a MessageContext for testing."""
    if msg_type is None:
        msg_type = MessageType(code=9900, name="test_rule_type")
    response = Response(type=msg_type, content=content, _hash=b"\x00" * 4, _request_id=request_id)

    if handler is None:
        handler = MagicMock()
        handler.is_server = is_server
        handler.sender = MagicMock()
        handler.has_route = MagicMock(return_value=has_route)
        handler.get_route = MagicMock(return_value=lambda c, r: None)
        handler._executor = MagicMock()
        handler.on_recv = (lambda c, r: None) if has_on_recv else None
        handler.pending_requests = {}
        handler.pending_requests_lock = MagicMock()
        handler.handshake_handler = MagicMock()

    return MessageContext(response=response, handler=handler, is_server=is_server)


class TestPingRule:
    def test_can_handle_ping(self):
        rule = PingRule()
        ctx = make_context(msg_type=PING)
        assert rule.can_handle(ctx) is True

    def test_cannot_handle_non_ping(self):
        rule = PingRule()
        ctx = make_context()
        assert rule.can_handle(ctx) is False

    def test_handle_sends_pong_server(self):
        rule = PingRule()
        handler = MagicMock()
        handler.is_server = True
        handler.sender = MagicMock()
        from veltix.server.client_info import ClientInfo

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = ClientInfo(conn=sock, addr=("127.0.0.1", 9999), thread_id=1)
        ctx = make_context(
            msg_type=PING, is_server=True, handler=handler, request_id=b"\x01\x02\x03\x04"
        )
        ctx.client = client
        rule.handle(ctx)
        handler.sender.send.assert_called_once()

    def test_handle_sends_pong_client(self):
        rule = PingRule()
        handler = MagicMock()
        handler.is_server = False
        handler.sender = MagicMock()
        ctx = make_context(msg_type=PING, is_server=False, handler=handler)
        rule.handle(ctx)
        handler.sender.send.assert_called_once()

    def test_try_handle_returns_true_for_ping(self):
        rule = PingRule()
        ctx = make_context(msg_type=PING)
        assert rule.try_handle(ctx) is True

    def test_try_handle_returns_false_for_non_ping(self):
        rule = PingRule()
        ctx = make_context()
        assert rule.try_handle(ctx) is False


class TestPendingRequestRule:
    def test_can_handle_returns_false(self):
        rule = PendingRequestRule()
        ctx = make_context()
        assert rule.can_handle(ctx) is False

    def test_try_handle_with_matching_request(self):
        rule = PendingRequestRule()
        handler = MagicMock()
        handler.pending_requests = {}
        handler.pending_requests_lock = MagicMock()
        request_id = b"\xaa\xbb\xcc\xdd"
        from queue import Queue

        q = Queue()
        handler.pending_requests[request_id] = q

        ctx = make_context(handler=handler, request_id=request_id)
        result = rule.try_handle(ctx)
        assert result is True
        assert not q.empty()
        assert q.get().content == b""

    def test_try_handle_without_matching_request(self):
        rule = PendingRequestRule()
        handler = MagicMock()
        handler.pending_requests = {}
        handler.pending_requests_lock = MagicMock()
        ctx = make_context(handler=handler, request_id=b"\xde\xad\xbe\xef")
        result = rule.try_handle(ctx)
        assert result is False


class TestRouteRule:
    def test_can_handle_with_route(self):
        rule = RouteRule()
        ctx = make_context(has_route=True)
        assert rule.can_handle(ctx) is True

    def test_can_handle_without_route(self):
        rule = RouteRule()
        ctx = make_context(has_route=False)
        assert rule.can_handle(ctx) is False

    def test_handle_dispatches_to_route_server(self):
        rule = RouteRule()
        handler = MagicMock()
        handler.is_server = True
        handler._executor = MagicMock()
        handler.get_route = MagicMock(return_value=lambda c, r: None)
        ctx = make_context(handler=handler, is_server=True, has_route=True)
        rule.handle(ctx)
        handler._executor.submit.assert_called_once()

    def test_handle_dispatches_to_route_client(self):
        rule = RouteRule()
        handler = MagicMock()
        handler.is_server = False
        handler._executor = MagicMock()
        handler.get_route = MagicMock(return_value=lambda c, r: None)
        ctx = make_context(handler=handler, is_server=False, has_route=True)
        rule.handle(ctx)
        handler._executor.submit.assert_called_once()


class TestOnRecvRule:
    def test_can_handle_with_on_recv(self):
        rule = OnRecvRule()
        ctx = make_context(has_on_recv=True)
        assert rule.can_handle(ctx) is True

    def test_can_handle_without_on_recv(self):
        rule = OnRecvRule()
        ctx = make_context(has_on_recv=False)
        assert rule.can_handle(ctx) is False

    def test_handle_dispatches_to_on_recv(self):
        rule = OnRecvRule()
        handler = MagicMock()
        handler._executor = MagicMock()
        handler.on_recv = MagicMock()
        ctx = make_context(handler=handler, has_on_recv=True)
        rule.handle(ctx)
        handler._executor.submit.assert_called_once()


class TestUnhandledRule:
    def test_can_handle_always_true(self):
        rule = UnhandledRule()
        ctx = make_context()
        assert rule.can_handle(ctx) is True

    def test_handle_does_not_raise(self):
        rule = UnhandledRule()
        ctx = make_context(is_server=True)
        rule.handle(ctx)  # should not raise


class TestRulesManager:
    def test_empty_manager_returns_false(self):
        mgr = RulesManager()
        ctx = make_context(is_server=False)
        assert mgr.process(ctx) is False

    def test_add_rule_and_process(self):
        mgr = RulesManager()
        rule = UnhandledRule()
        mgr.add_rule(rule)

        ctx = make_context(is_server=False)
        assert mgr.process(ctx) is True

    def test_process_with_matching_rule(self):
        mgr = RulesManager()
        rule = PingRule()
        mgr.add_rule(rule)

        ctx = make_context(msg_type=PING)
        assert mgr.process(ctx) is True

    def test_process_without_matching_rule(self):
        mgr = RulesManager()
        rule = PingRule()
        mgr.add_rule(rule)

        ctx = make_context()
        assert mgr.process(ctx) is False


class TestAllRules:
    def test_all_rules_is_list(self):
        assert isinstance(ALL_RULES, list)

    def test_all_rules_has_correct_count(self):
        assert len(ALL_RULES) == 5

    def test_all_rules_contains_all_rule_types(self):
        types_in_all = [type(r).__name__ for r in ALL_RULES]
        assert "PingRule" in types_in_all
        assert "PendingRequestRule" in types_in_all
        assert "RouteRule" in types_in_all
        assert "OnRecvRule" in types_in_all
        assert "UnhandledRule" in types_in_all

    def test_all_rules_ordered_correctly(self):
        """Rules order matters: Ping -> Pending -> Route -> OnRecv -> Unhandled."""
        assert isinstance(ALL_RULES[0], PingRule)
        assert isinstance(ALL_RULES[1], PendingRequestRule)
        assert isinstance(ALL_RULES[2], RouteRule)
        assert isinstance(ALL_RULES[3], OnRecvRule)
        assert isinstance(ALL_RULES[4], UnhandledRule)
