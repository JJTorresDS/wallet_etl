#!/bin/bash

# Run the Python script
LOGFILE="app.log"

echo "******* Starting pipelines ..." >> $LOGFILE

cd "$(dirname "$0")" # navigates to the dir where this script sits
uv run price_fetcher.py --once >> $LOGFILE 2>&1 &