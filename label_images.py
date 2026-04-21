# run_once_label_images.py
from ultralytics import YOLO
import cv2, json, os

model = YOLO("yolov8n.pt")   # downloads automatically first run

CATEGORIES = {
    "traffic-lights": "traffic light",
    "buses":          "bus"
}

output = {}

for category, target_label in CATEGORIES.items():
    output[category] = {}
    folder = f"static/tile_captcha/{category}"

    for image_name in os.listdir(folder):
        img_path = os.path.join(folder, image_name)
        img = cv2.imread(img_path)
        
        if img is None:
            print(f"❌ Skipping invalid image: {img_path}")
            continue

        h, w, _ = img.shape
        th, tw = h // 3, w // 3

        correct_tiles = []

        for idx in range(9):
            i, j = divmod(idx, 3)
            tile = img[i*th:(i+1)*th, j*tw:(j+1)*tw]

            results = model(tile, verbose=False)
            labels = [results[0].names[int(c)] for c in results[0].boxes.cls]

            if target_label in labels:
                correct_tiles.append(idx)

        output[category][image_name] = correct_tiles
        print(f"{category}/{image_name} → correct tiles: {correct_tiles}")

with open("static/tile_captcha/labels.json", "w") as f:
    json.dump(output, f, indent=2)

print("Done — labels.json written")