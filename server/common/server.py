import socket
import logging
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
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
        self.known_agencies = set()
        
        self.storage_lock = threading.Lock()  # Para proteger store_bets/load_bets
        self.state_lock = threading.Lock()    # Para proteger estado compartido
        self.lottery_condition = threading.Condition(self.state_lock)  # Para notificar sorteo
        
        # Thread pool para manejar conexiones concurrentemente
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.active_connections = []
        
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
        self.executor.shutdown(wait=False)

    def run(self):
        """
        Server loop - Accepts connections from agencies and processes bets
        Now handles multiple connections concurrently
        """
        try:
            while self._running:
                try:
                    client_sock = self.__accept_new_connection()
                    if client_sock:
                        # submit connection to thread pool
                        future = self.executor.submit(self.__handle_client_connection_thread, client_sock)
                        self.active_connections.append(future)
                except OSError:
                    if not self._running:
                        break
                    raise
        finally:
            self.__cleanup()

    def __cleanup(self):
        """Clean up resources before shutting down"""
        # wait for active connections with timeout
        if self.active_connections:
            logging.info('action: waiting_active_connections | result: in_progress')
            for future in self.active_connections:
                try:
                    future.result(timeout=2)
                except:
                    pass
        
        # shutdown executor
        self.executor.shutdown(wait=True, cancel_futures=True)
        
        if hasattr(self, '_server_socket'):
            try:
                self._server_socket.close()
                logging.info('action: server_socket_closed | result: success')
            except:
                pass
        logging.info('action: graceful_shutdown | result: success')

    def __handle_client_connection_thread(self, client_sock):
        """
        Thread wrapper para manejar conexión con logging de errores
        """
        try:
            self.__handle_client_connection(client_sock)
        except Exception as e:
            logging.error(f"Error in client thread: {e}")
        finally:
            try:
                client_sock.close()
            except:
                pass

    def __handle_client_connection(self, client_sock):
        """Maneja una conexion del cliente (ahora thread-safe)"""
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

    def __handle_batch(self, client_sock, msg):
        """Procesa un batch (ahora thread-safe)"""
        try:
            # deserializo el batch
            bets_data = deserialize_batch(msg)
            
            if bets_data:
                agency_id = bets_data[0]['agency_id']
                # proteger acceso a known_agencies
                with self.state_lock:
                    self.known_agencies.add(agency_id)
                    logging.debug(f"known agencies so far: {self.known_agencies}")

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
            
            # proteger store_bets con lock
            with self.storage_lock:
                store_bets(bets)
            
            # respondo con el ultimo numero
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

    def __handle_done(self, client_sock, msg):
        """Maneja DONE message (thread-safe)"""
        try:
            agency_id = msg[1]
            
            # proteger acceso al estado compartido
            should_do_lottery = False
            with self.state_lock:
                self.agencies_done.add(agency_id)
                logging.debug(f"Agency {agency_id} finished. Total done: {len(self.agencies_done)}/{len(self.known_agencies)}")

                # si debemos hacer el sorteo
                if not self.lottery_done and len(self.known_agencies) >= 3:
                    if len(self.agencies_done) == len(self.known_agencies):
                        should_do_lottery = True
                        logging.debug(f"All {len(self.known_agencies)} agencies finished. Will start lottery.")
            
            # Enviar ACK
            response = bytes([0x01])
            send_message(client_sock, response)
            
            # hacer sorteo fuera del lock si es necesario
            if should_do_lottery:
                self.__do_lottery()
                    
        except Exception as e:
            logging.error(f"Error handling DONE: {e}")

    def __do_lottery(self):
        """Hace el sorteo cuando terminaron todas las agencias"""
        logging.info("action: sorteo | result: success")
        
        # crgar apuestas
        with self.storage_lock:
            all_bets = list(load_bets())
        
        logging.debug(f"Loaded {len(all_bets)} bets for lottery")
        
        # busco los ganadores
        winners_temp = {}
        for bet in all_bets:
            if has_won(bet):
                # si es ganador, lo agrego a su agencia
                if bet.agency not in winners_temp:
                    winners_temp[bet.agency] = []
                winners_temp[bet.agency].append(bet.document)
        
        # actualizar estado y notificar threads esperando
        with self.lottery_condition:
            self.winners = winners_temp
            self.lottery_done = True
            # notificar a todos los threads esperando el sorteo
            self.lottery_condition.notify_all()
        
        # debug: cuantos ganadores por agencia
        for agency, winners in self.winners.items():
            logging.debug(f"Agency {agency}: {len(winners)} winners")

    def __handle_get_winners(self, client_sock, msg):
        """Responde consulta de ganadores"""
        try:
            # saco el agency_id
            agency_id = msg[1]
            
            # esperar a que el sorteo este listo
            with self.lottery_condition:
                # si el sorteo no está listo, esperamos
                while not self.lottery_done and self._running:
                    logging.debug(f"Agency {agency_id} waiting for lottery...")
                    # esperar con timeout para poder chequear _running
                    if not self.lottery_condition.wait(timeout=0.5):
                        # timeout, verificar si seguimos corriendo
                        if not self._running:
                            # shutting down
                            response = bytes([MESSAGE_TYPE_NOT_READY])
                            send_message(client_sock, response)
                            return
                
                # el sorteo está listo o el server está cerrando
                if not self.lottery_done:
                    response = bytes([MESSAGE_TYPE_NOT_READY])
                    send_message(client_sock, response)
                    return
                
                # busco ganadores de esta agencia (dentro del lock)
                agency_winners = self.winners.get(agency_id, [])
            
            # armo la respuesta (fuera del lock)
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
            if not self._running:
                logging.debug("Accept interrupted by shutdown")
            return None