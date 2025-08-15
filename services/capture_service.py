# ファイル名: services/capture_service.py (修正後)

import multiprocessing
import time
import logging
import cv2

# --- 新しい専門クラスと設定管理をインポート ---
from services.video_source import VideoSource
from services.person_tracker import PersonTracker
from services.feature_extractor import FeatureExtractor
from core.config_manager import ConfigManager

def capture_process_entrypoint(data_queue, log_queue, running_event):
    """
    別プロセスで実行されるエントリーポイント。
    ロギングを設定し、CaptureServiceのメインループを実行する。
    """
    # サブプロセス用のロギングを設定
    from utils.logger_config import setup_queue_logging
    setup_queue_logging(log_queue) # このプロセスも「キューに送るだけ」に設定
    
    logger = logging.getLogger(__name__)
    logger.info("キャプチャプロセスを開始します。")

    try:
        # CaptureServiceのインスタンスを作成し、実行
        service = CaptureService(data_queue, running_event)
        service.run()
    except Exception as e:
        logger.critical(f"キャプチャプロセスで致命的なエラー: {e}", exc_info=True)
        #エラー情報をキューに格納
        error_data = {"error": f"映像処理プロセスでエラーが発生しました。\n詳細はログを確認してください。\n\n{e}"}
        data_queue.put(error_data)


class CaptureService:
    def __init__(self, data_queue, running_event):
        """
        リアルタイム映像処理の全てを管理するクラス。

        Args:
            data_queue: 親プロセス(GUI)にデータを送るためのキュー。
            running_event: 実行/停止を制御するためのイベント。
        """
        self.data_queue = data_queue
        self.running_event = running_event
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # --- 設定の読み込み ---
        config = ConfigManager().config.get('realtime_processing', {})
        self.video_source_path = config.get('video_source', 0)
        self.yolo_model_path = config.get('yolo_model_path', 'yolov8n.pt')
        self.mediapipe_model_path = config.get('mediapipe_model_path', 'face_landmarker.task')
        self.device = config.get('device', 'cpu')
        self.show_preview = config.get('show_preview', True)

    def run(self):
        """【別プロセスで実行されるメインループ】"""
        self.logger.info("サービスの実行を開始します。")
        
        # --- 各専門クラスを初期化 ---
        try:
            video_source = VideoSource(self.video_source_path)
            person_tracker = PersonTracker(self.yolo_model_path, device=self.device)
            feature_extractor = FeatureExtractor(self.mediapipe_model_path)
        except Exception as e:
            self.logger.error(f"サービスの初期化に失敗しました: {e}")
            return

        self.logger.info("サービスの初期化が完了し、メインループを開始します。")
        while self.running_event.is_set():
            ret, frame = video_source.get_frame()
            if not ret:
                self.logger.warning("フレームの取得に失敗しました。ループを終了します。")
                break

            # 1. 人物を追跡
            tracked_persons, annotated_frame = person_tracker.track(frame)
            
            # 2. プレビュー表示
            if self.show_preview:
                cv2.imshow("Realtime Analysis Preview", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.running_event.clear() # 'q'キーで終了
                    break

            # 3. 各人物の特徴量を計算
            all_features_data = {'timestamp': time.time()}
            for person in tracked_persons:
                box = person['box']
                person_image = frame[box[1]:box[3], box[0]:box[2]]

                if person_image.size > 0:
                    features = feature_extractor.extract(person_image)
                    all_features_data[person['id']] = features

            # 4. GUIにデータを送信
            if len(tracked_persons) > 0:
                self.data_queue.put(all_features_data)
            
            # time.sleep(0.01) # 適切な待機時間

        # --- リソースの解放 ---
        video_source.release()
        if self.show_preview:
            cv2.destroyAllWindows()
        self.logger.info("メインループが終了し、リソースを解放しました。")