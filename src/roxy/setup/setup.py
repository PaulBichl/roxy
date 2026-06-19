import os
from pathlib import Path

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")

import requests
from ultralytics import YOLO

MODEL_DIR = Path("./tmp/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Download nano classification model in .pt format.
file_id = "18KgHfnAvAmR7DuYrtCHeY7vpTvVb4oVr"
url = f"https://drive.google.com/uc?id={file_id}"
output = MODEL_DIR / "model.pt"
with requests.get(url, stream=True, timeout=30) as response:
    response.raise_for_status()
    with output.open("wb") as file_handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                file_handle.write(chunk)

# Convert model into NCNN format for edge deployment.
model = YOLO(str(output))
model.export(format="ncnn")
