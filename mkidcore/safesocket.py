from socket import *
from threading import RLock
import socket as _socket
import types


class RLockSocketv2(object):
    def __init__(self, sock):
        self.__RLSsocket = sock
        self.__RLSlock = RLock()

    def __getattr__(self, attr):
        return getattr(self.__RLSsocket, attr)

    def accept(self, *a, **kw):
        with self.__RLSlock:
            conn, addr = self.__RLSsocket.accept(*a, **kw)
        return RLockSocketv2(conn), addr

    def sendall(self, *a, **kw):
        with self.__RLSlock:
            return self.__RLSsocket.sendall(*a, **kw)

    def send(self, *a, **kw):
        with self.__RLSlock:
            return self.__RLSsocket.send(*a, **kw)


def create_connection(*a, **kw):
    sock = _socket.create_connection(*a, **kw)
    return RLockSocketv2(sock)


def socket(*a, **kw):
    """ Replace socket.socket with an RLock protected socket via delegation"""
    sock = _socket.socket(*a, **kw)
    return RLockSocketv2(sock)
