package common

import (
	"bufio"
	"fmt"
	"net"
	"os"
	"os/signal"
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

// Client Entity that encapsulates how
type Client struct {
	config   ClientConfig
	conn     net.Conn
	shutdown chan os.Signal
	running  bool
}

// NewClient Initializes a new client receiving the configuration
// as a parameter
func NewClient(config ClientConfig) *Client {
	client := &Client{
		config:   config,
		shutdown: make(chan os.Signal, 1),
		running:  true,
	}
	
	// Register signal handler for SIGTERM
	signal.Notify(client.shutdown, syscall.SIGTERM)
	
	return client
}

// CreateClientSocket Initializes client socket. In case of
// failure, error is printed in stdout/stderr and exit 1
// is returned
func (c *Client) createClientSocket() error {
	conn, err := net.Dial("tcp", c.config.ServerAddress)
	if err != nil {
		log.Criticalf(
			"action: connect | result: fail | client_id: %v | error: %v",
			c.config.ID,
			err,
		)
		return err
	}
	c.conn = conn
	return nil
}

// closeConnection closes the current connection if it exists
func (c *Client) closeConnection() {
	if c.conn != nil {
		c.conn.Close()
		c.conn = nil
		log.Debugf("action: connection_closed | result: success | client_id: %v", c.config.ID)
	}
}

// StartClientLoop Send messages to the client until some time threshold is met
func (c *Client) StartClientLoop() {
	// Handle graceful shutdown in a goroutine
	go func() {
		<-c.shutdown
		log.Infof("action: sigterm_received | result: in_progress | client_id: %v", c.config.ID)
		c.running = false
		// Close any active connection
		c.closeConnection()
	}()

	// There is an autoincremental msgID to identify every message sent
	// Messages if the message amount threshold has not been surpassed
	for msgID := 1; msgID <= c.config.LoopAmount && c.running; msgID++ {
		// Check if we should shutdown before creating connection
		if !c.running {
			break
		}

		// Create the connection the server in every loop iteration
		err := c.createClientSocket()
		if err != nil {
			if !c.running {
				// Error due to shutdown
				break
			}
			return
		}

		// TODO: Modify the send to avoid short-write
		_, err = fmt.Fprintf(
			c.conn,
			"[CLIENT %v] Message N°%v\n",
			c.config.ID,
			msgID,
		)
		
		if err != nil {
			log.Errorf("action: send_message | result: fail | client_id: %v | error: %v",
				c.config.ID,
				err,
			)
			c.closeConnection()
			if !c.running {
				break
			}
			return
		}

		msg, err := bufio.NewReader(c.conn).ReadString('\n')
		c.closeConnection()

		if err != nil {
			if !c.running {
				// Error due to shutdown, exit gracefully
				break
			}
			log.Errorf("action: receive_message | result: fail | client_id: %v | error: %v",
				c.config.ID,
				err,
			)
			return
		}

		log.Infof("action: receive_message | result: success | client_id: %v | msg: %v",
			c.config.ID,
			msg,
		)

		// Wait a time between sending one message and the next one
		select {
		case <-time.After(c.config.LoopPeriod):
			// Normal wait
		case <-c.shutdown:
			// Shutdown signal received during wait
			c.running = false
			log.Infof("action: shutdown_during_wait | result: success | client_id: %v", c.config.ID)
			break
		}
	}
	
	// Clean shutdown
	if !c.running {
		log.Infof("action: graceful_shutdown | result: success | client_id: %v", c.config.ID)
	} else {
		log.Infof("action: loop_finished | result: success | client_id: %v", c.config.ID)
	}
}