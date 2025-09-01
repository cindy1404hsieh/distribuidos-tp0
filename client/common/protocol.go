package common

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"io"
	"net"
)

const (
	MaxMessageSize = 8192 // 8KB limit
	Encoding       = "utf-8"
)

// packString pack string as [lenght(1B)][data]
func packString(s string) []byte {
	data := []byte(s)
	if len(data) > 255 {
		panic(fmt.Sprintf("String too long: %d bytes", len(data)))
	}
	result := make([]byte, 1+len(data))
	result[0] = byte(len(data))
	copy(result[1:], data)
	return result
}

// SerializeBet serialize a bet for sending
func SerializeBet(agencyID uint8, firstName, lastName, dni, birthDate string, number uint32) []byte {
	buf := new(bytes.Buffer)
	
	// Agency ID (1 byte)
	buf.WriteByte(agencyID)

	// Strings with length prefix
	buf.Write(packString(firstName))
	buf.Write(packString(lastName))
	buf.Write(packString(dni))

	// Fixed date 10 bytes (YYYY-MM-DD)
	if len(birthDate) != 10 {
		panic(fmt.Sprintf("Invalid date format: %s", birthDate))
	}
	buf.WriteString(birthDate)

	// Number bet (4 bytes)
	binary.Write(buf, binary.BigEndian, number)
	
	return buf.Bytes()
}

// SendAll sends all bytes, handles short writes
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

// RecvExact receives exactly 'size' bytes, handles short reads
func RecvExact(conn net.Conn, size int) ([]byte, error) {
	buffer := make([]byte, size)
	_, err := io.ReadFull(conn, buffer)
	if err != nil {
		return nil, fmt.Errorf("failed to read %d bytes: %v", size, err)
	}
	return buffer, nil
}

// SendMessage sends a message with format: [size(2B)][data]
func SendMessage(conn net.Conn, message []byte) error {
	if len(message) > MaxMessageSize {
		return fmt.Errorf("message too large: %d bytes", len(message))
	}
	
	// Frame: [size(2B)][payload]
	sizeBuf := make([]byte, 2)
	binary.BigEndian.PutUint16(sizeBuf, uint16(len(message)))

	// Send size + message
	if err := SendAll(conn, sizeBuf); err != nil {
		return err
	}
	return SendAll(conn, message)
}

// RecvMessage receives a message with format: [size(2B)][data]
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

// SendSingleBet sends a bet and waits for confirmation
func SendSingleBet(conn net.Conn, agencyID uint8, firstName, lastName, dni, birthDate string, number uint32) error {
	// Serialize bet
	message := SerializeBet(agencyID, firstName, lastName, dni, birthDate, number)

	// Send
	if err := SendMessage(conn, message); err != nil {
		return fmt.Errorf("failed to send bet: %v", err)
	}

	// Wait for confirmation
	response, err := RecvMessage(conn)
	if err != nil {
		return fmt.Errorf("failed to receive confirmation: %v", err)
	}
	
	if len(response) != 4 {
		return fmt.Errorf("invalid response size: %d", len(response))
	}

	// Verify confirmed number
	confirmedNumber := binary.BigEndian.Uint32(response)
	if confirmedNumber != number {
		return fmt.Errorf("number mismatch: sent %d, confirmed %d", number, confirmedNumber)
	}
	
	return nil
}