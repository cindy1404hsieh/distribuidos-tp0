# Ejercicio 5 - Sistema de Lotería Nacional

## Cómo ejecutar

```bash
# Generar el docker-compose con 5 clientes (agencias)
./generar-compose.sh docker-compose-dev.yaml 5

# Levantar el sistema
make docker-compose-up

# Ver los logs
make docker-compose-logs

# Bajar el sistema
make docker-compose-down
```

## Protocolo de comunicación

El protocolo usa TCP con mensajes binarios. Cada mensaje tiene el formato:
```
[tamaño(2 bytes)][contenido]
```

### Formato de una apuesta
```
[agency_id(1B)][nombre_len(1B)][nombre][apellido_len(1B)][apellido][dni_len(1B)][dni][fecha(10B)][numero(4B)]
```

- Los strings se envían con un byte de longitud seguido de los datos
- La fecha siempre ocupa 10 bytes (formato YYYY-MM-DD)
- Los números se envían en big-endian

### Respuesta del servidor
El servidor responde con el número de la apuesta confirmada (4 bytes).

## Decisiones de diseño

- Cada cliente lee los datos de apuesta de variables de entorno
- Se usa un protocolo binario para eficiencia
- Las funciones `send_all()` y `recv_exact()` manejan short reads/writes
- El servidor usa las funciones provistas `store_bets()` para persistir