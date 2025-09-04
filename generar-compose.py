#!/usr/bin/env python3
import sys
from datetime import datetime, timedelta

def generate_docker_compose(output_file, client_count):
    """
    Generates a docker-compose.yaml file with the specified number of clients.
    Includes volumes for external configuration files and bet environment variables.
    """
    
    # Build the YAML content manually
    yaml_content = []
    
    # Header and services
    yaml_content.append("name: tp0")
    yaml_content.append("services:")
    
    # Server configuration with volume
    yaml_content.append("  server:")
    yaml_content.append("    container_name: server")
    yaml_content.append("    image: server:latest")
    yaml_content.append("    entrypoint: python3 /main.py")
    yaml_content.append("    environment:")
    yaml_content.append("      - PYTHONUNBUFFERED=1")
    #yaml_content.append(f"      - EXPECTED_AGENCIES={client_count}")
    yaml_content.append("    networks:")
    yaml_content.append("      - testing_net")
    yaml_content.append("    volumes:")
    yaml_content.append("      - ./server/config.ini:/config.ini")
    yaml_content.append("")
    
    # Generate clients dynamically with volumes and bet data
    base_date = datetime(1999, 3, 17)  
    base_dni = 30904465  
    base_number = 7574  
    
    for i in range(1, client_count + 1):
        client_name = f"client{i}"
        
        
        birth_date = (base_date + timedelta(days=i*30)).strftime("%Y-%m-%d")
        
        dni = base_dni + i
        bet_number = base_number if i % 3 == 0 else base_number + i 
        
        yaml_content.append(f"  {client_name}:")
        yaml_content.append(f"    container_name: {client_name}")
        yaml_content.append("    image: client:latest")
        yaml_content.append("    entrypoint: /client")
        yaml_content.append("    environment:")
        yaml_content.append(f"      - CLI_ID={i}")
        
        yaml_content.append(f"      - CLI_NOMBRE=Juan_{i}")
        yaml_content.append(f"      - CLI_APELLIDO=Perez_{i}")
        yaml_content.append(f"      - CLI_DOCUMENTO={dni}")
        yaml_content.append(f"      - CLI_NACIMIENTO={birth_date}")
        yaml_content.append(f"      - CLI_NUMERO={bet_number}")
        yaml_content.append("    networks:")
        yaml_content.append("      - testing_net")
        yaml_content.append("    depends_on:")
        yaml_content.append("      - server")
        yaml_content.append("    volumes:")
        yaml_content.append("      - ./client/config.yaml:/config.yaml")
        yaml_content.append(f"      - ./.data/agency-{i}.csv:/data/agency-{i}.csv")
        if i < client_count:  # Add empty line between clients except for the last one
            yaml_content.append("")
    
    # Networks configuration
    yaml_content.append("")
    yaml_content.append("networks:")
    yaml_content.append("  testing_net:")
    yaml_content.append("    ipam:")
    yaml_content.append("      driver: default")
    yaml_content.append("      config:")
    yaml_content.append("        - subnet: 172.25.125.0/24")
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write('\n'.join(yaml_content))
        f.write('\n')  # Add final newline
    
    print(f"Generated {output_file} with {client_count} clients (agencies):")
    print(f"  - Server with config volume: ./server/config.ini:/config.ini")
    
    if client_count > 0:
        print(f"  - {client_count} lottery agencies with bet data:")
        for i in range(1, min(4, client_count + 1)): 
            birth_date = (base_date + timedelta(days=i*30)).strftime("%Y-%m-%d")
            dni = base_dni + i
            bet_number = base_number if i % 3 == 0 else base_number + i
            print(f"    * client{i}: Juan_{i} Perez_{i}, DNI: {dni}, Fecha: {birth_date}, Número: {bet_number}")
        if client_count > 3:
            print(f"    * ... and {client_count - 3} more agencies")
    else:
        print(f"  - Server only (no clients)")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generar-compose.py <output_file> <client_count>")
        print("Example: python3 generar-compose.py docker-compose-dev.yaml 5")
        sys.exit(1)
    
    output_file = sys.argv[1]
    
    try:
        client_count = int(sys.argv[2])
        if client_count < 0:
            raise ValueError("Number of clients must be non-negative")
        if client_count > 5 and client_count != int(sys.argv[2]):
            print("Note: Exercise 5 expects exactly 5 agencies")
    except ValueError as e:
        print(f"Error: Invalid number of clients - {e}")
        sys.exit(1)
    
    generate_docker_compose(output_file, client_count)

if __name__ == "__main__":
    main()