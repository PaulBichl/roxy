#!/bin/bash

echo "Stopping and removing old container..."
docker stop motion-detector
docker rm motion-detector

echo "Starting container..."
docker run -d \
  --name motion-detector \
  --restart unless-stopped \
  --privileged \
  --device /dev/gpiomem \
  --device /dev/gpiochip0 \
  --device /dev/gpiochip1 \
  -v /run/udev:/run/udev:ro \
  -v "$PWD/data.json:/camera/data.json:ro" \
  p5-camera
