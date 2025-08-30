#!/bin/bash
# Check if the correct number of arguments is provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <output_file> <client_count>"
    echo "Example: $0 docker-compose-dev.yaml 5"
    exit 1
fi

OUTPUT_FILE=$1
CLIENT_COUNT=$2

# Validate that client count is a positive integer
if ! [[ "$CLIENT_COUNT" =~ ^[0-9]+$ ]] || [ "$CLIENT_COUNT" -eq 0 ]; then
    echo "Error: Client count must be a positive integer"
    exit 1
fi

echo "Generating Docker Compose configuration..."
echo "Output file: $OUTPUT_FILE"
echo "Number of clients: $CLIENT_COUNT"

# Call the script to generate the compose file
python3 generar-compose.py "$OUTPUT_FILE" "$CLIENT_COUNT"

# Check if the script executed successfully
if [ $? -eq 0 ]; then
    echo "Docker Compose file generated successfully: $OUTPUT_FILE"
else
    echo "Error: Failed to generate Docker Compose file"
    exit 1
fi