# CHANGE 1: Use standard Bookworm (Python 3.11) to match the 'apt' packages
FROM ghcr.io/dtcooper/raspberrypi-os:bookworm

# 2. Install System Dependencies
# We include python3-venv and python3-pip explicitly just in case
RUN apt-get update && apt-get install -y \
    rpicam-apps \
    python3-picamera2 \
    python3-numpy \
    python3-pip \
    python3-venv \
    libgl1 \
    libcap-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /camera

# 3. Create a Virtual Environment that includes System Packages
# --system-site-packages is CRITICAL: It lets the venv see picamera2
RUN python3 -m venv --system-site-packages /opt/venv

# 4. Activate the venv for all future commands
ENV PATH="/opt/venv/bin:$PATH"

# 5. FORCE Python to look in the apt library location (Safety Net)
ARG PYTHONPATH=""
ENV PYTHONPATH="/usr/lib/python3/dist-packages:$PYTHONPATH"

# 6. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy App
COPY . .

# 8. Setup
RUN python3 setup.py
RUN chmod +x roxy.py

CMD ["python3", "roxy.py"]
