#!/bin/bash

# GraphRAG Python 3.10 Installer
# This script installs Python 3.10 from source.
# Useful for older servers (CentOS 7, Ubuntu 18.04) where the default Python is old.

set -e

echo "========================================"
echo "   Python 3.10 Automatic Installer"
echo "========================================"

if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root (use sudo)." 1>&2
   exit 1
fi

# Detect Package Manager
if command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
    echo "[*] Detected RedHat/CentOS based system."
elif command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt-get"
    echo "[*] Detected Debian/Ubuntu based system."
else
    echo "Error: Unsupported package manager. This script supports yum and apt-get."
    exit 1
fi

echo "[*] Installing build dependencies..."
if [ "$PKG_MANAGER" == "yum" ]; then
    yum groupinstall -y "Development Tools"
    yum install -y openssl-devel bzip2-devel libffi-devel zlib-devel wget
elif [ "$PKG_MANAGER" == "apt-get" ]; then
    apt-get update
    apt-get install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev
fi

VERSION="3.10.13"
TARBALL="Python-$VERSION.tgz"
URL="https://www.python.org/ftp/python/$VERSION/$TARBALL"

echo "[*] Downloading Python $VERSION..."
cd /usr/src
wget -N $URL

echo "[*] Extracting..."
tar xzf $TARBALL

echo "[*] Configuring and Building (this may take 5-10 minutes)..."
cd "Python-$VERSION"
./configure --enable-optimizations
make -j$(nproc)

echo "[*] Installing (altinstall)..."
make altinstall

echo ""
echo "========================================"
echo "   Installation Complete!"
echo "========================================"
if command -v python3.10 &> /dev/null; then
    echo "[✓] python3.10 is now available."
    echo "You can now run:"
    echo "  ./deploy.sh"
else
    echo "Warning: python3.10 executable not found in path. Please check installation logs."
fi
