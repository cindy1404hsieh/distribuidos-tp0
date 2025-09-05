import os
import socket
import logging
import signal
import sys
import threading
from .protocol import (
    recv_message,
    send_message,
    deserialize_batch,
    serialize_winners,
    int_to_bytes,
    MESSAGE_TYPE_BATCH,
    MESSAGE_TYPE_DONE,
    MESSAGE_TYPE_GET_WINNERS,
    MESSAGE_TYPE_WINNERS,
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
        self.expected_agencies = int(os.environ.get("EXPECTED_AGENCIES", 5))
        self.agencies_done = set()  # agencias que terminaron
        self.lottery_done = False  # ya hice el sorteo?
        self.winners = {}  # ganadores por agencia
        self.known_agencies = set()

        # Locks para sincronización thread-safe
        self.storage_lock = threading.Lock()  # Para proteger store_bets/load_bets
        self.state_lock = threading.Lock()    # Para proteger estado compartido
        self.lottery_condition = threading.Condition(self.state_lock)  # Para notificar sorteo
        self.max_threads = 10  
        self.active_count = 0
        self.count_lock = threading.Lock()
        # Lista manual de threads activos
        self.active_threads = []
        self.threads_lock = threading.Lock()  # Para proteger la lista de threads
        
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
        """ Server loop - Accepts connections from agencies and processes bets
        Now handles multiple connections concurrently with manual thread management
        """
        try:
            while self._running:
                try:
                    client_sock = self.__accept_new_connection()
                    if client_sock:
                        with self.count_lock:
                            if self.active_count >= self.max_threads:
                                logging.warning(f"Max threads reached ({self.max_threads}), rejecting connection")
                                client_sock.close()
                                continue
                            self.active_count += 1
                        # Crear y lanzar un thread manualmente para cada conexión
                        thread = threading.Thread(
                            target=self.__handle_client_thread,
                            args=(client_sock,),
                            daemon=False  
                        )
                        
                        # Registrar el thread en nuestra lista
                        with self.threads_lock:
                            # Limpiar threads muertos antes de agregar el nuevo
                            self.active_threads = [t for t in self.active_threads if t.is_alive()]
                            self.active_threads.append(thread)
                            logging.debug(f"Active threads count: {len(self.active_threads)}")
                        thread.start()
                        
                except OSError:
                    if not self._running:
                        break
                    raise
        finally:
            self.__cleanup()

    def __cleanup(self):
        """Clean up resources before shutting down"""
        logging.info('action: cleanup_start | result: in_progress')
        
        # Esperar a que terminen todos los threads activos con timeout
        with self.threads_lock:
            threads_to_wait = self.active_threads.copy()
        
        if threads_to_wait:
            logging.info(f'action: waiting_active_threads | count: {len(threads_to_wait)}')
            for thread in threads_to_wait:
                try:
                    # Join con timeout para no bloquear indefinidamente
                    thread.join(timeout=2.0)
                    if thread.is_alive():
                        logging.warning(f'Thread {thread.name} did not finish in time')
                except Exception as e:
                    logging.error(f"Error joining thread: {e}")
        
        # Cerrar el socket del servidor si aún está abierto
        if hasattr(self, '_server_socket'):
            try:
                self._server_socket.close()
                logging.info('action: server_socket_closed | result: success')
            except:
                pass
        
        logging.info('action: graceful_shutdown | result: success')

    def __handle_client_thread(self, client_sock):
        """Thread function para manejar una conexión de cliente"""
        thread_id = threading.current_thread().name
        logging.debug(f"Thread {thread_id} started for client connection")
        
        try:
            self.__handle_client_connection(client_sock)
        except Exception as e:
            logging.error(f"Error in thread {thread_id}: {e}")
        finally:
            # Siempre cerrar el socket del cliente
            try:
                client_sock.close()
                logging.debug(f"Thread {thread_id} closed client socket")
            except:
                pass
            
            # Remover este thread de la lista de activos
            with self.threads_lock:
                current_thread = threading.current_thread()
                if current_thread in self.active_threads:
                    self.active_threads.remove(current_thread)
                    logging.debug(f"Thread {thread_id} removed from active list")
            with self.count_lock:
                self.active_count -= 1

    def __handle_client_connection(self, client_sock):
        """Maneja una conexión del cliente (thread-safe)"""
        try:
            # Recibo el mensaje
            msg = recv_message(client_sock)
            
            # Verifico que tipo de mensaje es
            msg_type = msg[0]
            logging.debug(f"Thread {threading.current_thread().name} - Message type: {msg_type:#x}")
            
            if msg_type == MESSAGE_TYPE_BATCH:
                # Es un batch de apuestas
                self.__handle_batch(client_sock, msg)
                
            elif msg_type == MESSAGE_TYPE_DONE:
                # Agencia terminó de mandar
                logging.debug(f"Thread {threading.current_thread().name} - DONE message received")
                self.__handle_done(client_sock, msg)
                
            elif msg_type == MESSAGE_TYPE_GET_WINNERS:
                # Agencia pide ganadores
                self.__handle_get_winners(client_sock, msg)
                
            else:
                logging.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logging.error(f"Error handling client in thread {threading.current_thread().name}: {e}")

    def __handle_batch(self, client_sock, msg):
        """Procesa un batch de apuestas (thread-safe)"""
        thread_name = threading.current_thread().name
        try:
            # Deserializo el batch
            bets_data = deserialize_batch(msg)
            
            if bets_data:
                agency_id = bets_data[0]['agency_id']
                
                # Proteger acceso a known_agencies
                with self.state_lock:
                    self.known_agencies.add(agency_id)
                    known_count = len(self.known_agencies)
                
                logging.debug(f"Thread {thread_name} - Known agencies: {known_count}")
                
                # Convertir a objetos Bet
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
                
                # Proteger store_bets con lock
                with self.storage_lock:
                    store_bets(bets)
                
                # Responder con el último número
                last_number = bets_data[-1]['number']
                response = int_to_bytes(last_number, 4)
                send_message(client_sock, response)
                
                logging.info(f"action: apuesta_recibida | result: success | cantidad: {len(bets)}")
                
        except Exception as e:
            logging.error(f"Thread {thread_name} - apuesta_recibida | result: fail | error: {e}")
            try:
                response = int_to_bytes(0, 4)
                send_message(client_sock, response)
            except:
                pass

    def __handle_done(self, client_sock, msg):
        """Maneja mensaje DONE (thread-safe)"""
        thread_name = threading.current_thread().name
        try:
            agency_id = msg[1]
            
            # Proteger acceso al estado compartido
            should_do_lottery = False
            
            with self.state_lock:
                self.agencies_done.add(agency_id)
                done_count = len(self.agencies_done)
                known_count = len(self.known_agencies)
                
                logging.debug(f"Thread {thread_name} - Agency {agency_id} done. Total: {done_count}/{known_count}")
                
                # Verificar si debemos hacer el sorteo
                if not self.lottery_done and known_count >= self.expected_agencies:
                    if done_count == known_count:
                        should_do_lottery = True
                        logging.debug(f"Thread {thread_name} - All {known_count} agencies finished. Will start lottery.")
            
            # Enviar ACK
            response = bytes([0x01])
            send_message(client_sock, response)
            
            # Hacer sorteo fuera del lock si es necesario
            if should_do_lottery:
                self.__do_lottery()
                
        except Exception as e:
            logging.error(f"Thread {thread_name} - Error handling DONE: {e}")

    def __do_lottery(self):
        """Realiza el sorteo cuando todas las agencias terminaron"""
        thread_name = threading.current_thread().name
        logging.info("action: sorteo | result: success")
        
        # Cargar todas las apuestas
        with self.storage_lock:
            all_bets = list(load_bets())
        
        logging.debug(f"Thread {thread_name} - Loaded {len(all_bets)} bets for lottery")
        
        # Buscar los ganadores
        winners_temp = {}
        for bet in all_bets:
            if has_won(bet):
                # Si es ganador, agregarlo a su agencia
                if bet.agency not in winners_temp:
                    winners_temp[bet.agency] = []
                winners_temp[bet.agency].append(bet.document)
        
        # Actualizar estado y notificar threads esperando
        with self.lottery_condition:
            self.winners = winners_temp
            self.lottery_done = True
            # Notificar a TODOS los threads esperando el sorteo
            self.lottery_condition.notify_all()
        
        # Debug: mostrar cuántos ganadores por agencia
        for agency, agency_winners in self.winners.items():
            logging.debug(f"Agency {agency}: {len(agency_winners)} winners")

    def __handle_get_winners(self, client_sock, msg):
        """Responde consulta de ganadores (thread-safe)"""
        thread_name = threading.current_thread().name
        try:
            # Extraer el agency_id
            agency_id = msg[1]
            
            # Esperar a que el sorteo esté listo
            with self.lottery_condition:
                # Mientras el sorteo no esté listo Y el servidor siga corriendo
                while not self.lottery_done and self._running:
                    logging.debug(f"Thread {thread_name} - Agency {agency_id} waiting for lottery...")
                    
                    # wait con timeout para poder chequear _running periódicamente
                    notified = self.lottery_condition.wait(timeout=0.5)
                    
                    if not notified:
                        # Timeout expiró, verificar si seguimos corriendo
                        if not self._running:
                            # Server shutting down
                            response = bytes([MESSAGE_TYPE_NOT_READY])
                            send_message(client_sock, response)
                            return
                
                # Salimos del loop: o el sorteo está listo o el server está cerrando
                if not self.lottery_done:
                    response = bytes([MESSAGE_TYPE_NOT_READY])
                    send_message(client_sock, response)
                    return
                
                # Buscar ganadores de esta agencia (dentro del lock)
                agency_winners = self.winners.get(agency_id, [])
            
            # Armar la respuesta (fuera del lock para no bloquear otros threads)
            response = serialize_winners(agency_winners)
            send_message(client_sock, response)
            
            logging.debug(f"Thread {thread_name} - Sent {len(agency_winners)} winners to agency {agency_id}")
            
        except Exception as e:
            logging.error(f"Thread {thread_name} - Error handling GET_WINNERS: {e}")
            # Si hay error, mandar respuesta vacía
            try:
                response = bytes([MESSAGE_TYPE_NOT_READY])
                send_message(client_sock, response)
            except:
                pass

    def __accept_new_connection(self):
        """ Accept new connections
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
            raise