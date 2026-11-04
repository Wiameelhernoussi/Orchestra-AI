from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import quote, urljoin, urlsplit

import httpx


MAX_RESPONSE_BYTES = 256 * 1024
MAX_REDIRECTS = 3
EXPECTED_GITHUB_ROOT_FILES = (
    "README.md",
    "package.json",
    "pyproject.toml",
    "index.html",
)


class _PageTitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_title = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(" ".join(self._parts).split())[:300]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        hostname: str,
        address: str,
        *,
        port: int,
        timeout: float,
    ) -> None:
        super().__init__(
            hostname,
            port=port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._pinned_address = address

    def connect(self) -> None:
        sock = socket.create_connection(
            (self._pinned_address, self.port),
            self.timeout,
        )
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class EvidenceFactChecker:
    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        resolver: Callable[..., list[tuple[Any, ...]]] = socket.getaddrinfo,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._http = http_client
        self._timeout_seconds = timeout_seconds
        self._resolver = resolver

    def close(self) -> None:
        if self._http is not None:
            self._http.close()

    def check_links(self, links: list[str]) -> list[dict[str, Any]]:
        return [self.check_link(link) for link in links]

    def check_link(self, raw_url: str) -> dict[str, Any]:
        fact: dict[str, Any] = {
            "url": raw_url,
            "https": False,
            "http_status": None,
            "title": None,
            "result": "unavailable",
            "reason": "",
            "github_repo_exists": None,
            "github_expected_files": [],
        }
        try:
            response, final_url = self._get_public_url(raw_url)
            fact["https"] = True
            fact["http_status"] = response.status_code
            fact["result"] = "checked"
            fact["reason"] = (
                "HTTP response received."
                if 200 <= response.status_code < 400
                else "The page returned a non-success HTTP status."
            )
            fact["title"] = self._page_title(response)
            github = self._check_github_repo(final_url)
            if github is not None:
                fact.update(github)
        except _BlockedURL as exc:
            fact.update(result="blocked", reason=str(exc))
        except (
            http.client.HTTPException,
            httpx.HTTPError,
            OSError,
            UnicodeError,
            ValueError,
        ) as exc:
            fact.update(
                result="unavailable",
                reason=f"Link check failed ({type(exc).__name__}).",
            )
        return fact

    def _get_public_url(self, url: str) -> tuple[httpx.Response, str]:
        current = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            parsed, address = self._validate_public_https_url(current)
            response = self._request_bounded(current, parsed, address)
            if response.status_code not in {301, 302, 303, 307, 308}:
                return response, current
            location = response.headers.get("location")
            if not location or redirect_count == MAX_REDIRECTS:
                raise _BlockedURL("Redirect limit reached or Location is missing.")
            current = urljoin(current, location)
            self._validate_public_https_url(current)
        raise _BlockedURL("Redirect limit reached.")

    def _validate_public_https_url(self, url: str):
        parsed = urlsplit(url)
        if parsed.scheme.casefold() != "https":
            raise _BlockedURL("Only HTTPS links are checked.")
        if not parsed.hostname or parsed.username or parsed.password:
            raise _BlockedURL("URL host is missing or contains credentials.")
        if parsed.port not in (None, 443):
            raise _BlockedURL("Only the standard HTTPS port is checked.")
        hostname = parsed.hostname.rstrip(".").casefold()
        try:
            addresses = [ipaddress.ip_address(hostname)]
        except ValueError:
            try:
                records = self._resolver(
                    hostname,
                    parsed.port or 443,
                    type=socket.SOCK_STREAM,
                )
            except (OSError, socket.gaierror) as exc:
                raise _BlockedURL("Hostname could not be resolved.") from exc
            addresses = [
                ipaddress.ip_address(record[4][0].split("%", 1)[0])
                for record in records
                if record and len(record) > 4 and record[4]
            ]
        if not addresses:
            raise _BlockedURL("Hostname did not resolve to an address.")
        if any(not address.is_global for address in addresses):
            raise _BlockedURL("Private, loopback, link-local, or reserved IP is blocked.")
        return parsed, str(addresses[0])

    def _request_bounded(
        self,
        url: str,
        parsed_url,
        address: str,
    ) -> httpx.Response:
        if self._http is not None:
            with self._http.stream(
                "GET",
                url,
                headers={
                    "Accept": "text/html,application/json;q=0.9,*/*;q=0.1",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                body = self._bounded_body(response.iter_bytes())
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=body,
                )

        connection = _PinnedHTTPSConnection(
            parsed_url.hostname,
            address,
            port=parsed_url.port or 443,
            timeout=self._timeout_seconds,
        )
        try:
            target = parsed_url.path or "/"
            if parsed_url.query:
                target = f"{target}?{parsed_url.query}"
            connection.request(
                "GET",
                target,
                headers={
                    "Accept": "text/html,application/json;q=0.9,*/*;q=0.1",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            body = self._bounded_body(
                iter(lambda: response.read(64 * 1024), b"")
            )
            return httpx.Response(
                status_code=response.status,
                headers=response.getheaders(),
                content=body,
            )
        finally:
            connection.close()

    @staticmethod
    def _bounded_body(chunks) -> bytes:
        body: list[bytes] = []
        total = 0
        for chunk in chunks:
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise _BlockedURL("Response exceeded the size limit.")
            body.append(chunk)
        return b"".join(body)

    @staticmethod
    def _page_title(response: httpx.Response) -> str | None:
        content_type = response.headers.get("content-type", "").casefold()
        if "html" not in content_type or not response.content:
            return None
        parser = _PageTitleParser()
        parser.feed(response.content.decode("utf-8", errors="replace"))
        return parser.title or None

    def _check_github_repo(self, url: str) -> dict[str, Any] | None:
        parsed = urlsplit(url)
        if parsed.hostname != "github.com":
            return None
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            return {
                "github_repo_exists": False,
                "github_expected_files": [
                    {"name": name, "present": False}
                    for name in EXPECTED_GITHUB_ROOT_FILES
                ],
            }
        owner, repository = (quote(part, safe="") for part in parts[:2])
        api_base = f"https://api.github.com/repos/{owner}/{repository}"
        repo_response, _ = self._get_public_url(api_base)
        if repo_response.status_code == 404:
            return {
                "github_repo_exists": False,
                "github_expected_files": [
                    {"name": name, "present": False}
                    for name in EXPECTED_GITHUB_ROOT_FILES
                ],
            }
        if repo_response.status_code != 200:
            return {
                "github_repo_exists": None,
                "github_expected_files": [],
            }
        contents_response, _ = self._get_public_url(f"{api_base}/contents")
        if contents_response.status_code != 200:
            return {
                "github_repo_exists": True,
                "github_expected_files": [],
            }
        try:
            contents = contents_response.json()
        except json.JSONDecodeError:
            contents = []
        present = {
            item.get("name")
            for item in contents
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        } if isinstance(contents, list) else set()
        return {
            "github_repo_exists": True,
            "github_expected_files": [
                {"name": name, "present": name in present}
                for name in EXPECTED_GITHUB_ROOT_FILES
            ],
        }


class _BlockedURL(ValueError):
    pass
