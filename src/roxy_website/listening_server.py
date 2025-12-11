# Now this import will work because Python can see the 'roxy' folder in 'src'
import json
import logging
import os
import sys
from unittest.mock import MagicMock

import docker
from flask import Flask, jsonify, request
from flask_cors import CORS

# Set directory paths to allow imports from the parent 'roxy' module
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Add fake modules to sys.modules to prevent import errors becuase of missing roxy module being imported
sys.modules["cv2"] = MagicMock()
sys.modules["gpiozero"] = MagicMock()
sys.modules["ultralytics"] = MagicMock()

# Import the FlapLock class from the roxy module
from roxy.roxy import FlapLock  # noqa: E402

app = Flask("Docker_controller")
CORS(app)  # Enable CORS for all routes

client = docker.from_env()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONTAINER_NAME = "motion-detector"


# Routes for controlling the Docker container using HTTP
@app.route("/restart_container", methods=["POST"])
def restart_container() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.restart()
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} restarted."}), 200
    except docker.errors.NotFound:
        return jsonify({"status": "error", "message": f"Container {CONTAINER_NAME} not found."}), 404
    except Exception as e:
        logger.error(f"Error restarting container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/stop", methods=["POST"])
@app.route("/stop_container", methods=["POST"])
def stop_container() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.stop()
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} stopped."}), 200
    except docker.errors.NotFound:
        return jsonify({"status": "error", "message": f"Container {CONTAINER_NAME} not found."}), 404
    except Exception as e:
        logger.error(f"Error stopping container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/start", methods=["POST"])
@app.route("/start_container", methods=["POST"])
def start_container() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.start()
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} started."}), 200
    except docker.errors.NotFound:
        return jsonify({"status": "error", "message": f"Container {CONTAINER_NAME} not found."}), 404
    except Exception as e:
        logger.error(f"Error starting container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Lock state to ensure the user know the current state of the lock
@app.route("/get_lock_state", methods=["get"])
def get_lock_state():  # noqa: ANN201 -> Response
    flap_lock = FlapLock()
    state = flap_lock.lock_state
    return jsonify({state})


# Requirement from should have
@app.route("/toggle_lock", methods=["post"])
def toggle_lock() -> None:
    flap_lock = FlapLock()
    state = flap_lock.lock_state
    if state == "LOCKED":
        flap_lock.unlock()
    else:
        flap_lock.lock()


# Updating the config to implment changes from website
@app.route("/update", methods=["POST"])
def update_settings() -> tuple:
    try:
        data = request.json
        with open("~/roxy/src/roxy/config.json", "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "success", "message": "Settings updated."}), 200
    except Exception as e:
        logger.error(f"Error updating settings: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Container status not used
@app.route("/status", methods=["GET"])
def service_status() -> tuple:
    try:
        container = client.containers.get(CONTAINER_NAME)
        # Docker status: running, exited, paused, restarting, etc.
        state = "running" if container.status == "running" else "stopped"
        return jsonify({"state": state, "uptime": container.status}), 200
    except docker.errors.NotFound:
        return jsonify({"state": "stopped", "uptime": "not found"}), 200
    except Exception as e:
        logger.error(f"Error checking status: {e!s}")
        return jsonify({"state": "unknown", "error": str(e)}), 500


# Run server onn local host with port 5000
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)  # noqa: S104
