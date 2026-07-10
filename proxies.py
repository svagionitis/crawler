class ProxyProvider:
    """Base interface for connection proxy providers."""
    def get_proxies(self) -> dict:
        raise NotImplementedError


class DirectConnectionProvider(ProxyProvider):
    """Fallback default connection (no proxy)."""
    def get_proxies(self) -> dict:
        return {}


class StaticProxyProvider(ProxyProvider):
    """Standard proxy provider supporting HTTP, HTTPS, or SOCKS proxies."""
    def __init__(self, proxy_url: str):
        self.proxy_url = proxy_url

    def get_proxies(self) -> dict:
        return {
            "http": self.proxy_url,
            "https": self.proxy_url
        }


class TorProxyProvider(StaticProxyProvider):
    """Tor proxy provider mapping to a local SOCKS5h Tor proxy wrapper."""
    def __init__(self, tor_url: str = "socks5h://127.0.0.1:9050"):
        super().__init__(tor_url)


def get_proxy_provider(proxy_str: str) -> ProxyProvider:
    """Factory function to parse proxy configuration string and return a provider."""
    if not proxy_str:
        return DirectConnectionProvider()

    proxy_str_stripped = proxy_str.strip()
    if not proxy_str_stripped:
        return DirectConnectionProvider()

    if proxy_str_stripped.lower() == "tor":
        return TorProxyProvider()

    return StaticProxyProvider(proxy_str_stripped)
