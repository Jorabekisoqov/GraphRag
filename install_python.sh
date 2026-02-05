#!/bin/bash
set -e

# ----------- Configurable variables -----------
PYTHON_VERSION="3.10.13"
OPENSSL_VERSION="1.1.1q"
PREFIX="/usr/local/python3.10"
SRC_DIR="/usr/src"
BUILD_DIR="$SRC_DIR/Python-$PYTHON_VERSION"
OPENSSL_DIR="$SRC_DIR/openssl-$OPENSSL_VERSION"
# ---------------------------------------------

echo "Step 0: Install build dependencies"
yum groupinstall -y "Development Tools" || true
yum install -y wget bzip2 bzip2-devel libffi-devel zlib-devel make || true

echo "Step 1: Download OpenSSL if not exists"
cd $SRC_DIR
if [ ! -f "openssl-$OPENSSL_VERSION.tar.gz" ]; then
    wget https://www.openssl.org/source/openssl-$OPENSSL_VERSION.tar.gz
fi

echo "Step 2: Extract OpenSSL"
rm -rf $OPENSSL_DIR
tar -xvf openssl-$OPENSSL_VERSION.tar.gz

echo "Step 3: Build and install OpenSSL"
cd $OPENSSL_DIR
./config --prefix=/usr/local/openssl --openssldir=/usr/local/openssl shared zlib
make -j$(nproc)
make install
