"""YOLO-based object detection provider (graceful skip if weights missing)."""
from __future__ import annotations
import warnings
from pathlib import Path


class YoloProvider:
    def __init__(self, weights_path: Path, conf_threshold: float = 0.35):
        self._model = None
        self._conf = conf_threshold
        try:
            from ultralytics import YOLO  # type: ignore[import]
            if weights_path.exists():
                self._model = YOLO(str(weights_path))
            else:
                warnings.warn(
                    f"YOLO weights not found at {weights_path}. "
                    "L1 detection skipped. Download: yolo download model=yolov8n.pt"
                )
        except ImportError:
            warnings.warn("ultralytics not installed — L1 YOLO detection unavailable.")

    @property
    def available(self) -> bool:
        return self._model is not None

    def detect(self, image_path: Path) -> list[dict]:
        """Run YOLO detection. Returns [] if model unavailable."""
        if self._model is None:
            return []
        results = self._model(str(image_path), conf=self._conf, verbose=False)
        detections = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            img_w, img_h = r.orig_shape[1], r.orig_shape[0]
            for box in boxes:
                cls_id = int(box.cls[0])
                class_name = r.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                detections.append({
                    "class_name": class_name,
                    "confidence": round(conf, 4),
                    "bbox": [round(x1), round(y1), round(x2), round(y2)],
                    "bbox_norm": [
                        round(x1 / img_w, 4), round(y1 / img_h, 4),
                        round(x2 / img_w, 4), round(y2 / img_h, 4),
                    ],
                })
        return detections
