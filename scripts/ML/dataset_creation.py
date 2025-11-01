import os
import shutil

from sklearn.model_selection import train_test_split

# ==========================
# CONFIGURATION
#
# manually download datset from:
# https://drive.google.com/drive/folders/1z0j79JHVrOO0lx5NlqUYMM0Ai9Ic5wpZ?usp=drive_link
# remove any unwanted classes beforehand
# extract images from /cat/Olivia and /cat/Roxy to /cat
#
# ==========================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))  # directory where script lives
RAW_DATA_DIR = os.path.join(SCRIPT_DIR, "tmp", "CatFlapData")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "dataset")
SPLIT_RATIO = 0.8

# Auto-detect class folders
CLASS_NAMES = [d for d in os.listdir(RAW_DATA_DIR) if os.path.isdir(os.path.join(RAW_DATA_DIR, d))]

print(f"Detected classes: {CLASS_NAMES}")

# ==========================
# SPLIT AND COPY
# ==========================
for cls in CLASS_NAMES:
    cls_dir = os.path.join(RAW_DATA_DIR, cls)
    imgs = [f for f in os.listdir(cls_dir) if os.path.isfile(os.path.join(cls_dir, f))]
    train_imgs, val_imgs = train_test_split(imgs, train_size=SPLIT_RATIO, random_state=42)

    for phase, file_list in [("train", train_imgs), ("val", val_imgs)]:
        dest_dir = os.path.join(OUTPUT_DIR, phase, cls)
        os.makedirs(dest_dir, exist_ok=True)
        for f in file_list:
            shutil.copy(os.path.join(cls_dir, f), os.path.join(dest_dir, f))
