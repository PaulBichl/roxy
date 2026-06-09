FROM ghcr.io/dtcooper/raspberrypi-os:bookworm

# 1. Use PiWheels (CRITICAL for Pi 5 speed)
ENV PIP_EXTRA_INDEX_URL=https://www.piwheels.org/simple

# 2. Install System-level math and image libraries
# These allow pip to skip compiling the heavy stuff.
RUN apt-get update && apt-get install -y \
    rpicam-apps \
    python3-picamera2 \
    python3-numpy \
    python3-opencv \
    python3-pip \
    python3-venv \
    libgl1 \
    libglib2.0-0 \
    libopenblas-dev \
    libcap-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /camera

# 3. Setup Virtual Env with access to the system packages above
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/usr/lib/python3/dist-packages:$PYTHONPATH"

# 4. Install Pip requirements (Should now find pre-compiled wheels)
COPY setup/requirements.txt ./setup/
RUN pip install -r setup/requirements.txt

# 5. Copy and Run Setup
COPY . .
ARG ROXY_SKIP_MODEL_SETUP=1
RUN if [ "$ROXY_SKIP_MODEL_SETUP" = "1" ]; then \
            echo "Skipping setup/setup.py (manual model workflow)"; \
        else \
            python3 setup/setup.py; \
        fi && chmod +x roxy.py

CMD ["python3", "roxy.py"]
