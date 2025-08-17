# ファイル名: services/feature_extractor.py (修正後)

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import logging
from constants import ALL_VARIABLES
from .analysis_utils import calculate_emotion_features, calculate_head_pose_features

logger = logging.getLogger(__name__)

class FeatureExtractor:
    """MediaPipeを使い、人物画像から特徴量を抽出するクラス。"""

    def __init__(self, model_path):
        logger.info(f"MediaPipeモデル '{model_path}' を読み込んでいます...")
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        logger.info("MediaPipeモデルの読み込みが完了しました。")

    def extract(self, person_image):
        """
        人物画像から特徴量を計算して返す。（ヘルパー関数を利用）
        """
        # MediaPipeが要求するRGB形式に変換
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(person_image, cv2.COLOR_BGR2RGB))
        
        # ランドマークを検出
        detection_result = self.landmarker.detect(mp_image)

        # すべての変数を0で初期化
        features = {var: 0.0 for var in ALL_VARIABLES}

        # 感情の計算をヘルパー関数に任せる
        emotion_features = calculate_emotion_features(detection_result.face_blendshapes)
        features.update(emotion_features)

        # 頭の向きの計算をヘルパー関数に任せる
        head_pose_features = calculate_head_pose_features(detection_result.facial_transformation_matrixes)
        features.update(head_pose_features)
        
        return features