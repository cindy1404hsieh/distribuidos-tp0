#!/bin/bash

# Script to validate echo server functionality using netcat
# Uses Docker to avoid installing netcat on host machine

# Configuration
SERVER_HOST="server"
SERVER_PORT="12345"
TEST_MESSAGE="Hello from netcat test"
NETWORK_NAME="tp0_testing_net"

# Function to check if server container is running
check_server_running() {
    docker ps --format "table {{.Names}}" | grep -q "^server$"
    return $?
}

# Validate prerequisites
if ! check_server_running; then
    echo "action: test_echo_server | result: fail"
    exit 1
fi

# Create temporary file for response
RESPONSE_FILE=$(mktemp /tmp/echo_response.XXXXXX)
trap "rm -f $RESPONSE_FILE" EXIT

# Run netcat test in a Docker container using busybox
docker run --rm \
    --network="${NETWORK_NAME}" \
    busybox:latest \
    sh -c "echo '${TEST_MESSAGE}' | nc -w 2 ${SERVER_HOST} ${SERVER_PORT}" > "${RESPONSE_FILE}" 2>/dev/null

# Check if docker command succeeded
if [ $? -ne 0 ]; then
    echo "action: test_echo_server | result: fail"
    exit 1
fi

# Read and clean the response
RESPONSE=$(cat "${RESPONSE_FILE}" 2>/dev/null | tr -d '\n\r')
EXPECTED_MESSAGE=$(echo -n "${TEST_MESSAGE}")

# Compare sent and received messages
if [ "${RESPONSE}" = "${EXPECTED_MESSAGE}" ]; then
    echo "action: test_echo_server | result: success"
    exit 0
else
    echo "action: test_echo_server | result: fail"
    exit 1
fi