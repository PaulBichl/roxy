import os

import gdown
from ultralytics import YOLO

# download nano classification model in .pt format
file_id = "1-jPnj9iWWz7V60TIRJ7TSHhhF6dNQ_c2"
url = f"https://drive.google.com/uc?id={file_id}"
os.makedirs("./models", exist_ok=True)
output = "./models/model.pt"
gdown.download(url, output, quiet=False)

# convert model into NCNN format for edge deployment, is quite fast, no issues with doing this on raspberry pi
model = YOLO("./models/model.pt")
model.export(format="ncnn")
