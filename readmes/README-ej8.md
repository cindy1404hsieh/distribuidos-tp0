# Ejercicio 8:

extendí el servidor para que pueda procesar múltiples agencias de forma concurrente, manejando tanto la recepción de apuestas como la consulta de ganadores sin bloquear la ejecución de otras agencias.

## Patrón de concurrencia

El servidor utiliza **multithreading manual** para manejar cada conexión entrante en un thread separado usando `threading.Thread()`.

Cada batch de apuestas se procesa de forma independiente y los accesos a recursos compartidos como almacenamiento de apuestas o estado del sorteo están protegidos con locks (threading.Lock y threading.Condition).

## Justificación 

Python tiene GIL, por lo que usar threads no genera verdadero paralelismo en CPU-bound.

Nuestro servidor es I/O-bound, así que el overhead de threads es pequeño y suficiente para atender múltiples agencias simultáneamente.

Threads simplifican la concurrencia respecto a procesos o async I/O, evitando cambios significativos en la estructura de la aplicación.

Locks y Condition aseguran consistencia de datos y sincronización del sorteo sin race conditions.

## Flujo 

Cada cliente se conecta y envía mensajes según nuestro protocolo (batch de apuestas, DONE, GET_WINNERS).

Cada conexión se maneja en un **thread independiente creado manualmente**:

MESSAGE_TYPE_BATCH: deserializa apuestas, las almacena con lock, responde con ACK.

MESSAGE_TYPE_DONE: marca la agencia como finalizada y dispara el sorteo si todas las agencias terminaron.

MESSAGE_TYPE_GET_WINNERS: espera al sorteo si aún no se realizó, luego responde con los ganadores de esa agencia.

Sorteo: se ejecuta solo cuando todas las agencias han enviado DONE, actualizando self.winners y notificando a threads esperando.

**Mantengo una lista manual de threads activos** y cierro todas las conexiones esperando que terminen con join() al finalizar (__cleanup).

## consistencia

Locks (storage_lock, state_lock) protegen almacenamiento y estado compartido.

Condition (lottery_condition) permite que los threads que piden ganadores esperen hasta que el sorteo esté listo, evitando busy waiting.

Se manejan excepciones en cada operación para no interrumpir otras conexiones.

## Como ejecutar
### Generar compose con 5 clientes
./generar-compose.sh docker-compose-dev.yaml 5

###  Levantar el sistema
make docker-compose-up

### Ver logs
make docker-compose-logs

###  Detener el sistema
make docker-compose-down

Correcciones
### El cliente cargaba todo el CSV en memoria antes de procesarlo
ahora hace procesamiento por streaming - lectura y envío incremental de batches.

### getWinners() hacía polling constante sin delays
Agregue time.Sleep(100 * time.Millisecond) entre reintentos.

### El servidor creaba threads ilimitados
Contador con limite maximo de 10 threads

### threads bloqueados en recv_message() no detectaban SIGTERM
ahora Socket con timeout + verificación de flag _running.

### el cliente abría/cerraba una conexión TCP por cada batch 
Ahora usa una sola conexión para todos los batches.
Se dejó DONE y GET_WINNERS con conexiones propias porque son mensajes puntuales y no afectan el rendimiento, manteniendo simple la implementación.