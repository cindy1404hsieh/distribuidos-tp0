#!/usr/bin/env python3

import sys
import yaml

def generate_docker_compose(output_file, client_count):
    """
    Generates a docker-compose.yaml file with the specified number of clients.
    """
    # Base structure of the docker-compose
    compose_config = {
        'name': 'tp0',
        'services': {
            'server': {
                'container_name': 'server',
                'image': 'server:latest',
                'entrypoint': 'python3 /main.py',
                'environment': [
                    'PYTHONUNBUFFERED=1',
                    'LOGGING_LEVEL=DEBUG'
                ],
                'networks': ['testing_net']
            }
        },
        'networks': {
            'testing_net': {
                'ipam': {
                    'driver': 'default',
                    'config': [
                        {'subnet': '172.25.125.0/24'}
                    ]
                }
            }
        }
    }

    # Generate clients dynamically
    for i in range(1, client_count + 1):
        client_name = f'client{i}'
        compose_config['services'][client_name] = {
            'container_name': client_name,
            'image': 'client:latest',
            'entrypoint': '/client',
            'environment': [
                f'CLI_ID={i}',
                'CLI_LOG_LEVEL=DEBUG'
            ],
            'networks': ['testing_net'],
            'depends_on': ['server']
        }

    # Write the YAML file
    with open(output_file, 'w') as f:
        yaml.dump(compose_config, f, default_flow_style=False, sort_keys=False)

    print(f"Generated {output_file} with {client_count} clients:")
    for i in range(1, client_count + 1):
        print(f"  - client{i}")

def main():
    if len(sys.argv) != 3:
        print("Use: python3 generar-compose.py <output_file> <client_count>")
        sys.exit(1)
    
    output_file = sys.argv[1]
    try:
        client_count = int(sys.argv[2])
        if client_count < 1:
            raise ValueError("the number of clients must be greater than 0")
    except ValueError as e:
        print(f"Error: Invalid number of clients - {e}")
        sys.exit(1)
    
    generate_docker_compose(output_file, client_count)

if __name__ == "__main__":
    main()