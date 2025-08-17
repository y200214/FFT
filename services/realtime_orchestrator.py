# services/realtime_orchestrator.py

import time
import logging

# 連携させる各サービスクラスをインポート
from .video_source import VideoSource
from .person_tracker import PersonTracker
from .feature_extractor import FeatureExtractor
from constants import REALTIME_ID_PREFIX # 定数をインポート

logger = logging.getLogger(__name__)

class RealtimeOrchestrator:
    """
    リアルタイム解析のパイプライン全体を管理する司令塔クラス。
    """
    def __init__(self, config):
        """
        configオブジェクトから設定を読み込み、各専門クラスを初期化する。
        """
        self.config = config
        logger.info("リアルタイム処理のオーケストレーターを初期化しています...")

        # 各専門クラスのインスタンスを作成
        self.video_source = VideoSource(self.config['video_source'])
        self.person_tracker = PersonTracker(
            model_path=self.config['yolo_model_path'],
            device=self.config['device']
        )
        self.feature_extractor = FeatureExtractor(
            model_path=self.config['mediapipe_model_path']
        )
        logger.info("オーケストレーターの初期化が完了しました。")


    def process_one_frame(self):
        """
        1フレーム分の処理を実行し、整形されたデータパケットと描画済みフレームを返す。
        """
        ret, frame = self.video_source.get_frame()
        if not ret:
            return None, None

        # 1. 人物追跡
        tracked_persons, annotated_frame = self.person_tracker.track(frame)
        if not tracked_persons:
            # 誰もいなくても、描画済み（この場合は元画像と同じ）フレームは返す
            return {}, annotated_frame

        # 2. 特徴量抽出
        all_features = {'timestamp': time.time()}
        for person in tracked_persons:
            person_id = person['id']
            box = person['box']

            # バウンディングボックスで人物画像を切り抜き
            x1, y1, x2, y2 = box
            person_image = frame[y1:y2, x1:x2]

            # 画像が空でないことを確認
            if person_image.size == 0:
                continue

            # FeatureExtractorに渡して特徴量を取得
            features = self.feature_extractor.extract(person_image)
            all_features[person_id] = features

        return all_features, annotated_frame

    def release(self):
        """
        リソースを解放する。
        """
        self.video_source.release()