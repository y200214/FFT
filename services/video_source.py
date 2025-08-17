# ファイル名: services/video_source.py (新規作成)

import time
import cv2
import logging

logger = logging.getLogger(__name__)

class VideoSource:
    """カメラや動画ファイルからの映像取得を専門に担当するクラス。"""
    
    def __init__(self, source):
        # sourceが数字のみの文字列なら、整数(カメラ番号)に変換する
        processed_source = source
        if isinstance(source, str) and source.isdigit():
            processed_source = int(source)
        
        self.source = source
        self.cap = None
        self._open_source()

    def _open_source(self):
        """映像ソースを開く。失敗した場合は数回リトライする。"""
        # --- ここから修正 ---
        processed_source = self.source
        if isinstance(self.source, str) and self.source.isdigit():
            processed_source = int(self.source)

        for attempt in range(3): # 最大3回試行
            logger.info(f"映像ソース '{self.source}' を開いています... ({attempt + 1}/3)")
            self.cap = cv2.VideoCapture(processed_source)
            if self.cap.isOpened():
                logger.info("映像ソースを正常に開きました。")
                return # 成功したらメソッドを抜ける
            
            logger.warning(f"映像ソース '{self.source}' を開けませんでした。0.5秒後に再試行します。")
            time.sleep(0.5)
        
        # 3回試行しても失敗した場合
        logger.error(f"映像ソース '{self.source}' を開けませんでした。")
        raise IOError(f"Cannot open video source: {self.source}")

    def get_frame(self):
        """
        ソースから1フレーム取得する。

        Returns:
            tuple[bool, numpy.ndarray | None]: 読み込みの成否とフレーム画像。
        """
        if self.cap is None or not self.cap.isOpened():
            return False, None
        
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        """リソースを解放する。"""
        if self.cap:
            logger.info("映像ソースを解放します。")
            self.cap.release()