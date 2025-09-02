#!/bin/bash

# Pruebo el echo server
TEST_MSG="Hola mundo"
RESPONSE=$(echo "$TEST_MSG" | docker run --rm --network tp0_testing_net busybox nc server 12345)

if [ "$RESPONSE" = "$TEST_MSG" ]; then
    echo "action: test_echo_server | result: success"
else
    echo "action: test_echo_server | result: fail"
fi