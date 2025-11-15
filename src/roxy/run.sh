#!/bin/bash

# Stop and remove any old container with this name
echo "Stopping and removing old container..."
docker stop motion-detector
docker rm motion-detector

# Run the new, correct container in the background
echo "Starting container..."
docker run -d \
  --name motion-detector \
  --restart unless-stopped \
  --privileged \
  -v /run/udev:/run/udev:ro \
  -v "$PWD/data.json:/camera/data.json:ro" \
  p5-camera
