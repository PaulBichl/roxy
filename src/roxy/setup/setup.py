import os

import gdown
from ultralytics import YOLO

# download nano classification model in .pt format
file_id = "18KgHfnAvAmR7DuYrtCHeY7vpTvVb4oVr"
url = f"https://drive.google.com/uc?id={file_id}"
os.makedirs("./tmp/models", exist_ok=True)
output = "./tmp/models/model.pt"
gdown.download(url, output, quiet=False)

# convert model into NCNN format for edge deployment, is quite fast, no issues with doing this on raspberry pi
model = YOLO("./tmp/models/model.pt")
model.export(format="ncnn")
