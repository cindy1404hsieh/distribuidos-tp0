package common

import (
    "fmt" 
	"net"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
	"encoding/csv"
	"encoding/binary"
	"github.com/op/go-logging"
    "io"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
	BatchMaxAmount int
}

// BetData contains the bet data from env vars
type BetData struct {
	FirstName string
	LastName  string
	DNI       string
	BirthDate string
	Number    uint32
}

// Client Entity that encapsulates lottery agency logic
type Client struct {
	config   ClientConfig
	betData  BetData
	shutdown chan os.Signal
	running  bool
    conn     net.Conn
}

// NewClient Initializes a new client with bet data from environment
func NewClient(config ClientConfig) *Client {
	// Read bet data from environment variables
	betData := BetData{
		FirstName: os.Getenv("CLI_NOMBRE"),
		LastName:  os.Getenv("CLI_APELLIDO"),
		DNI:       os.Getenv("CLI_DOCUMENTO"),
		BirthDate: os.Getenv("CLI_NACIMIENTO"),
	}
	
	// Parse bet number
	if numStr := os.Getenv("CLI_NUMERO"); numStr != "" {
		if num, err := strconv.ParseUint(numStr, 10, 32); err == nil {
			betData.Number = uint32(num)
		}
	}
	
	// Validate that we have all the data
	if betData.FirstName == "" || betData.LastName == "" || 
	   betData.DNI == "" || betData.BirthDate == "" || betData.Number == 0 {
		log.Warning("Missing bet data in environment variables")
	}
	
	client := &Client{
		config:   config,
		betData:  betData,
		shutdown: make(chan os.Signal, 1),
		running:  true,
	}
	
	// Register signal handler for SIGTERM
	signal.Notify(client.shutdown, syscall.SIGTERM)
	
	return client
}

