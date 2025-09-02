package common

import (
	"net"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/op/go-logging"
)

var log = logging.MustGetLogger("log")

// ClientConfig Configuration used by the client
type ClientConfig struct {
	ID            string
	ServerAddress string
	LoopAmount    int
	LoopPeriod    time.Duration
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
	
	// we send a single bet
	if !c.running {
		return
	}
	
	// Connect to the server
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Errorf("action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}
	defer conn.Close()

	// Parse agency ID from client ID
	agencyID, _ := strconv.ParseUint(c.config.ID, 10, 8)

	// Send bet using the protocol
	err = SendSingleBet(
		conn,
		uint8(agencyID),
		c.betData.FirstName,
		c.betData.LastName,
		c.betData.DNI,
		c.betData.BirthDate,
		c.betData.Number,
	)
	
	if err != nil {
		log.Errorf("action: send_bet | result: fail | client_id: %v | error: %v",
			c.config.ID, err)
		return
	}

	log.Infof("action: apuesta_enviada | result: success | dni: %v | numero: %v",
		c.betData.DNI, c.betData.Number)
	
	// Clean shutdown
	if !c.running {
		log.Infof("action: graceful_shutdown | result: success | client_id: %v", c.config.ID)
	} else {
		log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
	}
}