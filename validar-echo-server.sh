#!/bin/bash

# Script to validate echo server functionality using netcat

# Configuration
SERVER_HOST="server"
SERVER_PORT="12345"
TEST_MESSAGE="Hello from netcat test"
NETWORK_NAME="tp0_testing_net"

# Run netcat test in a Docker container using busybox
RESPONSE=$(docker run --rm \
    --network="${NETWORK_NAME}" \
    busybox:latest \
    sh -c "echo '${TEST_MESSAGE}' | nc -w 2 ${SERVER_HOST} ${SERVER_PORT}" 2>/dev/null)

# Compare sent and received messages
if [ "${RESPONSE}" = "${TEST_MESSAGE}" ]; then
    echo "action: test_echo_server | result: success"
else
    echo "action: test_echo_server | result: fail"
fi