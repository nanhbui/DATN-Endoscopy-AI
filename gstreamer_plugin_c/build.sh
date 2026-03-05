#!/bin/bash
# Build script for GStreamer YOLO plugin

set -e  # Exit on error

echo "========================================="
echo "Building GStreamer YOLO Plugin (C++)"
echo "========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check dependencies
echo -e "\n${YELLOW}[1/5] Checking dependencies...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}ERROR: $1 not found${NC}"
        echo "Install with: sudo apt-get install $2"
        exit 1
    fi
    echo -e "${GREEN}✓ $1 found${NC}"
}

check_command "pkg-config" "pkg-config"
check_command "cmake" "cmake"
check_command "g++" "g++"

# Check GStreamer
if ! pkg-config --exists gstreamer-1.0; then
    echo -e "${RED}ERROR: GStreamer not found${NC}"
    echo "Install with: sudo apt-get install libgstreamer1.0-dev"
    exit 1
fi
echo -e "${GREEN}✓ GStreamer found ($(pkg-config --modversion gstreamer-1.0))${NC}"

# Check OpenCV
if ! pkg-config --exists opencv4; then
    echo -e "${YELLOW}WARNING: OpenCV 4 not found, trying OpenCV 3...${NC}"
    if ! pkg-config --exists opencv; then
        echo -e "${RED}ERROR: OpenCV not found${NC}"
        echo "Install with: sudo apt-get install libopencv-dev"
        exit 1
    fi
fi
echo -e "${GREEN}✓ OpenCV found${NC}"

# Check LibTorch
echo -e "\n${YELLOW}[2/5] Checking LibTorch...${NC}"
if [ ! -d "../libtorch" ]; then
    echo -e "${YELLOW}LibTorch not found. Downloading...${NC}"

    # Download LibTorch CPU version
    LIBTORCH_URL="https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.1.0%2Bcpu.zip"

    cd ..
    echo "Downloading from: $LIBTORCH_URL"
    wget -O libtorch.zip "$LIBTORCH_URL"

    echo "Extracting..."
    unzip -q libtorch.zip
    rm libtorch.zip

    cd gstreamer_plugin_c
    echo -e "${GREEN}✓ LibTorch downloaded${NC}"
else
    echo -e "${GREEN}✓ LibTorch found${NC}"
fi

# Create build directory
echo -e "\n${YELLOW}[3/5] Creating build directory...${NC}"
rm -rf build
mkdir build
cd build

# Run CMake
echo -e "\n${YELLOW}[4/5] Running CMake...${NC}"
cmake .. || {
    echo -e "${RED}CMake failed!${NC}"
    exit 1
}

# Build
echo -e "\n${YELLOW}[5/5] Building plugin...${NC}"
make -j$(nproc) || {
    echo -e "${RED}Build failed!${NC}"
    exit 1
}

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN}BUILD SUCCESSFUL!${NC}"
echo -e "${GREEN}=========================================${NC}"

echo -e "\nPlugin built: ${GREEN}build/libgstyoloinference.so${NC}"
echo -e "\nTo install system-wide:"
echo -e "  ${YELLOW}sudo make install${NC}"
echo -e "\nTo test:"
echo -e "  ${YELLOW}export GST_PLUGIN_PATH=\$(pwd)${NC}"
echo -e "  ${YELLOW}gst-inspect-1.0 yoloinference${NC}"
