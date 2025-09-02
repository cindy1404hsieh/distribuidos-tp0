# Ejercicio 1: 



## Solución Implementada

### Archivos creados
- `generar-compose.sh`: Script bash principal (punto de entrada)
- `generar-compose.py`: Script Python que genera el archivo YAML

### Uso
```bash
# Dar permisos de ejecución (solo primera vez)
chmod +x generar-compose.sh
chmod +x generar-compose.py

# Generar compose con N clientes
./generar-compose.sh <archivo_salida> <cantidad_clientes>

# Ejemplo: generar 5 clientes
./generar-compose.sh docker-compose-dev.yaml 5
```
 

## Testing

### Ejecución de tests automáticos
```
cd ../tp0-tests
source venv/bin/activate
export REPO_PATH=/path/to/tp0-base
make test
```

### Verificación manual
```
./generar-compose.sh test.yaml 3

# Contar clientes generados
grep -c "client[0-9]:" test.yaml  
# Deberia mostrar: 3
```

