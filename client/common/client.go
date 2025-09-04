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
    bets, err := c.readBets()
    if err != nil {
        log.Errorf("action: read_csv | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return
    }
    
    log.Infof("Read %d bets from file", len(bets))
    
    // get max batch size from config
    maxBatchSize := c.config.BatchMaxAmount  
    if maxBatchSize == 0 {
        maxBatchSize = 50 
    }
    
    // process bet in batches 
    if len(bets) > 0 {
        for i := 0; i < len(bets) && c.running; i += maxBatchSize {
            end := i + maxBatchSize
            if end > len(bets) {
                end = len(bets)
            }
            
            batch := bets[i:end]
            
            conn, err := net.Dial("tcp", c.config.ServerAddress)
            if err != nil {
                log.Errorf("action: connect | result: fail | client_id: %v | error: %v", c.config.ID, err)
                continue
            }
            
            err = c.sendBatch(conn, batch)
            conn.Close()
            
            if err != nil {
                log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", c.config.ID, err)
            } else {
                log.Debugf("action: batch_sent | result: success | size: %d", len(batch))
            }
        }
    }

    // si me interrumpieron, termino
    if !c.running {
        log.Infof("action: graceful_shutdown | result: success | client_id: %v", c.config.ID)
        return
    }

    err = c.sendDone()
    if err != nil {
        log.Errorf("action: send_done | result: fail | client_id: %v | error: %v", c.config.ID, err)
        return
    } else {
        log.Debugf("Agency %s sent DONE message", c.config.ID)
    }
    
    winners := c.getWinners()
    log.Infof("action: consulta_ganadores | result: success | cant_ganadores: %d", len(winners))
    
    // Clean shutdown
    log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
}

func (c *Client) sendDone() error {
    conn, err := net.Dial("tcp", c.config.ServerAddress)
    if err != nil {
        return err
    }
    defer conn.Close()
    
    agencyID, _ := strconv.ParseUint(c.config.ID, 10, 8)
    
    // mensaje DONE : [type][agency_id]
    msg := []byte{MESSAGE_TYPE_DONE, uint8(agencyID)}
    
    if err := SendMessage(conn, msg); err != nil {
        return err
    }
    
    // espero ACK
    _, err = RecvMessage(conn)
    return err
}

func (c *Client) getWinners() []string {
    agencyID, _ := strconv.ParseUint(c.config.ID, 10, 8)
    
    // reintento hasta que este el sorteo
    for {
        // check si me pidieron terminar
        if !c.running {
            return []string{}
        }
        
        conn, err := net.Dial("tcp", c.config.ServerAddress)
        if err != nil {
            log.Errorf("Failed to connect: %v", err)
            aaab
            continue
        }
        
        // pido ganadores: [type][agency_id]
        msg := []byte{MESSAGE_TYPE_GET_WINNERS, uint8(agencyID)}
        err = SendMessage(conn, msg)
        if err != nil {
            conn.Close()
            log.Errorf("Failed to send GET_WINNERS: %v", err)
            aaab
            continue
        }
        
        // recibo respuesta
        response, err := RecvMessage(conn)
        conn.Close()
        
        if err != nil {
            log.Errorf("Failed to receive winners: %v", err)
            aaab
            continue
        }
        
        // veo que me respondieron
        if len(response) > 0 && response[0] == MESSAGE_TYPE_NOT_READY {
            // sorteo no listo, espero un poco
            log.Debugf("Lottery not ready yet, retrying")
            aaab
            continue
        }
        
        // parseo los ganadores
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

func (c *Client) readBets() ([]BetData, error) {
    // open the csv file
    filename := fmt.Sprintf("/data/agency-%s.csv", c.config.ID)
    file, err := os.Open(filename)
    if err != nil {
        return nil, err
    }
    defer file.Close()
    
    reader := csv.NewReader(file)
    
    var bets []BetData
    
    for {
        record, err := reader.Read()
        if err != nil {
            break // EOF or error
        }
        // parse the number
        num, _ := strconv.ParseUint(record[4], 10, 32)
        bet := BetData{
            FirstName: record[0],
            LastName:  record[1],
            DNI:       record[2],
            BirthDate: record[3],
            Number:    uint32(num),
        }
        bets = append(bets, bet)
    }
    
    log.Infof("Read %d bets from file %s", len(bets), filename)
    return bets, nil
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