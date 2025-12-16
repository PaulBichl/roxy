# Now this import will work because Python can see the 'roxy' folder in 'src'
import json
import logging
import subprocess

import docker
from flask import Flask, jsonify, request
from flask_cors import CORS

json_path = "/home/p5/roxy/src/roxy/config.json"

app = Flask("Docker_controller")
CORS(app)  # Enable CORS for all routes

client = docker.from_env()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONTAINER_NAME = "motion-detector"
run_directory = "/home/p5/roxy/src/roxy/run.sh"


def is_docker_running() -> bool:
    """Check if the Docker container is running."""
    try:
        container = client.containers.get(CONTAINER_NAME)
        return container.status == "running"
    except docker.errors.NotFound:
        return False
    except Exception as e:
        logger.error(f"Error checking Docker status: {e!s}")
        return False


# Routes for controlling the Docker container using HTTP
@app.route("/restart_container", methods=["POST"])
def restart_container() -> dict:
    stop_container()
    start_container()
    return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} restarted."}), 200


@app.route("/stop", methods=["POST"])
@app.route("/stop_container", methods=["POST"])
def stop_container() -> dict:
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
def start_container() -> dict:
    try:
        subprocess.run([run_directory], check=True)
        return jsonify({"status": "success", "message": f"Container {CONTAINER_NAME} started."}), 200
    except Exception as e:
        logger.error(f"Error starting container: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Manual lock overrides (not using Docker)
@app.route("/lock", methods=["post"])
def lock() -> dict:
    if is_docker_running():
        return jsonify({"status": "error", "message": "Docker is running."}), 409

    try:
        # Uses subprocess to ensure GPIO is released after command
        cmd = ["python3", "-c", "from flap_lock_overwrite import FlapLock; FlapLock().lock()"]
        subprocess.run(cmd, cwd="/home/p5/roxy/src/roxy_website", check=True)

        return jsonify({"status": "success", "message": "Device locked."}), 200
    except subprocess.CalledProcessError as e:
        logger.error(f"Error locking device: {e}")
        return jsonify({"status": "error", "message": "Failed to execute lock command"}), 500


@app.route("/unlock", methods=["post"])
def unlock() -> dict:
    try:
        # Uses subprocess to ensure GPIO is released after command
        cmd = ["python3", "-c", "from flap_lock_overwrite import FlapLock; FlapLock().unlock()"]
        subprocess.run(cmd, cwd="/home/p5/roxy/src/roxy_website", check=True)

        return jsonify({"status": "success", "message": "Device locked."}), 200
    except subprocess.CalledProcessError as e:
        logger.error(f"Error locking device: {e}")
        return jsonify({"status": "error", "message": "Failed to execute lock command"}), 500


# Updating the config to implment changes from website (Not used currently)
@app.route("/update", methods=["POST"])
def update_settings() -> dict:
    try:
        data = request.json
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "success", "message": "Settings updated."}), 200
    except Exception as e:
        logger.error(f"Error updating settings: {e!s}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Container status not used
@app.route("/status", methods=["GET"])
def service_status() -> dict:
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
