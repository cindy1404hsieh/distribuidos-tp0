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
    
    // process in batches
    for i := 0; i < len(bets) && c.running; i += maxBatchSize {
        end := i + maxBatchSize
        if end > len(bets) {
            end = len(bets)
        }
        
        batch := bets[i:end]
        
        // connect for each batch
        conn, err := net.Dial("tcp", c.config.ServerAddress)
        if err != nil {
            log.Errorf("action: connect | result: fail | client_id: %v | error: %v", c.config.ID, err)
            continue
        }
        
        // send the batch
        err = c.sendBatch(conn, batch)
        conn.Close()
        
        if err != nil {
            log.Errorf("action: send_batch | result: fail | client_id: %v | error: %v", c.config.ID, err)
        } else {
            log.Infof("action: batch_sent | result: success | size: %d", len(batch))
        }
    }
    
    // Clean shutdown
    if !c.running {
        log.Infof("action: graceful_shutdown | result: success | client_id: %v", c.config.ID)
    } else {
        log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
    }
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
    
    log.Infof("Read %d bets from file", len(bets))
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
    
    log.Infof("action: batch_sent | result: success | size: %d", len(batch))
    return nil
}
