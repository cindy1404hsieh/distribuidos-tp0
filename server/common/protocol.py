import struct
import socket
from typing import Tuple, Optional
import logging

ENCODING = 'utf-8'
MAX_MESSAGE_SIZE = 8192  # 8KB 

class ProtocolError(Exception):
    """Errores específicos del protocolo"""
    pass

# serialize
def pack_string(s: str) -> bytes:
    """Empaqueta string como [largo(2B)][datos]"""
    encoded = s.encode(ENCODING)
    if len(encoded) > 255:  # Usamos 1 byte para largo
        raise ProtocolError(f"String too long: {len(encoded)} bytes")
    return struct.pack('!B', len(encoded)) + encoded

def unpack_string(data: bytes, offset: int = 0) -> Tuple[str, int]:
    """Desempaqueta string, retorna (string, bytes_consumidos)"""
    length = data[offset]
    offset += 1
    string = data[offset:offset+length].decode(ENCODING)
    return string, length + 1

def serialize_bet(agency_id: int, first_name: str, last_name: str, 
                  dni: str, birth_date: str, number: int) -> bytes:
    """
    Serializa una apuesta individual
    Formato: [agency(1B)][nombre][apellido][dni_str][fecha(10B)][numero(4B)]
    """
    buf = bytearray()
    
    # Agency ID (1 byte)
    buf.append(agency_id)

    # Strings with length prefix
    buf.extend(pack_string(first_name))
    buf.extend(pack_string(last_name))
    buf.extend(pack_string(dni))  # DNI as string to preserve leading zeros

    # Fixed date 10 bytes (YYYY-MM-DD)
    if len(birth_date) != 10:
        raise ProtocolError(f"Invalid date format: {birth_date}")
    buf.extend(birth_date.encode('ascii'))

    # Bet number (4 bytes)
    buf.extend(struct.pack('!I', number))
    
    return bytes(buf)

def deserialize_bet(data: bytes) -> dict:
    """Deserializa una apuesta desde bytes"""
    offset = 0
    
    # Agency ID
    agency_id = data[offset]
    offset += 1
    
    # Strings
    first_name, consumed = unpack_string(data, offset)
    offset += consumed
    
    last_name, consumed = unpack_string(data, offset)
    offset += consumed
    
    dni, consumed = unpack_string(data, offset)
    offset += consumed

    # Fixed date (10 bytes)
    birth_date = data[offset:offset+10].decode('ascii')
    offset += 10

    # Bet number
    number = struct.unpack('!I', data[offset:offset+4])[0]
    
    return {
        'agency_id': agency_id,
        'first_name': first_name,
        'last_name': last_name,
        'dni': dni,
        'birth_date': birth_date,
        'number': number
    }

# tcp communication
def send_all(sock: socket.socket, data: bytes) -> None:
    """Send all bytes, handles short writes"""
    sent = 0
    while sent < len(data):
        n = sock.send(data[sent:])
        if n == 0:
            raise ProtocolError("Connection closed during send")
        sent += n
    logging.debug(f"Sent {len(data)} bytes")

def recv_exact(sock: socket.socket, size: int) -> bytes:
    """Receive exactly 'size' bytes, handles short reads"""
    buffer = bytearray(size)
    pos = 0
    while pos < size:
        n = sock.recv_into(memoryview(buffer)[pos:])
        if n == 0:
            raise ProtocolError("Connection closed during receive")
        pos += n
    logging.debug(f"Received {size} bytes")
    return bytes(buffer)

def send_message(sock: socket.socket, message: bytes) -> None:
    """
    Envía mensaje con formato: [tamaño(2B)][datos]
    """
    if len(message) > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message too large: {len(message)} bytes")
    
    # Frame: [size(2B)][payload]
    frame = struct.pack('!H', len(message)) + message
    send_all(sock, frame)

def recv_message(sock: socket.socket) -> bytes:
    """
    Receive message with format: [size(2B)][data]
    """
    # Read size
    size_bytes = recv_exact(sock, 2)
    size = struct.unpack('!H', size_bytes)[0]
    
    if size > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message too large: {size} bytes")

    # Read payload
    return recv_exact(sock, size)

# === HIGH LEVEL API ===
def send_single_bet(sock: socket.socket, **bet_data) -> int:
    """
    Send a single bet and wait for confirmation
    Returns the number confirmed by the server
    """
    # Serialize bet
    message = serialize_bet(
        bet_data['agency_id'],
        bet_data['first_name'],
        bet_data['last_name'],
        bet_data['dni'],
        bet_data['birth_date'],
        bet_data['number']
    )

    # Send
    send_message(sock, message)

    # Wait for confirmation (server sends the number back)
    response = recv_message(sock)
    if len(response) != 4:
        raise ProtocolError(f"Invalid response size: {len(response)}")
    
    confirmed_number = struct.unpack('!I', response)[0]
    return confirmed_number

def receive_single_bet(sock: socket.socket) -> dict:
    """
    Receive a bet and send confirmation
    Used by the server
    """
    # Receive message
    message = recv_message(sock)

    # Deserialize
    bet_data = deserialize_bet(message)

    # Send confirmation (echo of the number)
    confirmation = struct.pack('!I', bet_data['number'])
    send_message(sock, confirmation)
    
    return bet_data