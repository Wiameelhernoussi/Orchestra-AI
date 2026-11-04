from __future__ import annotations

import socket

import httpx
import pytest

from app.services.evidence_facts import (
    MAX_RESPONSE_BYTES,
    EvidenceFactChecker,
    _PinnedHTTPSConnection,
)


def _resolver_for(ip: str = "8.8.8.8"):
    def resolve(host, port, *, type):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))
        ]

    return resolve


def _checker(handler, resolver=None):
    return EvidenceFactChecker(
        http_client=httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            trust_env=False,
        ),
        resolver=resolver or _resolver_for(),
    )


def test_rejects_non_https_and_private_ip_without_request():
    calls = []
    checker = _checker(
        lambda request: calls.append(request) or httpx.Response(200),
        resolver=_resolver_for("127.0.0.1"),
    )
    try:
        non_https = checker.check_link("http://example.test")
        private_dns = checker.check_link("https://example.test")
    finally:
        checker.close()

    assert non_https["result"] == "blocked"
    assert "HTTPS" in non_https["reason"]
    assert private_dns["result"] == "blocked"
    assert "Private" in private_dns["reason"]
    assert calls == []


def test_rejects_private_address_in_mixed_dns_answers():
    calls = []

    def resolve(host, port, *, type):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", port)),
        ]

    checker = _checker(
        lambda request: calls.append(request) or httpx.Response(200),
        resolver=resolve,
    )
    try:
        fact = checker.check_link("https://example.test")
    finally:
        checker.close()

    assert fact["result"] == "blocked"
    assert calls == []


def test_rejects_redirect_to_private_host_without_requesting_target():
    requested_urls = []

    def respond(request):
        requested_urls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://127.0.0.1/admin"})

    checker = _checker(respond)
    try:
        fact = checker.check_link("https://example.test/start")
    finally:
        checker.close()

    assert fact["result"] == "blocked"
    assert requested_urls == ["https://example.test/start"]


def test_rejects_responses_larger_than_limit():
    checker = _checker(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"x" * (MAX_RESPONSE_BYTES + 1),
        )
    )
    try:
        fact = checker.check_link("https://example.test")
    finally:
        checker.close()

    assert fact["result"] == "blocked"
    assert "size limit" in fact["reason"]


def test_extracts_page_title_and_public_github_facts():
    requested_urls = []

    def respond(request):
        requested_urls.append(str(request.url))
        if request.url.host == "github.com":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<html><title>Project home</title></html>",
            )
        if request.url.path == "/repos/acme/demo":
            return httpx.Response(200, json={"full_name": "acme/demo"})
        if request.url.path == "/repos/acme/demo/contents":
            return httpx.Response(200, json=[{"name": "README.md"}, {"name": "src"}])
        raise AssertionError(f"Unexpected URL: {request.url}")

    checker = _checker(respond)
    try:
        fact = checker.check_link("https://github.com/acme/demo")
    finally:
        checker.close()

    assert fact["result"] == "checked"
    assert fact["title"] == "Project home"
    assert fact["github_repo_exists"] is True
    files = {item["name"]: item["present"] for item in fact["github_expected_files"]}
    assert files["README.md"] is True
    assert files["package.json"] is False
    assert requested_urls == [
        "https://github.com/acme/demo",
        "https://api.github.com/repos/acme/demo",
        "https://api.github.com/repos/acme/demo/contents",
    ]


def test_github_rate_limit_is_not_reported_as_missing_repository():
    def respond(request):
        if request.url.host == "github.com":
            return httpx.Response(200, headers={"content-type": "text/html"})
        return httpx.Response(403, json={"message": "API rate limit exceeded"})

    checker = _checker(respond)
    try:
        fact = checker.check_link("https://github.com/acme/demo")
    finally:
        checker.close()

    assert fact["github_repo_exists"] is None
    assert fact["github_expected_files"] == []


def test_pinned_connection_uses_validated_ip_but_keeps_hostname_for_tls(monkeypatch):
    calls = {}

    class FakeContext:
        def wrap_socket(self, sock, *, server_hostname):
            calls["server_hostname"] = server_hostname
            return sock

    monkeypatch.setattr("app.services.evidence_facts.ssl.create_default_context", FakeContext)
    monkeypatch.setattr(
        "app.services.evidence_facts.socket.create_connection",
        lambda address, timeout: calls.update(address=address, timeout=timeout) or object(),
    )
    connection = _PinnedHTTPSConnection(
        "example.test",
        "8.8.8.8",
        port=443,
        timeout=1.5,
    )
    connection.connect()

    assert calls["address"] == ("8.8.8.8", 443)
    assert calls["server_hostname"] == "example.test"
    assert calls["timeout"] == 1.5
