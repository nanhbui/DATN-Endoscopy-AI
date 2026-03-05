#!/bin/bash
# Stream camera from local to GPU server via UDP
# Usage: ./stream_to_server.sh [camera_id] [server_ip]

CAMERA_ID=${1:-0}
SERVER_IP=${2:-10.8.0.7}
PORT=5000

echo "======================================"
echo "  LOCAL CAMERA → GPU SERVER STREAM"
echo "======================================"
echo "Camera: /dev/video${CAMERA_ID}"
echo "Server: ${SERVER_IP}:${PORT}"
echo "Press Ctrl+C to stop"
echo "======================================"

# Stream using GStreamer UDP (low latency) - MJPG camera input
gst-launch-1.0 -v \
    v4l2src device=/dev/video${CAMERA_ID} ! \
    image/jpeg,width=1280,height=720,framerate=30/1 ! \
    jpegdec ! \
    videoconvert ! \
    x264enc tune=zerolatency bitrate=3000 speed-preset=ultrafast key-int-max=30 ! \
    rtph264pay config-interval=1 pt=96 ! \
    udpsink host=${SERVER_IP} port=${PORT}
