"""Fail-closed URL, DNS and destination policy for browser traffic."""

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlsplit, urlunsplit


class ScopeError(ValueError):
    pass


def clean_url(value: str) -> str:
    """Remove query, fragment and user info before persisting or showing a URL."""
    parts = urlsplit(value)
    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port else ""
    return urlunsplit((parts.scheme, host + port, parts.path or "/", "", ""))


def origin(value: str) -> tuple[str, str, int]:
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ScopeError("Only HTTP(S) URLs with a host are allowed")
        if parts.username or parts.password or parts.fragment:
            raise ScopeError("Credentials and fragments are not allowed in URLs")
        return parts.scheme, parts.hostname.lower().rstrip("."), parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as exc:
        raise ScopeError("Invalid URL") from exc


def _is_global(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global


@dataclass
class ScopePolicy:
    authorized_origins: tuple[str, ...]
    private_worker: bool = False
    private_cidrs: tuple[str, ...] = ()
    pinned: dict[str, str] = field(default_factory=dict, init=False)
    _origins: set[tuple[str, str, int]] = field(default_factory=set, init=False)
    _networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = field(default=(), init=False)

    def __post_init__(self) -> None:
        if not self.authorized_origins:
            raise ScopeError("At least one authorized origin is required")
        self._origins = {origin(item) for item in self.authorized_origins}
        for item in self.authorized_origins:
            parts = urlsplit(item)
            if parts.path not in ("", "/") or parts.query:
                raise ScopeError("Authorized origins cannot contain a path or query")
        self._networks = tuple(ipaddress.ip_network(item, strict=True) for item in self.private_cidrs)
        if self._networks and not self.private_worker:
            raise ScopeError("Private ranges require an explicitly enabled private worker")
        if any(not network.is_private for network in self._networks):
            raise ScopeError("Private worker ranges must be private networks")

    def _allowed_ip(self, value: str) -> bool:
        address = ipaddress.ip_address(value)
        if address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved:
            return False
        return _is_global(address) or (self.private_worker and any(address in network for network in self._networks))

    def prepare(self) -> None:
        """Resolve all authorized hosts before Chromium starts; reject mixed DNS answers."""
        for _, host, port in self._origins:
            try:
                literal = ipaddress.ip_address(host)
            except ValueError:
                literal = None
            if literal is not None:
                if not self._allowed_ip(str(literal)):
                    raise ScopeError("Destination IP is outside permitted networks")
                self.pinned[host] = str(literal)
                continue
            try:
                addresses = {result[4][0] for result in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
            except OSError as exc:
                raise ScopeError("Authorized host could not be resolved") from exc
            if not addresses or any(not self._allowed_ip(item) for item in addresses):
                raise ScopeError("DNS returned an address outside permitted networks")
            ipv4 = sorted(item for item in addresses if isinstance(ipaddress.ip_address(item), ipaddress.IPv4Address))
            if not ipv4:
                raise ScopeError("An authorized host requires an IPv4 address for this browser profile")
            self.pinned[host] = ipv4[0]

    def check(self, value: str, *, navigation: bool = False) -> str:
        key = origin(value)
        parts = urlsplit(value)
        if key not in self._origins or key[1] not in self.pinned:
            raise ScopeError("URL is outside authorized origins")
        if navigation and (parts.query or parts.fragment):
            raise ScopeError("Navigation with query or fragment is disabled by default")
        if any(
            key.lower() in {"action", "cmd", "command", "operation", "op", "method", "do"}
            and value.lower() in {"delete", "remove", "destroy", "logout", "signout", "purchase", "checkout", "reset", "update", "save"}
            for key, value in parse_qsl(parts.query)
        ):
            raise ScopeError("Potentially destructive query is disabled")
        path = parts.path.lower().strip("/")
        if any(segment in {"delete", "remove", "destroy", "logout", "signout", "checkout", "purchase", "reset"} for segment in path.split("/")):
            raise ScopeError("Potentially destructive navigation is disabled")
        return clean_url(value)

    def chromium_rules(self) -> str:
        """Pin approved DNS names to reviewed IPs in Chromium."""
        rules = [f"MAP {host} {address}" for host, address in sorted(self.pinned.items()) if host != address]
        return ", ".join(rules)
