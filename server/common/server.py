import socket
import logging
import signal
import sys
from .protocol import receive_batch, send_message
from .utils import Bet, store_bets

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        
        # Flag for graceful shutdown
        self._running = True
        
        # Register signal handler for SIGTERM
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigterm(self, sig, frame):
        """Handle SIGTERM signal for graceful shutdown"""
        logging.info('action: sigterm_received | result: in_progress')
        self._running = False
        # Close the server socket to unblock accept()
        if self._server_socket:
            try:
                self._server_socket.close()
                logging.info('action: close_server_socket | result: success')
            except:
                pass

    def run(self):
        """
        Server loop - Accepts connections from agencies and processes bets
        """
        try:
            while self._running:
                try:
                    client_sock = self.__accept_new_connection()
                    if client_sock:
                        self.__handle_client_connection(client_sock)
                except OSError:
                    # Socket closed during accept()
                    if not self._running:
                        break
                    raise
        finally:
            self.__cleanup()

    def __cleanup(self):
        """Clean up resources before shutting down"""
        if hasattr(self, '_server_socket'):
            try:
                self._server_socket.close()
                logging.info('action: server_socket_closed | result: success')
            except:
                pass
        logging.info('action: graceful_shutdown | result: success')

    def __handle_client_connection(self, client_sock):
        try:
            # receive the batch
            bets_data = receive_batch(client_sock)
            
            # convert to Bet objects
            bets = []
            for bet_data in bets_data:
                bet = Bet(
                    agency=str(bet_data['agency_id']),
                    first_name=bet_data['first_name'],
                    last_name=bet_data['last_name'],
                    document=bet_data['dni'],
                    birthdate=bet_data['birth_date'],
                    number=str(bet_data['number'])
                )
                bets.append(bet)
            
            # store all bets in the batch
            store_bets(bets)
            
            from .protocol import int_to_bytes
            last_number = bets_data[-1]['number']
            response = int_to_bytes(last_number, 4) 
            send_message(client_sock, response)
            
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
            
        except Exception as e:
            logging.error(f"action: apuesta_recibida | result: fail | error: {e}")
            try:
                response = int_to_bytes(0, 4)  
                send_message(client_sock, response)
            except:
                pass
        finally:
            client_sock.close()


    def __accept_new_connection(self):
        """
        Accept new connections

        Function blocks until a connection to a client is made.
        Then connection created is printed and returned
        """
        logging.info('action: accept_connections | result: in_progress')
        try:
            c, addr = self._server_socket.accept()  
            logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
        except OSError:
            return None