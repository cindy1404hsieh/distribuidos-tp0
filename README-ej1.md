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

## Decisiones de Diseño

#### Decisión
Se optó por generar el archivo YAML manualmente, línea por línea, sin usar la librería `pyyaml`, sin dependencias externas y tener un control total del formato. Se observo una reducción de tiempo de ejecución de los tests. 


### Validación de Entrada

El script valida:
- Número correcto de argumentos
- Cantidad de clientes debe ser un entero positivo
- Mensajes de error descriptivos para guiar al usuario
 

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

