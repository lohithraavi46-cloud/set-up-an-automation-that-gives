"""Local ONNX crop-disease inference service.

The public model is downloaded from Hugging Face on first use and cached by
the Hugging Face client. No uploaded image is sent to a paid AI provider.
"""
import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image

MODEL_REPO = os.getenv("AGRIBRIDGE_DISEASE_MODEL_REPO", "BiernyVR/crop-disease-classifier")
MODEL_FILE = os.getenv("AGRIBRIDGE_DISEASE_MODEL_FILE", "efficientnet_v2_s_best.onnx")
CLASSES_FILE = os.getenv("AGRIBRIDGE_DISEASE_CLASSES_FILE", "classes.json")
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

@lru_cache(maxsize=1)
def model_assets():
    model_path = hf_hub_download(repo_id=MODEL_REPO, filename=MODEL_FILE)
    classes_path = hf_hub_download(repo_id=MODEL_REPO, filename=CLASSES_FILE)
    with open(classes_path, encoding="utf-8") as source:
        raw_classes = json.load(source)
    # Repositories commonly publish either an ordered label list, a
    # {"0": "label"} mapping, or the inverse {"label": 0} mapping.
    # Normalize every shape into {model_index: label}.
    if isinstance(raw_classes, list):
        classes = {index: str(label) for index, label in enumerate(raw_classes)}
    elif isinstance(raw_classes, dict) and isinstance(raw_classes.get("classes"), list):
        classes = {index: str(label) for index, label in enumerate(raw_classes["classes"])}
    elif isinstance(raw_classes, dict) and all(str(key).isdigit() for key in raw_classes):
        classes = {int(key): str(label) for key, label in raw_classes.items()}
    elif isinstance(raw_classes, dict) and all(str(value).isdigit() or isinstance(value, int) for value in raw_classes.values()):
        classes = {int(index): str(label) for label, index in raw_classes.items()}
    else:
        raise ValueError("Unsupported classes.json format; expected labels indexed by class.")
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    return session, classes

def preprocess(image_path: Path) -> np.ndarray:
    image = Image.open(image_path).convert("RGB").resize((224, 224))
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    normalized = (pixels - MEAN) / STD
    return np.expand_dims(np.transpose(normalized, (2, 0, 1)), axis=0).astype(np.float32)

def analyze_image(image_path: Path) -> dict:
    session, classes = model_assets()
    input_name = session.get_inputs()[0].name
    logits = session.run(None, {input_name: preprocess(image_path)})[0][0]
    exp_scores = np.exp(logits - np.max(logits))
    probabilities = exp_scores / exp_scores.sum()
    top_indices = np.argsort(probabilities)[-3:][::-1]
    predictions = [
        {"label": classes.get(int(index), f"Unknown class {int(index)}"), "confidence": round(float(probabilities[index]), 4)}
        for index in top_indices
    ]
    best = predictions[0]
    return {
        "diagnosis": best["label"],
        "confidence": best["confidence"],
        "top_predictions": predictions,
        "model": MODEL_REPO,
    }
