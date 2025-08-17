# ファイル名: services/person_tracker.py (新規作成)

import cv2
import logging
from ultralytics import YOLO
from constants import ALL_VARIABLES, REALTIME_ID_PREFIX

logger = logging.getLogger(__name__)

class PersonTracker:
    """YOLOv8を使い、フレーム内の人物を検出・追跡するクラス。"""

    def __init__(self, model_path, device='cpu'):
        logger.info(f"YOLOv8モデル '{model_path}' をデバイス '{device}' で読み込んでいます...")
        self.model = YOLO(model_path)
        self.device = device
        logger.info("YOLOv8モデルの読み込みが完了しました。")

    def track(self, frame):
        """
        フレーム内の人物を追跡し、結果を返す。

        Args:
            frame (numpy.ndarray): 入力フレーム画像。

        Returns:
            list[dict]: 追跡された人物情報のリスト。
                        例: [{'id': '1', 'box': [x1, y1, x2, y2]}]
        """
        # `persist=True` は追跡を継続するために重要
        results = self.model.track(frame, persist=True, classes=[0], device=self.device, verbose=False)
        
        tracked_persons = []
        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)

            for box, track_id in zip(boxes, track_ids):
                tracked_persons.append({
                    "id": f"{REALTIME_ID_PREFIX}{track_id}",
                    "box": box
                })
        annotated_frame = results[0].plot()
        return tracked_persons, annotated_frame