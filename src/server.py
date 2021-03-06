from socket import *                                            # Socket programming
from threading import Thread                                    # Python Threads
import re
import traceback


class Server:
    """Implements a multi-threaded server for a asynchronous chat application"""

    def __init__(self, host="127.0.0.1", port=8080, buffer_size=1024, backlog=10):
        """
        Constructs an object of the Class Server
        :param host: IP address of the server
        :param port: Port which server will use
        :param buffer_size: Determines the amount of bytes retrieved from the network per reading
        :param backlog: Determines the amount of clients that may wait for the server
        """
        # Data management
        self.clients = {}
        self.rooms = {}

        # Setting socket properties
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self.backlog = backlog
        self.own_address = (self.host, self.port)

        # Regexp to easily switch between commands
        self.commands_re = re.compile("^\\\(quit|leave|join|rooms|online|create)(?:\s*{(.*)})?$", re.MULTILINE)

        # Prints a welcome message to console
        print("\nWelcome to Concord Server v.0.9.2\n"
              "This program is under GNU General Public License v3.0\n")

        # Create TCP socket with user selected properties.
        self.socket = socket(AF_INET, SOCK_STREAM)

        try:
            # Bind the socket to address.
            # The socket must not already be bound, it may raise the treated OSError exception
            self.socket.bind(self.own_address)
            # Enable a server to accept connections.
            self.socket.listen(self.backlog)

            # Prints console feedback message and reconfigure the buttons
            print("Server is up and running! Waiting for connections...")

            # Set up threads
            self.listening_thread = Thread(target=self.listen)
            self.client_threads = []
            # From now on, we're allowed to receive connections
            self.listening_thread.start()

            # This thread allow us to keep using the terminal
            self.console_thread = Thread(target=self.console)
            self.console_thread.start()

        except OSError:
            # Treating exception thrown by bind
            print(traceback.format_exc())
            print("Check your configuration and try again")

    def stop_server(self):
        """
        Stops the server by joining all threads and closing the server socket
        """

        # Closing socket of all clients
        for client in self.clients.values():
            client['socket'].close()
        del self.clients
        del self.rooms

        # Joining all clients threads and clearing threads list
        for thread in self.client_threads:
            if thread.isAlive():
                thread.join(1)
        self.client_threads.clear()

        # Joining listening thread
        if self.listening_thread.isAlive():
            self.listening_thread.join(1)

        # Close socket
        self.socket.close()

        # Prints message to terminal
        print("Server successfully shutdown")

    def listen(self):
        """
        Listen to network and starts the handling of upcoming connections,
        this is the target for dispatcher thread
        """

        while True:
            # Blocking socket call waiting for client connection
            client, client_address = self.socket.accept()

            # Prints message to terminal
            print("Connection established with {host}:{port}"
                  .format(host=client_address[0], port=client_address[1]))

            # Creates a new thread and insert it to server list
            new_thread = Thread(target=self.handle_connection, args=(client_address, client, ))
            self.client_threads.append(new_thread)
            new_thread.start()

    def handle_connection(self, address, socket):
        """
        Handles a connection with one client, this is the target for each worker thread
        :param address: tuple with IP (string) and port (integer) of connected user, e.g ('127.0.0.1', 8080)
        :param socket: Python socket object already connected to address

        Description:
        1. Retrieve user's nickname that will be used for entire section
            * New messages will be requested until receiving a unique display name
        2. Starts a 'infinity loop' treating inbound messages from socket
            2.1. Decodes the message between command or chat message
                * If it's a chat message, broadcast it to all users in room
                * If it's a command, execute correspondent action
        """

        # Prints message to terminal
        print("Thread started for address %s:%s" % (address[0], address[1]))

        # Initial conditions
        proceed = True
        nick = ""
        insert_regexp = re.compile("^\\\(quit|insert)\s*(?:{(.*)})?$", re.MULTILINE)

        try:
            # Loop to get user's nickname
            while proceed:
                # Retrieve message from socket, decode and match with regexp
                message = socket.recv(self.buffer_size)
                message_text = message.decode("utf8")
                match = insert_regexp.match(message_text)

                # If line matched, it means that user issued insert command
                if match:
                    command, nick = match.groups()
                    if command == "quit":
                        socket.send(bytes("\\quit=success", "utf8"))
                        socket.close()
                        print("(Address %s:%s) has quit" % (address[0], address[1]))
                        return
                    elif command == "insert" and nick is not None:
                        # Nickname is already in use
                        if nick in self.clients.keys():
                            socket.send(bytes("\\insert=not_valid_nickname", "utf8"))
                        # Adds client to list
                        else:
                            self.clients[nick] = {'address': address, 'socket': socket, 'room': None}
                            proceed = False
                else:
                    socket.send(bytes("\\insert=not_valid_nickname", "utf8"))

            # Prints message to terminal
            print("Address %s:%s is now using '%s' nickname" % (address[0], address[1], nick))

            # 'Infinity' loop
            while True:
                # Wait until receive a message
                message = socket.recv(self.buffer_size)
                message_text = message.decode("utf8")

                # Tries to match message_text to regexp
                match = self.commands_re.match(message_text)
                if match:
                    command, argument = match.groups()

                    # Quit: broadcast advise to room, send confirmation to client and break outer loop to exit thread
                    if command == 'quit':
                        self.leave_room(nick, socket)
                        del self.clients[nick]
                        socket.send(bytes("\\quit=success", "utf8"))
                        socket.close()
                        # Prints message to terminal
                        print("%s (address %s:%s) has quit" % (nick, address[0], address[1]))
                        return

                    # Rooms: join all keys from rooms hash and send back to user
                    elif command == 'rooms':
                        room_list = "\\rooms=" + "|".join(self.rooms.keys())
                        socket.send(bytes(room_list, "utf8"))

                    # Online: join all keys from rooms['room'] hash and send back to user
                    elif command == 'online':
                        answer = self.get_online_users(argument)
                        socket.send(bytes(answer, "utf8"))

                    # Join: change 'room' value on user hash entry, add his entry to room,
                    # send confirmation and broadcast message to room
                    elif command == 'join':
                        self.join_room(nick, argument, socket)

                    # Leave: remove his entry from room, clear 'room' value on user hash entry,
                    # send confirmation and broadcast message to room
                    elif command == 'leave':
                        self.leave_room(nick, socket)

                    # Create: create new entry on rooms hash
                    elif command == 'create':
                        self.create_room(argument, socket)

                # The message was a normal text, broadcast it to room users
                else:
                    self.room_announce(message_text, self.clients[nick]['room'], nick)

        # Exceptions to handle inadequate user quitting
        except ConnectionResetError:
            if nick != '':
                self.room_announce("{nick} has left the chat".format(nick=nick), self.clients[nick]['room'], "Server")
                del self.rooms[self.clients[nick]['room']]['users'][nick]
                del self.clients[nick]
            socket.close()
            # Prints message to terminal
            print("%s (address %s:%s) has quit" % (nick, address[0], address[1]))
            return
        except BrokenPipeError:
            if nick != '':
                del self.rooms[self.clients[nick]['room']]['users'][nick]
                del self.clients[nick]
            socket.close()
            # Prints message to terminal
            print("%s (address %s:%s) has quit" % (nick, address[0], address[1]))
            return

    def room_announce(self, msg, room, prefix):
        """
        Send a message to all sockets given a valid room
        :param msg: Message string to be sent
        :param room: Destination room
        :param prefix: Prefix for message tag sender identification
        """
        # The following condition assumes that rooms_hash will be accessed within function call
        if room is not None:
            Server.broadcast(msg, [client['socket'] for client in self.rooms[room]['users'].values()], prefix)

    def get_online_users(self, room):
        """
        Builds a string with all online users of a valid room
        :param room: Target room to get users
        :return: String ready to be sent to some client
        """
        # Checks if room exists
        if (room in self.rooms.keys()) and (room is not None):
            users_list = "\\online=" + "|".join(self.rooms[room]['users'].keys())
            return users_list
        else:
            return "\\online=no_room"

    def join_room(self, user_nick, room, user_socket):
        """
        Insert a user in a room
        :param user_nick: Nick of the user who made the request
        :param room: Name of the room which he wants to join
        :param user_socket: Socket connected to the user
        """
        # Checks if room exists
        if (room in self.rooms.keys()) and (room is not None):
            # Changes clients dict
            self.clients[user_nick]['room'] = room
            # Add to room dict
            self.rooms[room]['users'][user_nick] = self.clients[user_nick]
            # Send user confirmation
            user_socket.send(bytes("\\join=success", "utf8"))
            # Updates list of online users
            self.room_announce(self.get_online_users(room), room, "")
            # Prints message to terminal
            print("'%s' joined '%s' room" % (user_nick, room))
        else:
            # Room does not exist
            user_socket.send(bytes("\\join=failure", "utf8"))

    def leave_room(self, user_nick, user_socket):
        """
        Removes a user from current room
        :param user_nick: Nick of the user who made the request
        :param user_socket: Socket connected to the user
        """
        # Checks if the user is actually joined to any room
        room_name = self.clients[user_nick]['room']
        if room_name is not None:
            # Send user confirmation
            user_socket.send(bytes("\\leave=success", "utf8"))
            # Deletes his entry from room dictionary
            del self.rooms[room_name]['users'][user_nick]
            # Deletes empty room (the last user is leaving)
            if len(self.rooms[room_name]['users']) == 0:
                del self.rooms[room_name]
                # Prints message to terminal
                print("Room '%s' deleted by server because of emptiness" % room_name)
            else:
                # Updates the list of online users to remaining users in room
                self.room_announce(self.get_online_users(self.clients[user_nick]['room']), room_name, "")
            # Nullify the room entry on clients dict
            self.clients[user_nick]['room'] = None

            # Prints message to terminal
            print("'%s' is now outside of any room" % user_nick)
        # User is already of a room
        else:
            user_socket.send(bytes("\\leave=no_room", "utf8"))

    def create_room(self, room_name, user_socket):
        """
        Creates a new room
        :param room_name: Name of the room to be created
        :param user_socket: Socket connected to user (who requested the creation)
        """
        # Checks if name is available
        if (room_name not in self.rooms.keys()) and (room_name is not None):
            # Creates a empty entry in dict
            self.rooms[room_name] = {'users': {}}
            # Replies with success
            user_socket.send(bytes("\\create=success", "utf8"))

            # Prints message to terminal
            print("'%s' room has been created" % room_name)
        # Name is in use
        else:
            user_socket.send(bytes("\\create=failure", "utf8"))

    @staticmethod
    def broadcast(msg, recipients, prefix):
        """
        Static method that sends a message to all socket in recipients list
        :param msg: Message to be sent
        :param recipients: List of sockets of all clients that will receive the message
        :param prefix: Prefix is for adding an identification tag
        """
        if prefix != "":
            # Prefix is for name identification.
            for recipient in recipients:
                recipient.send(bytes("[{prefix}]: {msg}".format(prefix=prefix, msg=msg), "utf8"))
        else:
            # Send message without the prefix
            for recipient in recipients:
                recipient.send(bytes(msg, "utf8"))

    def console(self):
        """
        Function to receive commmand from server terminal.
        This is the target of a thread in the Server class constructor
        """
        while True:
            # Reads from terminal
            command = input()
            # Checks for available commands (just 'quit' for now)
            if command == "quit":
                # Prints message to terminal
                print("User has request server stop")
                self.stop_server()
                # Stop the thread by ending the function
                break


if __name__ == "__main__":
    valid = False
    host, port, buffer_size, backlog = 0, 0, 0, 0
    while not valid:
        try:
            host = input("Host (127.0.0.1):")
            port = int(input("Port (8080):"))
            buffer_size = int(input("Buffer Size (1024):"))
            backlog = int(input("Backlog (10):"))
            valid = True
        except ValueError:
            print("Verifique os dados inseridos!")

    server = Server(host, port, buffer_size, backlog)
