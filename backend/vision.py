

import cv2
import numpy as np
import threading
import time
from ultralytics import YOLO
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from config import HUDConfig


@dataclass
class CardDetection:
    
    card_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]
    zone: Optional[str]


class VisionEngine:
    

    def __init__(self, config: HUDConfig):
        self.config = config
        self.model: Optional[YOLO] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self._is_running = False
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._grab_thread: Optional[threading.Thread] = None

    def _update_camera(self):
        
        while self._is_running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                with self._frame_lock:
                    self._latest_frame = frame
            else:
                time.sleep(0.01)

    @staticmethod
    def list_cameras(max_index: int = 6) -> List[int]:

        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    def set_camera(self, device_index: int) -> bool:

        self.stop()
        self.config.camera.device_index = device_index
        return self.start()

    def start(self) -> bool:
        
        if self.model is None:
            try:
                self.model = YOLO(self.config.yolo.model_path)
                print(f"[VisionEngine] Loaded YOLO model from {self.config.yolo.model_path}")
                if hasattr(self.model, 'names'):
                    print(f"[VisionEngine] Model classes: {self.model.names}")
            except Exception as e:
                print(f"[VisionEngine] Failed to load YOLO model: {e}")
                return False

        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.config.camera.device_index)
            if not self.cap.isOpened():
                print(f"[VisionEngine] Failed to open camera {self.config.camera.device_index}")
                return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.camera.fps)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[VisionEngine] Camera opened: {actual_w}x{actual_h}")

        self._is_running = True
        if self._grab_thread is None or not self._grab_thread.is_alive():
            self._grab_thread = threading.Thread(target=self._update_camera, daemon=True)
            self._grab_thread.start()

        return True

    def stop(self):
        
        self._is_running = False
        if self._grab_thread and self._grab_thread.is_alive():
            self._grab_thread.join(timeout=1.0)
            self._grab_thread = None
            
        if self.cap and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            print("[VisionEngine] Camera released")

    def read_frame(self) -> Optional[np.ndarray]:
        
        if not self._is_running:
            return None
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
        return frame

    def detect_cards(self, frame: np.ndarray) -> List[CardDetection]:
        
        if self.model is None:
            return []
        results = self.model(
            frame,
            conf=self.config.yolo.confidence_threshold,
            iou=self.config.yolo.iou_threshold,
            device=self.config.yolo.device if self.config.yolo.device else None,
            verbose=False,
        )

        detections: List[CardDetection] = []

        for result in results:
            if result.boxes is None:
                continue

            boxes = result.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                conf = float(boxes.conf[i].item())
                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                if cls_id in self.config.class_map:
                    card_name = self.config.class_map[cls_id]
                elif hasattr(self.model, 'names') and cls_id in self.model.names:
                    card_name = self.model.names[cls_id]
                else:
                    card_name = f"cls_{cls_id}"
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                zone = self.config.get_zone_for_point(cx, cy)

                detections.append(CardDetection(
                    card_name=card_name,
                    confidence=conf,
                    bbox=(int(x1), int(y1), int(x2), int(y2)),
                    center=(cx, cy),
                    zone=zone,
                ))
        seen: Dict[str, CardDetection] = {}
        for det in detections:
            if det.card_name not in seen or det.confidence > seen[det.card_name].confidence:
                seen[det.card_name] = det

        return list(seen.values())

    @property
    def is_running(self) -> bool:
        return self._is_running and self.cap is not None and self.cap.isOpened()
