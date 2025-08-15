# ファイル名: service_manager.py (新規作成)

import multiprocessing
import logging
from services.capture_service import capture_process_entrypoint

logger = logging.getLogger(__name__)

class RealtimeServiceManager:
    """
    リアルタイム映像解析サービス（別プロセス）の管理を専門に行うクラス。
    """
    def __init__(self, data_queue, log_queue):
        self.data_queue = data_queue
        self.log_queue = log_queue
        self.running_event = None
        self._capture_process = None

    def start(self):
        """映像解析サービスを開始する。"""
        if self.is_running():
            logger.warning("サービスは既に実行中です。")
            return

        logger.info("リアルタイム解析サービスを開始します...")
        self.running_event = multiprocessing.Event()
        self.running_event.set() # 実行フラグを立てる

        self._capture_process = multiprocessing.Process(
            target=capture_process_entrypoint,
            args=(self.data_queue, self.log_queue, self.running_event),
            name="CaptureServiceProcess"
        )
        self._capture_process.start()
        logger.info("リアルタイム解析サービスが開始されました。")

    def stop(self):
        """映像解析サービスを停止する。"""
        if not self.is_running():
            logger.warning("サービスは実行されていません。")
            return

        logger.info("リアルタイム解析サービスを停止します...")
        if self.running_event:
            self.running_event.clear() # 実行フラグを降ろす

        if self._capture_process:
            self._capture_process.join(timeout=5) # プロセスの終了を待つ
            if self._capture_process.is_alive():
                logger.warning("プロセスが時間内に終了しなかったため、強制終了します。")
                self._capture_process.terminate()
            self._capture_process = None
        
        logger.info("リアルタイム解析サービスが停止しました。")


    def is_running(self):
        """サービスが実行中かを確認する。"""
        return self._capture_process is not None and self._capture_process.is_alive()