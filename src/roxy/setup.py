import os

import gdown
from ultralytics import YOLO

# download nano classification model
file_id = "1XBHIwLef2uT6u4mAxOi03UeHbfI8uEOU"
url = f"https://drive.google.com/uc?id={file_id}"
os.makedirs("./tmp/models", exist_ok=True)
output = "./tmp/models/model.pt"
gdown.download(url, output, quiet=False)


# modeel is stored as ./tmp/models/model.pt, convert to ncnn format => better performance on raspberry pi
model = YOLO("./tmp/models/model.pt")
model.export(format="ncnn")
