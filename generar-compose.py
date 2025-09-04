#!/usr/bin/env python3
import sys
from datetime import datetime, timedelta

def generate_docker_compose(output_file, client_count):
    yaml_content = []
    yaml_content.append("name: tp0")
    yaml_content.append("services:")

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
        if i < client_count:
            yaml_content.append("")

    yaml_content.append("")
    yaml_content.append("networks:")
    yaml_content.append("  testing_net:")
    yaml_content.append("    ipam:")
    yaml_content.append("      driver: default")
    yaml_content.append("      config:")
    yaml_content.append("        - subnet: 172.25.125.0/24")

    with open(output_file, 'w') as f:
        f.write('\n'.join(yaml_content))
        f.write('\n')
    print(f"Generated {output_file} with {client_count} clients")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 generar-compose.py <output_file> <client_count>")
        sys.exit(1)

    output_file = sys.argv[1]
    try:
        client_count = int(sys.argv[2])
        if client_count < 0:
            raise ValueError
    except ValueError:
        print("Error: Invalid client count")
        sys.exit(1)

    generate_docker_compose(output_file, client_count)

if __name__ == "__main__":
    main()
