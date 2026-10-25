"""
SOVEREIGN CONDUIT — WINDOWS SYSTEM PROXY AUTOMATOR
Principal Architect: Mohammad Rehan • Rehan Quant Lab
Invariant: Instant 1-click Windows System Proxy enable/disable.
Notifies Windows WinINet API in real-time so all browsers immediately route through Conduit.
"""

import sys
import ctypes
from typing import Tuple

if sys.platform == "win32":
    import winreg

INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37


class WindowsSystemProxyManager:
    """Manages Windows Internet Settings system-wide proxy configuration."""

    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    @classmethod
    def set_system_proxy(cls, host: str = "127.0.0.1", port: int = 1080) -> bool:
        """Enables system proxy to point to Sovereign Conduit."""
        if sys.platform != "win32":
            return False

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_WRITE)
            proxy_val = f"socks={host}:{port};http={host}:{port};https={host}:{port}"

            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_val)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "<local>;*.local;127.0.0.1;localhost")
            winreg.CloseKey(key)

            cls._notify_wininet()
            return True
        except Exception:
            return False

    @classmethod
    def disable_system_proxy(cls) -> bool:
        """Disables Windows system proxy cleanly."""
        if sys.platform != "win32":
            return False

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)

            cls._notify_wininet()
            return True
        except Exception:
            return False

    @classmethod
    def is_proxy_enabled(cls) -> Tuple[bool, str]:
        """Checks if Windows system proxy is currently pointing to a proxy."""
        if sys.platform != "win32":
            return False, ""

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.REG_PATH, 0, winreg.KEY_READ)
            enable_val, _ = winreg.QueryValueEx(key, "ProxyEnable")
            server_val, _ = winreg.QueryValueEx(key, "ProxyServer")
            winreg.CloseKey(key)
            return bool(enable_val), str(server_val)
        except Exception:
            return False, ""

    @staticmethod
    def _notify_wininet():
        """Notifies WinINet that proxy settings have changed in memory."""
        try:
            wininet = ctypes.windll.wininet
            wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
            wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)
        except Exception:
            pass
