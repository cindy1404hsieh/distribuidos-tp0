# server/common/protocol.py
"""
Communication protocol for the lottery system
"""
import socket
import logging

# Constants
ENCODING = 'utf-8'
MAX_MESSAGE_SIZE = 8192  

def int_to_bytes(n, length):
    """Convert an integer to bytes"""
    return n.to_bytes(length, byteorder='big')

def bytes_to_int(b):
    """Convert bytes to integer"""
    return int.from_bytes(b, byteorder='big')

def pack_string(s):
    """Pack string as [length(1B)][data]"""
    encoded = s.encode(ENCODING)
    if len(encoded) > 255:
        raise Exception(f"String too long: {len(encoded)} bytes")
    result = bytes([len(encoded)]) + encoded
    return result

def unpack_string(data, offset=0):
    """Unpack string, return (string, bytes_consumed)"""
    length = data[offset]
    offset += 1
    string = data[offset:offset+length].decode(ENCODING)
    return string, length + 1

def serialize_bet(agency_id, first_name, last_name, dni, birth_date, number):
    """
    Serialize a bet
    Format: [agency(1B)][first_name][last_name][dni_str][birth_date(10B)][number(4B)]
    """
    msg = b''
    
    # Agency ID (1 byte)
    msg += bytes([agency_id])
    
    # Strings with length prefix
    msg += pack_string(first_name)
    msg += pack_string(last_name)
    msg += pack_string(dni)  # DNI as string
    
    if len(birth_date) != 10:
        raise Exception(f"Invalid date format: {birth_date}")
    msg += birth_date.encode('ascii')
    
    # Bet number (4 bytes)
    msg += int_to_bytes(number, 4)
    
    return msg

def deserialize_bet(data):
    """Deserialize a bet from bytes"""
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
    
    # Date (fixed 10 bytes)
    birth_date = data[offset:offset+10].decode('ascii')
    offset += 10
    
    # Number (4 bytes)
    number = bytes_to_int(data[offset:offset+4])
    
    return {
        'agency_id': agency_id,
        'first_name': first_name,
        'last_name': last_name,
        'dni': dni,
        'birth_date': birth_date,
        'number': number
    }

# TCP COMMUNICATION
def send_all(sock, data):
    """Send all bytes, handle short writes"""
    sent = 0
    while sent < len(data):
        n = sock.send(data[sent:])
        if n == 0:
            raise Exception("Connection closed during send")
        sent += n
    logging.debug(f"Sent {len(data)} bytes")

def recv_exact(sock, size):
    """Receive exactly 'size' bytes, handle short reads"""
    data = b''
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:  
            raise Exception("Connection closed during receive")
        data += chunk
    logging.debug(f"Received {size} bytes")
    return data

def send_message(sock, message):
    """
    Send message with format: [size(2B)][data]
    """
    if len(message) > MAX_MESSAGE_SIZE:
        raise Exception(f"Message too large: {len(message)} bytes")
    
    # Size as 2 bytes
    size_bytes = int_to_bytes(len(message), 2)
    
    # Send size + message
    frame = size_bytes + message
    send_all(sock, frame)

def recv_message(sock):
    """
    Receive message with format: [size(2B)][data]
    """
    # Read size first
    size_bytes = recv_exact(sock, 2)
    size = bytes_to_int(size_bytes)
    
    if size > MAX_MESSAGE_SIZE:
        raise Exception(f"Message too large: {size} bytes")
    
    # Read the message
    return recv_exact(sock, size)

def send_single_bet(sock, agency_id, first_name, last_name, dni, birth_date, number):
    """
    Send a bet and wait for confirmation
    """
    # Serialize
    msg = serialize_bet(agency_id, first_name, last_name, dni, birth_date, number)
    
    # Send
    send_message(sock, msg)
    
    # Wait for response (confirmed number)
    response = recv_message(sock)
    if len(response) != 4:
        raise Exception(f"Invalid response: {len(response)} bytes")
    
    confirmed_number = bytes_to_int(response)
    return confirmed_number

def receive_single_bet(sock):
    """
    Receive a bet and send confirmation (used by server)
    """
    # Receive message
    msg = recv_message(sock)
    
    # Deserialize
    bet_data = deserialize_bet(msg)
    
    # Send confirmation (echo back the number)
    confirmation = int_to_bytes(bet_data['number'], 4)
    send_message(sock, confirmation)
    
    return bet_data
