import socket
import logging
import signal
import sys


class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        
        # Flag for graceful shutdown
        self._running = True
        
        # Register signal handler for SIGTERM
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigterm(self, sig, frame):
        """
        Handle SIGTERM signal for graceful shutdown
        """
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
        Server loop with graceful shutdown support

        Server that accept a new connections and establishes a
        communication with a client. After client with communucation
        finishes, servers starts to accept new connections again
        """
        try:
            while self._running:
                try:
                    client_sock = self.__accept_new_connection()
                    if client_sock:
                        self.__handle_client_connection(client_sock)
                except OSError:
                    # This happens when socket is closed during accept()
                    if not self._running:
                        break
                    raise
        finally:
            self.__cleanup()

    def __cleanup(self):
        """
        Clean up resources before shutting down
        """
        if hasattr(self, '_server_socket'):
            try:
                self._server_socket.close()
                logging.info('action: server_socket_closed | result: success')
            except:
                pass
        logging.info('action: graceful_shutdown | result: success')

    def __handle_client_connection(self, client_sock):
        """
        Read message from a specific client socket and closes the socket

        If a problem arises in the communication with the client, the
        client socket will also be closed
        """
        try:
            # TODO: Modify the receive to avoid short-reads
            msg = client_sock.recv(1024).rstrip().decode('utf-8')
            addr = client_sock.getpeername()
            logging.info(f'action: receive_message | result: success | ip: {addr[0]} | msg: {msg}')
            # TODO: Modify the send to avoid short-writes
            client_sock.send("{}\n".format(msg).encode('utf-8'))
        except OSError as e:
            logging.error(f"action: receive_message | result: fail | error: {e}")
        finally:
            client_sock.close()
            logging.debug('action: client_socket_closed | result: success')

    def __accept_new_connection(self):
        """
        Accept new connections

        Function blocks until a connection to a client is made.
        Then connection created is printed and returned
        """
        # Connection arrived
        logging.info('action: accept_connections | result: in_progress')
        try:
            c, addr = self._server_socket.accept()  # Bloquea hasta conexión o cierre
            logging.info(f'action: accept_connections | result: success | ip: {addr[0]}')
            return c
        except OSError:
            # Socket fue cerrado por SIGTERM
            return None