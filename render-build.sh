#!/usr/bin/env bash
# exit on error
set -o errexit

# Install TA-Lib C Library (Required for Agent 2: Chart Pattern Intelligence)
if [ ! -d "/opt/render/project/ta-lib" ]; then
    wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
    tar -xzf ta-lib-0.4.0-src.tar.gz
    cd ta-lib
    ./configure --prefix=/usr
    make
    make install
    cd ..
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz
fi

# Upgrade pip and install Python dependencies
pip install --upgrade pip
pip install TA-Lib  # Install the python wrapper AFTER the C library is in place
pip install -r requirements.txt