// StartClientLoop sends the bet to the central lottery server
func (c *Client) StartClientLoop() {
    // Handle graceful shutdown in a goroutine
    go func() {
        <-c.shutdown
        log.Infof("action: sigterm_received | result: in_progress | client_id: %v", c.config.ID)
        c.running = false
    }()

    // read bets from CSV
    filename := fmt.Sprintf("/data/agency-%s.csv", c.config.ID)
    file, err := os.Open(filename)
    if err != nil {
        log.Errorf("action: open_csv | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return
    }
    defer file.Close()
    
    reader := csv.NewReader(file)
    
    
    // get max batch size from config
    maxBatchSize := c.config.BatchMaxAmount  
    if maxBatchSize == 0 {
        maxBatchSize = 50 
    }
    
    // Procesar el CSV en streaming
    totalBets := 0
    err = c.sendAllBatchesOptimized(reader, maxBatchSize, &totalBets)
    if err != nil && err != io.EOF {
        log.Errorf("action: process_bets | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return
    }
    
    log.Infof("Processed total of %d bets", totalBets)
    
    if !c.running {
        log.Infof("action: graceful_shutdown | result: success | client_id: %v", c.config.ID)
        return
    }

    // DONE y GET_WINNERS usan conexiones separadas
    err = c.sendDone()
    if err != nil {
        log.Errorf("action: send_done | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return
    }
    
    log.Debugf("Agency %s sent DONE message", c.config.ID)
    
    winners := c.getWinners()
    log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %d", len(winners))
    
    log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}
func (c *Client) sendAllBatchesOptimized(reader *csv.Reader, maxBatchSize int, totalBets *int) error {
    // Abrir UNA conexión para TODOS los batches
    conn, err := net.Dial("tcp", c.config.ServerAddress)
    if err != nil {
        return fmt.Errorf("failed to connect: %v", err)
    }
    defer conn.Close()
    
    batch := make([]BetData, 0, maxBatchSize)
    consecutiveErrors := 0
    maxConsecutiveErrors := 3
    
    for c.running {
        record, err := reader.Read()
        
        if err == io.EOF {
            // Enviar último batch si existe
            if len(batch) > 0 {
                if err := c.sendBatch(conn, batch); err != nil {
                    // En EOF, si falla el último batch, reconectar
                    conn.Close()
                    newConn, reconnectErr := net.Dial("tcp", c.config.ServerAddress)
                    if reconnectErr != nil {
                        return fmt.Errorf("failed to reconnect for last batch: %v", reconnectErr)
                    }
                    conn = newConn
                    // Reintentar
                    if err := c.sendBatch(conn, batch); err != nil {
                        return err
                    }
                }
                *totalBets += len(batch)
            }
            return nil
        }
        
        if err != nil {
            return err
        }
        
        // Parsear el registro
        num, err := strconv.ParseUint(record[4], 10, 32)
        if err != nil {
            log.Warningf("Invalid number in CSV: %s, skipping", record[4])
            continue
        }
        
        bet := BetData{
            FirstName: record[0],
            LastName:  record[1],
            DNI:       record[2],
            BirthDate: record[3],
            Number:    uint32(num),
        }
        
        batch = append(batch, bet)
        
        if len(batch) >= maxBatchSize {
            // Intentar enviar con la conexión actual
            err := c.sendBatch(conn, batch)
            
            if err != nil {
                consecutiveErrors++
                log.Warningf("Batch send failed (attempt %d/%d): %v", 
                    consecutiveErrors, maxConsecutiveErrors, err)
                
                if consecutiveErrors >= maxConsecutiveErrors {
                    return fmt.Errorf("too many consecutive errors")
                }
                
                // Reconectar y reintentar
                conn.Close()
                newConn, reconnectErr := net.Dial("tcp", c.config.ServerAddress)
                if reconnectErr != nil {
                    return fmt.Errorf("failed to reconnect: %v", reconnectErr)
                }
                conn = newConn
                
                // Reintentar con nueva conexión
                if err := c.sendBatch(conn, batch); err != nil {
                    return fmt.Errorf("failed after reconnect: %v", err)
                }
            } else {
                consecutiveErrors = 0  // Reset en éxito
            }
            
            *totalBets += len(batch)
            batch = batch[:0]
        }
    }
    
    // Si nos interrumpieron, enviar batch pendiente
    if len(batch) > 0 && c.running {
        // Mejor esfuerzo para el último batch
        _ = c.sendBatch(conn, batch)
        *totalBets += len(batch)
    }
    
    return nil
}

// función para procesar bets en streaming
func (c *Client) processBetsStreaming(reader *csv.Reader, maxBatchSize int, totalBets *int) error {
    batch := make([]BetData, 0, maxBatchSize)
    
    for c.running {
        record, err := reader.Read()
        
        if err == io.EOF {
            if len(batch) > 0 {
                if err := c.sendBatchToServer(batch); err != nil {
                    return err
                }
                *totalBets += len(batch)
            }
            return nil
        }
        
        if err != nil {
            return err
        }
        
        num, err := strconv.ParseUint(record[4], 10, 32)
        if err != nil {
            log.Warningf("Invalid number in CSV: %s, skipping", record[4])
            continue
        }
        
        bet := BetData{
            FirstName: record[0],
            LastName:  record[1],
            DNI:       record[2],
            BirthDate: record[3],
            Number:    uint32(num),
        }
        
        batch = append(batch, bet)
        
        if len(batch) >= maxBatchSize {
            if err := c.sendBatchToServer(batch); err != nil {
                return err
            }
            *totalBets += len(batch)
            batch = batch[:0]
        }
    }
    
    if len(batch) > 0 && c.running {
        if err := c.sendBatchToServer(batch); err != nil {
            return err
        }
        *totalBets += len(batch)
    }
    
    return nil
}
// función auxiliar para enviar batch usando conexión existente
func (c *Client) sendBatchToServer(batch []BetData) error {
    conn, err := net.Dial("tcp", c.config.ServerAddress)
    if err != nil {
        log.Errorf("action: connect | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return err
    }
    defer conn.Close()
    
    err = c.sendBatch(conn, batch)
    if err != nil {
        log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return err
    }
    
    log.Debugf("action: batch_sent | result: success | size: %d", len(batch))
    return nil
}
func (c *Client) sendDone() error {
    if c.conn == nil {
        return fmt.Errorf("no connection available")
    }
    
    agencyID, _ := strconv.ParseUint(c.config.ID, 10, 8)
    
    // mensaje DONE : [type][agency_id]
    msg := []byte{MESSAGE_TYPE_DONE, uint8(agencyID)}
    
    if err := SendMessage(c.conn, msg); err != nil {
        return err
    }
    
    // espero ACK
    _, err := RecvMessage(c.conn)
    return err
}

func (c *Client) getWinners() []string {
    agencyID, _ := strconv.ParseUint(c.config.ID, 10, 8)
    
    for {
        if !c.running {
            return []string{}
        }
        
        conn, err := net.Dial("tcp", c.config.ServerAddress)
        if err != nil {
            log.Errorf("Failed to connect: %v", err)
            time.Sleep(100 * time.Millisecond)  
            continue
        }
        
        msg := []byte{MESSAGE_TYPE_GET_WINNERS, uint8(agencyID)}
        err = SendMessage(conn, msg)
        if err != nil {
            conn.Close()
            log.Errorf("Failed to send GET_WINNERS: %v", err)
            time.Sleep(100 * time.Millisecond)
            continue
        }
        
        response, err := RecvMessage(conn)
        conn.Close()
        
        if err != nil {
            log.Errorf("Failed to receive winners: %v", err)
            time.Sleep(100 * time.Millisecond)
            continue
        }
        
        if len(response) > 0 && response[0] == MESSAGE_TYPE_NOT_READY {
            log.Debugf("Lottery not ready yet, retrying...")
            time.Sleep(100 * time.Millisecond)  
            continue
        }
        
        return parseWinners(response)
    }
}

func parseWinners(data []byte) []string {
    offset := 0
    
    // tipo de mensaje
    msgType := data[offset]
    offset++
    
    if msgType != MESSAGE_TYPE_WINNERS {
        log.Errorf("Invalid message type: %d", msgType)
        return []string{}
    }
    
    // cantidad de ganadores
    count := binary.BigEndian.Uint16(data[offset:offset+2])
    offset += 2
    
    winners := make([]string, 0, count)
    
    // parseo cada DNI
    for i := uint16(0); i < count; i++ {
        length := data[offset]
        offset++
        dni := string(data[offset:offset+int(length)])
        offset += int(length)
        winners = append(winners, dni)
    }
    
    return winners
}



func (c *Client) sendBatch(conn net.Conn, batch []BetData) error {
    agencyID, _ := strconv.ParseUint(c.config.ID, 10, 8)
    
    // serialize the batch
    msg, err := SerializeBatch(uint8(agencyID), batch)
    if err != nil {
        return err
    }
    
    // send
    if err := SendMessage(conn, msg); err != nil {
        return err
    }
    
    // wait for response
    response, err := RecvMessage(conn)
    if err != nil {
        return err
    }
    
    if len(response) != 4 {
        return fmt.Errorf("invalid response size: expected 4 bytes, got %d", len(response))
    }
    
    confirmedNumber := binary.BigEndian.Uint32(response)
    expectedNumber := batch[len(batch)-1].Number
    
    if confirmedNumber != expectedNumber {
        return fmt.Errorf("number mismatch: expected %d, got %d", expectedNumber, confirmedNumber)
    }
    
    return nil
}