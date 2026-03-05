cmake_minimum_required(VERSION 3.10)
project(gst-yolo-plugin VERSION 1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(GSTREAMER REQUIRED gstreamer-1.0>=1.0)
pkg_check_modules(GSTREAMER_BASE REQUIRED gstreamer-base-1.0>=1.0)
pkg_check_modules(GSTREAMER_VIDEO REQUIRED gstreamer-video-1.0>=1.0)

find_package(OpenCV REQUIRED)

# LibTorch - Try Python PyTorch first, fallback to standalone
if(DEFINED ENV{PYTHON_TORCH_PATH})
    set(CMAKE_PREFIX_PATH "$ENV{PYTHON_TORCH_PATH}")
    message(STATUS "Using Python PyTorch: $ENV{PYTHON_TORCH_PATH}")
else()
    set(CMAKE_PREFIX_PATH "${CMAKE_SOURCE_DIR}/../libtorch")
    message(STATUS "Using standalone LibTorch: ${CMAKE_SOURCE_DIR}/../libtorch")
endif()
find_package(Torch REQUIRED)

# Include directories
include_directories(
    ${GSTREAMER_INCLUDE_DIRS}
    ${GSTREAMER_BASE_INCLUDE_DIRS}
    ${GSTREAMER_VIDEO_INCLUDE_DIRS}
    ${OpenCV_INCLUDE_DIRS}
    ${TORCH_INCLUDE_DIRS}
)

# Source files
set(SOURCES
    src/gstyoloinference.cpp
    src/yolo_runner.cpp
)

# Create shared library (GStreamer plugin)
add_library(gstyoloinference SHARED ${SOURCES})

# Link libraries
target_link_libraries(gstyoloinference
    ${GSTREAMER_LIBRARIES}
    ${GSTREAMER_BASE_LIBRARIES}
    ${GSTREAMER_VIDEO_LIBRARIES}
    ${OpenCV_LIBS}
    ${TORCH_LIBRARIES}
)

# Set RPATH so plugin can find LibTorch automatically
if(DEFINED ENV{PYTHON_TORCH_PATH})
    set(TORCH_LIB_PATH "$ENV{PYTHON_TORCH_PATH}/lib")
else()
    set(TORCH_LIB_PATH "${CMAKE_SOURCE_DIR}/../libtorch/lib")
endif()

set_target_properties(gstyoloinference PROPERTIES
    BUILD_RPATH "${TORCH_LIB_PATH}"
    INSTALL_RPATH "${TORCH_LIB_PATH}"
    BUILD_RPATH_USE_ORIGIN TRUE
)

# Compiler flags
target_compile_options(gstyoloinference PRIVATE
    -Wall -Wextra
    ${GSTREAMER_CFLAGS_OTHER}
)

# Installation
install(TARGETS gstyoloinference
    LIBRARY DESTINATION /usr/lib/gstreamer-1.0
)

# Print configuration
message(STATUS "GStreamer version: ${GSTREAMER_VERSION}")
message(STATUS "OpenCV version: ${OpenCV_VERSION}")
message(STATUS "LibTorch version: ${TORCH_VERSION}")
message(STATUS "Install directory: /usr/lib/gstreamer-1.0")
