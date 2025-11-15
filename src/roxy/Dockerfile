# Use Raspberry Pi OS (Bookworm) + Python base image
FROM ghcr.io/dtcooper/raspberrypi-os:python3.12-bookworm

# Install system dependencies including rpicam apps
RUN apt-get update && apt-get install -y \
    rpicam-apps \
    python3-picamera2 \
    python3-libcamera \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /camera

# Copy Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application
COPY . .

# Make your script executable
RUN chmod +x motion.py

# Start with bash so we can find the error
CMD ["./motion.py"]
