package common

import (
	"encoding/binary"
	"fmt"
	"net"
)

const (
	MaxMessageSize = 8192
	MessageTypeSingle = 0x01
	MessageTypeBatch  = 0x02
)

// packString packs a string as [length(1B)][data]
func packString(s string) []byte {
	data := []byte(s)
	if len(data) > 255 {
		panic(fmt.Sprintf("String too long: %d bytes", len(data)))
	}
	// Create buffer for result
	result := make([]byte, 1+len(data))
	result[0] = byte(len(data))
	copy(result[1:], data)
	return result
}

// SerializeBet serializes a bet
func SerializeBet(agencyID uint8, firstName, lastName, dni, birthDate string, number uint32) []byte {
	// Build message concatenating fields
	msg := make([]byte, 0, 256)
	
	// Agency ID (1 byte)
	msg = append(msg, agencyID)
	
	// Strings with length prefix
	msg = append(msg, packString(firstName)...)
	msg = append(msg, packString(lastName)...)
	msg = append(msg, packString(dni)...)
	
	if len(birthDate) != 10 {
		panic(fmt.Sprintf("Invalid date: %s", birthDate))
	}
	msg = append(msg, []byte(birthDate)...)
	
	// Bet number (4 bytes)
	numBytes := make([]byte, 4)
	binary.BigEndian.PutUint32(numBytes, number)
	msg = append(msg, numBytes...)
	
	return msg
}
func SerializeBatch(agencyID uint8, bets []BetData) ([]byte, error) {
    msg := make([]byte, 0, MaxMessageSize)

    // msg type (1 byte)
    msg = append(msg, MessageTypeBatch)

    // number of bets (2 bytes)
    numBets := uint16(len(bets))
    numBytes := make([]byte, 2)
    binary.BigEndian.PutUint16(numBytes, numBets)
    msg = append(msg, numBytes...)

    // serialize each bet
    for _, bet := range bets {
        betBytes := SerializeBet(agencyID, bet.FirstName, bet.LastName,
            bet.DNI, bet.BirthDate, bet.Number)

        // check that it doesnt exceed 8KB
        if len(msg) + len(betBytes) > MaxMessageSize {
            return nil, fmt.Errorf("batch too large")
        }
        msg = append(msg, betBytes...)
    }
    
    return msg, nil
}
// SendAll sends all bytes
func SendAll(conn net.Conn, data []byte) error {
	sent := 0
	for sent < len(data) {
		n, err := conn.Write(data[sent:])
		if err != nil {
			return err
		}
		if n == 0 {
			return fmt.Errorf("connection closed during send")
		}
		sent += n
	}
	return nil
}

// RecvExact receives exactly size bytes
func RecvExact(conn net.Conn, size int) ([]byte, error) {
	buf := make([]byte, size)
	received := 0
	
	for received < size {
		n, err := conn.Read(buf[received:])
		if err != nil {
			return nil, err
		}
		if n == 0 {
			return nil, fmt.Errorf("connection closed during receive")
		}
		received += n
	}
	
	return buf, nil
}

// SendMessage sends a message with format [size(2B)][data]
func SendMessage(conn net.Conn, message []byte) error {
	if len(message) > MaxMessageSize {
		return fmt.Errorf("message too large: %d bytes", len(message))
	}
	
	// Size as 2 bytes
	sizeBuf := make([]byte, 2)
	binary.BigEndian.PutUint16(sizeBuf, uint16(len(message)))
	
	// Send size
	if err := SendAll(conn, sizeBuf); err != nil {
		return err
	}
	
	// Send message
	return SendAll(conn, message)
}

// RecvMessage receives a message with format [size(2B)][data]
func RecvMessage(conn net.Conn) ([]byte, error) {
	// Read size
	sizeBuf, err := RecvExact(conn, 2)
	if err != nil {
		return nil, err
	}
	size := binary.BigEndian.Uint16(sizeBuf)
	
	if size > MaxMessageSize {
		return nil, fmt.Errorf("message too large: %d bytes", size)
	}
	
	// Read payload
	return RecvExact(conn, int(size))
}

// SendSingleBet sends a single bet and waits for confirmation
func SendSingleBet(conn net.Conn, agencyID uint8, firstName, lastName, dni, birthDate string, number uint32) error {
	// Serialize
	msg := SerializeBet(agencyID, firstName, lastName, dni, birthDate, number)
	
	// Send
	if err := SendMessage(conn, msg); err != nil {
		return fmt.Errorf("failed to send bet: %v", err)
	}
	
	// Receive confirmation
	response, err := RecvMessage(conn)
	if err != nil {
		return fmt.Errorf("failed to receive confirmation: %v", err)
	}
	
	if len(response) != 4 {
		return fmt.Errorf("invalid response size")
	}
	
	// Verify number
	confirmedNumber := binary.BigEndian.Uint32(response)
	if confirmedNumber != number {
		return fmt.Errorf("number mismatch: sent %d, confirmed %d", number, confirmedNumber)
	}
	
	return nil
}
