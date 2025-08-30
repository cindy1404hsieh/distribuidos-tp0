#!/usr/bin/env python3
import sys

def generate_docker_compose(output_file, client_count):
    """
    Generates a docker-compose.yaml file with the specified number of clients.
    Manually creates YAML content without external dependencies.
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
    yaml_content.append("      - LOGGING_LEVEL=DEBUG")
    yaml_content.append("    networks:")
    yaml_content.append("      - testing_net")
    yaml_content.append("    volumes:")
    yaml_content.append("      - ./server/config.ini:/config.ini")
    yaml_content.append("")
    
    # Generate clients dynamically with volumes
    for i in range(1, client_count + 1):
        client_name = f"client{i}"
        yaml_content.append(f"  {client_name}:")
        yaml_content.append(f"    container_name: {client_name}")
        yaml_content.append("    image: client:latest")
        yaml_content.append("    entrypoint: /client")
        yaml_content.append("    environment:")
        yaml_content.append(f"      - CLI_ID={i}")
        yaml_content.append("      - CLI_LOG_LEVEL=DEBUG")
        yaml_content.append("    networks:")
        yaml_content.append("      - testing_net")
        yaml_content.append("    depends_on:")
        yaml_content.append("      - server")
        yaml_content.append("    volumes:")
        yaml_content.append(f"      - ./client/config.yaml:/config.yaml")
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
    
    print(f"Generated {output_file} with {client_count} clients:")
    print(f"  - Server with config volume: ./server/config.ini:/config.ini")
    print(f"  - Each client with config volume: ./client/config.yaml:/config.yaml")
    for i in range(1, client_count + 1):
        print(f"  - client{i}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generar-compose.py <output_file> <client_count>")
        print("Example: python3 generar-compose.py docker-compose-dev.yaml 5")
        sys.exit(1)
    
    output_file = sys.argv[1]
    
    try:
        client_count = int(sys.argv[2])
        if client_count < 1:
            raise ValueError("Number of clients must be at least 1")
    except ValueError as e:
        print(f"Error: Invalid number of clients - {e}")
        sys.exit(1)
    
    generate_docker_compose(output_file, client_count)

if __name__ == "__main__":
    main()