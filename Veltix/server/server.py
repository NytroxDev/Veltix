import dataclasses
import socket
import threading
from typing import Callable, Optional, Union

from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..utils.binding import Binding
from ..utils.network import recv


@dataclasses.dataclass
class ServerConfig:
    """
    TCP server configuration.

    Attributes:
        host (str): Server listening address (default: '0.0.0.0')
        port (int): Server listening port (default: 8080)
        buffer_size (int): Buffer size for receiving data (default: 1024)
        max_connection (int): Maximum number of simultaneous connections (default: 2)
    """

    host: str = "0.0.0.0"
    port: int = 8080

    buffer_size: int = 1024

    max_connection: int = 2


@dataclasses.dataclass
class ClientInfo:
    """
    Information about a connected client.

    Attributes:
        conn (socket.socket): Socket connection to the client
        addr (socket._RetAddress): Client address (host, port)
    """

    conn: socket.socket
    addr: socket._RetAddress


class Server:
    def __init__(self, config: ServerConfig) -> None:
        """
        Initialize the TCP server.

        Args:
            config: Server configuration (host, port, buffer_size, max_connection)
        """
        # variable
        self.clients: list[ClientInfo] = []
        self.threads: list[threading.Thread] = []
        self.config: ServerConfig = config
        self.start_th: Optional[threading.Thread] = None
        self.on_recv: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.running: bool = True

        self.sender = Sender(mode=Mode.SERVER)

        # configuration du socket
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(0.5)
        self.socket.bind((self.config.host, self.config.port))

    def bind(self, event: Union[str, Binding], func: Callable) -> None:
        """
        Bind a callback function to a server event.

        Args:
            event: Event type (Binding.ON_RECV, Binding.ON_CONNECT or string)
            func: Callback function to execute
                - on_recv: func(client: ClientInfo, msg: Response)
                - on_connect: func(client: ClientInfo)
        """
        events = [Binding.ON_RECV, Binding.ON_CONNECT]

        for event_ in events:
            if event == event_ or event == event_.value:
                setattr(self, event_.value, func)

    def get_sender(self) -> Sender:
        """
        Get the sender instance for sending data to clients.

        Returns:
            Sender: The sender instance configured in server mode
        """
        return self.sender

    def get_all_clients_sockets(self) -> list[socket.socket]:
        """
        Get all client sockets.

        Returns:
            list[socket.socket]: List of all connected client sockets
        """
        return [client.conn for client in self.clients]

    def start(self, _on_th: bool = False) -> None:
        """
        Start the server and begin listening for connections.

        Automatically runs in a separate thread to avoid blocking the program.
        Accepts clients until max_connection is reached.

        Args:
            _on_th: Internal parameter, do not use (indicates if already in a thread)
        """
        if not _on_th:
            self.start_th = threading.Thread(target=self.start, args=(True,))
            self.start_th.start()
            return

        self.socket.listen()

        while self.running:
            try:
                if len(self.clients) >= self.config.max_connection:
                    continue
                conn, addr = self.socket.accept()
                client = ClientInfo(conn=conn, addr=addr)
                self.clients.append(client)
                thread = threading.Thread(target=self.handle_client, args=(client,))
                thread.start()
                self.threads.append(thread)
            except socket.timeout:
                continue
            except:
                return

    def handle_client(self, client: ClientInfo) -> None:
        """
        Handle communication with a connected client.

        Executed in a separate thread for each client.
        Calls on_connect at the beginning, then on_recv for each received message.
        Automatically closes the connection when the client disconnects.

        Args:
            client: Client information to handle
        """

        if self.on_connect:
            self.on_connect(client)

        while True:
            msg = recv(client.conn, self.config.buffer_size)

            if msg is None:
                self.close_client(client)
                break

            if self.on_recv:
                try:
                    response: Response = Request.parse(msg)
                    self.on_recv(client, response)
                except:
                    pass  # TODO: logger l'erreur

    def close_client(self, client: ClientInfo) -> bool:
        """
        Close a client connection and remove it from the list.

        Args:
            client: The client to disconnect

        Returns:
            True if the client was in the list and was removed, False otherwise
        """
        client.conn.close()
        if client in self.clients:
            self.clients.remove(client)
            return True
        else:
            return False

    def close_all(self) -> None:
        """
        Stop the server and close all connections.

        - Stops the client acceptance loop
        - Disconnects all clients
        - Waits for threads to finish (timeout 0.1s)
        - Closes the server socket
        """
        if self.start_th:
            self.running = False

        for client in self.clients:
            try:
                self.close_client(client)
            except:
                pass  # TODO: logger l'erreur

        for thread in self.threads:
            try:
                thread.join(0.1)
            except:
                pass  # TODO: logger l'erreur

        try:
            self.socket.close()
        except:
            pass  # TODO: logger l'erreur
