"""HTTP без лишнего: запросы к своим устройствам и локальным моделям идут мимо прокси."""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
import urllib.request

_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def is_local(host: str) -> bool:
    """localhost, 127.x, 10.x, 192.168.x и прочие частные адреса локальной сети."""
    if host in ("localhost", "") or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(host))
        except (OSError, ValueError):
            return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def urlopen(req: urllib.request.Request | str, timeout: float = 30.0):
    url = req.full_url if isinstance(req, urllib.request.Request) else req
    host = urllib.parse.urlsplit(url).hostname or ""
    if is_local(host):
        return _direct.open(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout)
