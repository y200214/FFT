# ファイル名: services/capture_service.py (修正)
from multiprocessing import Queue, Event
import multiprocessing
import time
import logging
import queue

from .realtime_orchestrator import RealtimeOrchestrator
from .process_utils import Status, StatusMessage

logger = logging.getLogger(__name__)

class CaptureService:
    # 【修正】analysis_active イベントを追加
    def __init__(self, data_queue: Queue, frame_queue: Queue, status_queue: Queue, config: dict, analysis_active: Event):
        self.data_queue = data_queue
        self.frame_queue = frame_queue
        self.status_queue = status_queue
        self.config = config
        self.analysis_active = analysis_active # 解析モード切り替え用
        self._process = None
        self.running = multiprocessing.Event()

    def start(self):
        if self._process and self._process.is_alive():
            return

        self.running.set()
        self._process = multiprocessing.Process(
            target=self._run_capture_loop,
            args=(self.data_queue, self.frame_queue, self.status_queue, self.running, self.config, self.analysis_active),
            daemon=True
        )
        self._process.start()
        logger.info("CaptureServiceを開始しました。")

    def stop(self):
        self.running.clear()
        if self._process:
            self._process.join(timeout=2)
            if self._process.is_alive():
                logger.warning("CaptureServiceが時間内に終了せず、強制終了します。")
                self._process.terminate()
            logger.info("CaptureServiceを停止しました。")
        self._process = None

    @staticmethod
    def _run_capture_loop(data_queue, frame_queue, status_queue, running_event, config, analysis_active_event):
        """【別プロセス】映像処理ループ"""
        logger.info("(別プロセス) 映像処理プロセスを開始します。")
        try:
            orchestrator = RealtimeOrchestrator(config)
        except Exception as e:
            logger.error(f"(別プロセス) Orchestratorの初期化に失敗: {e}")
            status_queue.put(StatusMessage(Status.ERROR, f"Orchestratorの初期化に失敗しました:\n{e}"))
            return

        while running_event.is_set():
            try:
                # --- ここからロジックを大幅に変更 ---
                if analysis_active_event.is_set():
                    # 【解析モード】YOLOとMediaPipeを使った本格処理
                    feature_packet, annotated_frame = orchestrator.process_one_frame()
                    if feature_packet:
                        data_queue.put(feature_packet, timeout=1)
                else:
                    # 【プレビューモード】映像取得のみの軽量処理
                    ret, frame = orchestrator.video_source.get_frame()
                    if not ret:
                        logger.info("(別プロセス) 映像ソースの終端に達しました。")
                        status_queue.put(StatusMessage(Status.COMPLETED, "映像の再生が完了しました。"))
                        break
                    annotated_frame = frame # 描画なしの元フレーム
                    feature_packet = None # 特徴量データなし

                # フレームキューへの送信は両モード共通
                if annotated_frame is not None:
                    if not frame_queue.empty():
                        frame_queue.get_nowait()
                    frame_queue.put(annotated_frame, timeout=1)

            except queue.Full:
                logger.warning("(別プロセス) UI側の処理が追いついていないため、フレームをスキップしました。")
                continue
            except Exception as e:
                import traceback
                logger.error(f"(別プロセス) フレーム処理中に予期せぬエラー: {e}\n{traceback.format_exc()}")
                status_queue.put(StatusMessage(Status.ERROR, f"フレーム処理中にエラーが発生しました:\n{e}"))
                time.sleep(1)
            
            time.sleep(0.001) # CPU負荷軽減

        orchestrator.release()
        logger.info("(別プロセス) 映像処理プロセスが正常に終了しました。")