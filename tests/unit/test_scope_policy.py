import socket

import pytest

from tester.blackbox.policy import ScopeError, ScopePolicy


def test_dns_with_any_private_answer_is_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(ScopeError, match="DNS"):
        ScopePolicy(("https://example.test",)).prepare()


def test_public_host_is_pinned_and_scope_remains_exact(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.215.14", 443)),
    ])
    policy = ScopePolicy(("https://example.test",))
    policy.prepare()
    assert "MAP example.test 93.184.215.14" in policy.chromium_rules()
    assert policy.check("https://example.test/docs") == "https://example.test/docs"
    with pytest.raises(ScopeError):
        policy.check("https://example.test:444/docs")
    with pytest.raises(ScopeError):
        policy.check("https://example.test/delete")
    with pytest.raises(ScopeError):
        policy.check("https://example.test/docs?mode=edit", navigation=True)
