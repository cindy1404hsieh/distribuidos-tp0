import socket
import logging
import signal
import sys
from .protocol import (
    recv_message, send_message, deserialize_batch, 
    serialize_winners, int_to_bytes,
    MESSAGE_TYPE_BATCH, MESSAGE_TYPE_DONE, 
    MESSAGE_TYPE_GET_WINNERS, MESSAGE_TYPE_WINNERS, 
    MESSAGE_TYPE_NOT_READY
)
from .utils import Bet, store_bets, load_bets, has_won

class Server:
    def __init__(self, port, listen_backlog):
        # Initialize server socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(('', port))
        self._server_socket.listen(listen_backlog)
        
        # Flag for graceful shutdown
        self._running = True
        
        # Para el ejercicio 7
        self.expected_agencies = 5
        self.agencies_done = set()  # agencias que terminaron
        self.lottery_done = False   # ya hice el sorteo?
        self.winners = {}           # ganadores por agencia
        
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
        """Maneja una conexion del cliente"""
        try:
            # recibo el mensaje
            msg = recv_message(client_sock)
            
            # veo que tipo de mensaje es
            msg_type = msg[0]
            logging.debug(f"Message type received: {msg_type:#x} from msg length {len(msg)}")
            if msg_type == MESSAGE_TYPE_BATCH:
                # es un batch de apuestas
                self.__handle_batch(client_sock, msg)
            elif msg_type == MESSAGE_TYPE_DONE:
                logging.debug("DONE message received")
                # agencia termino de mandar
                self.__handle_done(client_sock, msg)
            elif msg_type == MESSAGE_TYPE_GET_WINNERS:
                # agencia pide ganadores
                self.__handle_get_winners(client_sock, msg)
            else:
                logging.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logging.error(f"Error handling client: {e}")
        finally:
            client_sock.close()

    def __handle_batch(self, client_sock, msg):
        """Procesa un batch como antes"""
        try:
            # deserializo el batch
            bets_data = deserialize_batch(msg)
            
            # convierto a objetos Bet
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
            
            # guardo las apuestas
            store_bets(bets)
            
            # respondo con el ultimo numero
            last_number = bets_data[-1]['number']
            response = int_to_bytes(last_number, 4)
            send_message(client_sock, response)
            
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
            
        except Exception as e:
            logging.error(f"action: apuesta_recibida | result: fail | error: {e}")
            # mando error
            response = int_to_bytes(0, 4)
            send_message(client_sock, response)

    def __handle_done(self, client_sock, msg):
        """Maneja cuando una agencia termina"""
        try:
            # saco el agency_id del mensaje
            agency_id = msg[1]
            
            # marco que termino
            self.agencies_done.add(agency_id)
            logging.debug(f"Agency {agency_id} finished. Total done: {len(self.agencies_done)}")
            
            # respondo OK
            response = bytes([0x01])
            send_message(client_sock, response)
            
            # veo si ya terminaron las 5
            if len(self.agencies_done) == self.expected_agencies and not self.lottery_done:
                self.__do_lottery()
                
        except Exception as e:
            logging.error(f"Error handling DONE: {e}")

    def __do_lottery(self):
        """Hace el sorteo cuando terminaron las 5 agencias"""
        logging.info("action: sorteo | result: success")
        
        # cargo todas las apuestas
        all_bets = list(load_bets())
        logging.debug(f"Loaded {len(all_bets)} bets for lottery")
        
        # busco los ganadores
        self.winners = {}
        for bet in all_bets:
            if has_won(bet):
                # si es ganador, lo agrego a su agencia
                if bet.agency not in self.winners:
                    self.winners[bet.agency] = []
                self.winners[bet.agency].append(bet.document)
        
        self.lottery_done = True
        
        # debug: cuantos ganadores por agencia
        for agency, winners in self.winners.items():
            logging.debug(f"Agency {agency}: {len(winners)} winners")

    def __handle_get_winners(self, client_sock, msg):
        """Responde consulta de ganadores"""
        try:
            # saco el agency_id
            agency_id = msg[1]
            
            if not self.lottery_done:
                # sorteo no listo todavia - mando solo el tipo de mensaje
                response = bytes([MESSAGE_TYPE_NOT_READY])
                send_message(client_sock, response)
                logging.debug(f"Agency {agency_id} asked for winners but lottery not ready")
                return
            
            # busco ganadores de esta agencia
            agency_winners = self.winners.get(agency_id, [])
            
            # armo la respuesta
            response = serialize_winners(agency_winners)
            send_message(client_sock, response)
            
            logging.debug(f"Sent {len(agency_winners)} winners to agency {agency_id}")
            
        except Exception as e:
            logging.error(f"Error handling GET_WINNERS: {e}")
            # si hay error, mando respuesta vacia
            try:
                response = bytes([MESSAGE_TYPE_NOT_READY])
                send_message(client_sock, response)
            except:
                pass

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