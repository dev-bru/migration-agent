"""Block remote sockets before offline test modules are imported."""

import ipaddress
import socket

import pytest


def pytest_sessionstart(session):
    """Allow local process tests while refusing remote network access."""
    if session.config.option.markexpr == "live":
        return
    patch = pytest.MonkeyPatch()
    session.config._offline_socket_patch = patch

    def check(host):
        if host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise OSError("offline tests block non-loopback sockets")

    def guard(original):
        def connect(sock, address):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                check(address[0])
            return original(sock, address)
        return connect

    original_lookup = socket.getaddrinfo

    def lookup(host, *args, **kwargs):
        if host is not None:
            check(host)
        return original_lookup(host, *args, **kwargs)

    original_sendto = socket.socket.sendto

    def sendto(sock, data, *args):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            check(args[-1][0])
        return original_sendto(sock, data, *args)

    patch.setattr(socket.socket, "connect", guard(socket.socket.connect))
    patch.setattr(socket.socket, "connect_ex", guard(socket.socket.connect_ex))
    patch.setattr(socket.socket, "sendto", sendto)
    patch.setattr(socket, "getaddrinfo", lookup)


def pytest_sessionfinish(session):
    """Restore sockets when the offline run ends."""
    patch = getattr(session.config, "_offline_socket_patch", None)
    if patch:
        patch.undo()


@pytest.fixture(autouse=True)
def clear_provider_keys(monkeypatch, request):
    """Keep offline tests independent of real credentials."""
    if request.node.get_closest_marker("live") is None:
        for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_NIM_API_KEY"):
            monkeypatch.delenv(name, raising=False)
