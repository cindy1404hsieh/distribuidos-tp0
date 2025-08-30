# Ejercicio 2: Configuración Externa con Volumes

## Descripción
Modificación del cliente y servidor para que los cambios en archivos de configuración no requieran reconstruir las imágenes Docker.

## Solución Implementada

### Archivos modificados
- `client/Dockerfile`: Removida línea `COPY ./client/config.yaml`
- `server/config.ini`: Creado archivo de configuración del servidor
- `generar-compose.py`: Agregados volúmenes para montar configuraciones

### Archivos de configuración
- **Servidor**: `server/config.ini` - Define puerto, backlog y nivel de logging
- **Cliente**: `client/config.yaml` - Define servidor, loops y nivel de logging

## Ejecución

```bash
# Generar docker-compose con volúmenes
./generar-compose.sh docker-compose-dev.yaml 1

# Levantar el sistema
make docker-compose-up

# Modificar configuración sin rebuild (ejemplo)
sed -i 's/LOGGING_LEVEL = DEBUG/LOGGING_LEVEL = INFO/' server/config.ini

# Reiniciar para aplicar cambios (sin reconstruir imagen)
docker compose -f docker-compose-dev.yaml restart server
```

## Decisiones de Diseño

### Volúmenes Docker
Se montan los archivos de configuración como volúmenes:
- Server: `./server/config.ini:/config.ini`
- Client: `./client/config.yaml:/config.yaml`

### Prioridad de Configuración
1. Variables de entorno (si existen)
2. Archivos de configuración (si no hay env vars)

Por esto se removieron `LOGGING_LEVEL` y `CLI_LOG_LEVEL` del docker-compose.

## Testing

```
# Ejecutar solo tests del ejercicio 2
cd ../tp0-tests
source venv/bin/activate
export REPO_PATH=$(pwd)/../tp0-base
pytest test_ej2.py -v
```
