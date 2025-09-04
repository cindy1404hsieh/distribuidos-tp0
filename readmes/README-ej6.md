# Ejercicio 6 - Procesamiento por Batches

## Cómo ejecutar

```bash
# Igual que ej5, pero ahora los clientes leen de archivos CSV
./generar-compose.sh docker-compose-dev.yaml 5
make docker-compose-up
make docker-compose-logs
make docker-compose-down
```

Los archivos CSV deben estar en `.data/agency-N.csv` donde N es el número del cliente.

## Protocolo de batches

El protocolo ahora soporta múltiples apuestas en un mensaje:
```
[tamaño_total(2B)][cantidad_apuestas(2B)][apuesta1][apuesta2]...[apuestaN]
```

Cada apuesta individual mantiene el mismo formato que en ej5:
```
[agency_id(1B)][nombre_len(1B)][nombre][apellido_len(1B)][apellido][dni_len(1B)][dni][fecha(10B)][numero(4B)]
```

### Respuesta del servidor
El servidor responde con el número de la última apuesta del batch (4 bytes).

## Configuración

En `client/config.yaml`:
```
batch:
  maxAmount: 50  # máximo de apuestas por batch
```

Se eligió 50 como default para no exceder los 8KB por mensaje.


## Decisiones de implementación

- Los clientes leen todo el CSV al inicio y lo dividen en batches
- Cada batch se envía en una conexión TCP separada
- El servidor procesa todo el batch y responde con el número de la última apuesta
- Si alguna apuesta falla, el servidor rechaza todo el batch