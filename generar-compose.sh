#!/bin/bash
if [ "$#" -ne 2 ]; then
    echo "Use: $0 <output_file> <client_count>"
    echo "Example: $0 docker-compose.yml 5"
    exit 1
fi

OUTPUT_FILE=$1
CLIENT_COUNT=$2

echo "Generating $OUTPUT_FILE with $CLIENT_COUNT clients..."
echo "Output file: $OUTPUT_FILE"

python3 generar-compose.py "$OUTPUT_FILE" "$CLIENT_COUNT"

echo "Docker Compose file generated successfully: $OUTPUT_FILE"