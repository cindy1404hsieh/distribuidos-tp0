#!/bin/bash

NETWORK_NAME="testing_net"
TEST_MSG="Hola mundo"
RESPONSE=$(docker run --rm --network $NETWORK_NAME busybox sh -c "echo '$TEST_MSG' | nc server 12345")

if [ "$RESPONSE" = "$TEST_MSG" ]; then
    echo "action: test_echo_server | result: success"
else
    echo "action: test_echo_server | result: fail"
fi