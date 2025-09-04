Ejercicio 7:

Para el ejercicio 7 implementé un sistema de lotería donde múltiples agencias envían apuestas y consultan ganadores. El servidor debe esperar que todas las agencias terminen antes de realizar el sorteo.

Cada agencia (cliente) lee su archivo CSV con las apuestas
Las agencias envían las apuestas en batches al servidor
Cuando una agencia termina, envía un mensaje DONE
El servidor espera que todas las agencias envíen DONE
Se ejecuta el sorteo
Las agencias consultan sus ganadores

Protocolo de comunicación
Diseñé un protocolo binario porque es más eficiente que texto plano, ocupa menos ancho de banda, y es más rápido de parsear  con los siguientes tipos de mensajes:
MESSAGE_TYPE_BATCH = 0x02       # Envío de batch de apuestas
MESSAGE_TYPE_DONE = 0x03        # Agencia terminó de enviar
MESSAGE_TYPE_GET_WINNERS = 0x04 # Consultar ganadores
MESSAGE_TYPE_WINNERS = 0x05     # Respuesta con ganadores
MESSAGE_TYPE_NOT_READY = 0x06   # Sorteo aún no realizado

Formato de los mensajes:

Todos los mensajes empiezan con 2 bytes indicando el tamaño
Luego viene el tipo de mensaje (1 byte)
Después los datos específicos de cada mensaje




Estrategia de sincronización
Para manejar la consulta de ganadores implementé polling con reconexión:

El cliente envía DONE y se desconecta
El cliente se reconecta para pedir ganadores
Si el sorteo no está listo, el servidor responde NOT_READY
El cliente espera 100ms y vuelve a intentar
Cuando el sorteo está listo, recibe los ganadores

Por qué polling y no sockets persistentes?
Conozco la alternativa de mantener los sockets abiertos y que el servidor responda cuando esté listo, pero elegí polling porque:

Es más simple de implementar sin concurrencia
Evita mantener múltiples conexiones abiertas en el servidor secuencial

Sincronización del sorteo
El servidor mantiene un contador de agencias que terminaron. Cuando todas las agencias esperadas envían DONE, se ejecuta el sorteo. Esto garantiza que todas las apuestas se consideren.

Cierro todas las conexiones correctamente
Manejo graceful shutdown con SIGTERM
Si falla el envío de DONE, el cliente no continúa

Cómo ejecutar
bash
# Generar compose con 5 clientes
./generar-compose.sh docker-compose-dev.yaml 5

# Levantar el sistema
make docker-compose-up

# Ver logs
make docker-compose-logs

Decisiones de diseño

Reconexión para cada operación: Preferí reconectar para cada mensaje en lugar de mantener conexiones persistentes, ya que simplifica el manejo sin threads.
