#!/bin/bash

# Run the Python script
LOGFILE="app.log"

echo "******* Starting pipelines ..." >> $LOGFILE

cd "$(dirname "$0")" # navigates to the dir where this script sits

# Resolve uv path across macOS and Linux
if [[ "$(uname)" == "Darwin" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
else
    export PATH="/root/.local/bin:$PATH"
fi

uv run price_fetcher.py --once

if [ $? -eq 0 ]; then
    echo "SUCCESS: TRUE" >> $LOGFILE
else
    echo "SUCCESS: FALSE" >> $LOGFILE
fi