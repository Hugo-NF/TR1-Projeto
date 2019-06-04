# Project imports
# Python built-in for sockets programming
from socket import AF_INET, socket, SOCK_STREAM, SOCK_DGRAM

# Python build-in for handling threads
from threading import Thread

class Server:
    """Implements a multi-threaded server for a asynchronous chat application"""

    buffer_size = 1024

    def __init__(self, host, port, isTcp):
        self.clients = {}
        self.addresses = {}
        self.host = host
        self.port = port
        self.own_address = (self.host, self.port)
        if isTcp:
            self.socket = socket(AF_INET, SOCK_STREAM)
        else:
            self.socket = socket(AF_INET, SOCK_DGRAM)

    def start_server(self):
        self.socket.bind(self.own_address)
