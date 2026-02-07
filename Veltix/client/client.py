import dataclasses
import socket
import threading
from typing import Callable, Optional, Union

from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..utils.binding import Binding
from ..utils.network import recv


@dataclasses.dataclass
class ClientConfig:
    """
    TCP client configuration.
    
    Attributes:
        server_addr (str): Server address to connect to (default: "127.0.0.1")
        port (int): Server port to connect to (default: 8080)
        buffer_size (int): Buffer size for receiving data (default: 1024)
    """
    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = 1024

class Client:
    def __init__(self, config: ClientConfig) -> None:
        """
        Initialize the TCP client.
        
        Args:
            config: Client configuration (server_addr, port, buffer_size)
        """

        self.config: ClientConfig = config

        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.on_recv: Optional[Callable] = None

        self.is_connected: bool = False

        self.running: bool = True
        self.thread_handler: Optional[threading.Thread] = None

        self.sender = Sender(mode=Mode.CLIENT, conn=self.socket)

    def bind(self, event: Union[str, Binding], func: Callable) -> None:
        """
        Bind a callback function to a client event.
        
        Args:
            event: Event type (Binding.ON_RECV or string)
            func: Callback function to execute
                - on_recv: func(msg: Response)
        """
        events = [
            Binding.ON_RECV
        ]

        for event_ in events:
            if event == event_ or event == event_.value:
                setattr(self, event_.value, func)
        
    
    def connect(self) -> bool:
        """
        Connect to the server and start listening for messages.
        
        Returns:
            True if connection succeeded, False otherwise
        """
        try:
            self.socket.connect((self.config.server_addr, self.config.port))
            self.is_connected = True
            self.thread_handler = threading.Thread(target=self.handle_client)
            self.thread_handler.start()
            return True
        except:
            return False
        
    def get_sender(self) -> Sender:
        """
        Get the sender instance for sending data to the server.
        
        Returns:
            Sender: The sender instance configured in client mode
        """
        return self.sender
        
    def handle_client(self) -> None:
        """
        Handle communication with the server.
        
        Executed in a separate thread.
        Calls on_recv for each received message.
        Automatically closes the connection when the server disconnects.
        """

        while self.running:
            msg = recv(self.socket, self.config.buffer_size)
            
            if msg is None:
                self.disconnect()
                break
            
            if self.on_recv:
                try:
                    response: Response = Request.parse(msg)
                    self.on_recv(response)
                except:
                    pass  # TODO: logger l'erreur

    def disconnect(self) -> bool:
        """
        Disconnect from the server.
        
        Stops the message handling thread and closes the socket connection.
        
        Returns:
            True if disconnection succeeded, False otherwise
        """
        try:
            self.running = False
            self.socket.close()
            self.is_connected = False
            if self.thread_handler and threading.current_thread() != self.thread_handler:
                self.thread_handler.join(timeout=1.0)
            return True
        except:
            return False