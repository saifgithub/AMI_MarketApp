"""Request helpers — resolve the caller's IP behind the Cloudflare Tunnel."""

from __future__ import annotations

from fastapi import Request


def client_ip(request: Request) -> str | None:
    """Cloudflare `cf-connecting-ip` → `x-forwarded-for` first hop → socket peer."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",", 1)[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return None
