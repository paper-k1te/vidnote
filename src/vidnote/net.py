"""网络小工具。"""

from __future__ import annotations


def system_proxy() -> str | None:
    """系统代理地址。httpx 只认环境变量，这里补上 Windows 注册表里的设置。"""
    try:
        from urllib.request import getproxies  # noqa: PLC0415

        proxies = getproxies()
    except Exception:  # noqa: BLE001 - 读注册表失败就直连
        return None
    value = str(proxies.get("https") or proxies.get("http") or "").strip()
    if not value:
        return None
    return value if "://" in value else f"http://{value}"
