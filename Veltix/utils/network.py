import socket
from typing import Optional

def recv(conn: socket.socket, buf_size: int = 1024) -> Optional[bytes]:
    """
    Reçoit des données avec gestion d'erreurs
    Retourne None si erreur/déconnexion
    """

    try:
        data = conn.recv(buf_size)
        if not data:  # Connexion fermée proprement
            return None
        
        return data
    
    except Exception as e:
        print(f"Erreur recv: {e}")
        return None