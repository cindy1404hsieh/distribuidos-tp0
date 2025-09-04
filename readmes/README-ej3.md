# Ejercicio 3: Validación con Netcat

## Descripción
Script bash que valida el funcionamiento del echo server usando netcat, sin instalar herramientas en el host y sin exponer puertos.

## Solución Implementada

### Archivo creado
- `validar-echo-server.sh`: Script que ejecuta netcat dentro de un container Docker

### Estrategia
- Usa container `busybox` (ya presente en el proyecto) que incluye netcat
- Se conecta a la red interna `tp0_testing_net`
- Envía mensaje de prueba y verifica respuesta idéntica

## Ejecución

```bash
# Dar permisos de ejecución
chmod +x validar-echo-server.sh

# Con servidor levantado
make docker-compose-up
./validar-echo-server.sh
# Output: action: test_echo_server | result: success

# Con servidor apagado
make docker-compose-down
./validar-echo-server.sh
# Output: action: test_echo_server | result: fail
```

## Decisiones de Diseño

### Docker para Netcat
- No instala netcat en el host 
- Reutiliza imagen `busybox:latest` del proyecto
- Container temporal con `--rm` para limpieza automática

### Comunicación Interna
- Usa red Docker `tp0_testing_net` 
- No expone puertos al host 
- Conexión directa por nombre de container: `server:12345`

### Validación 
- Verifica que el servidor esté corriendo
- Maneja timeouts con `nc -w 2`
- Limpia archivos temporales con `trap`

## Testing

```bash
# Tests específicos del ejercicio 3
cd ../tp0-tests
source venv/bin/activate
export REPO_PATH=$(pwd)/../tp0-base
pytest test_ej3.py -v
```
