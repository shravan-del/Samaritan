#!/bin/bash
echo "Starting Samaritan..."
cd /Users/sathikinasetti/samaritan
python -m samaritan.main &
SERVER_PID=$!
echo "Server running at localhost:8001"
echo "Starting ngrok tunnel..."
ngrok http 8001
kill $SERVER_PID
