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
  -v /etc/localtime:/etc/localtime:ro \
  -v /etc/timezone:/etc/timezone:ro \
  -e TZ="$(cat /etc/timezone)" \
  -v "$PWD/config.json:/camera/config.json:ro" \
  p5-camera
