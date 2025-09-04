# Ejercicio 2: Configuración Externa con Volumes

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


## Testing

```
# Ejecutar solo tests del ejercicio 2
cd ../tp0-tests
source venv/bin/activate
export REPO_PATH=$(pwd)/../tp0-base
pytest test_ej2.py -v
```
