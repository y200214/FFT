# ファイル名: utils/logger_config.py

import logging
import sys
from logging.handlers import QueueHandler
import multiprocessing

# --- ログのフォーマットは共通 ---
LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(processName)s - %(name)s - %(levelname)s - %(message)s'
)

def setup_queue_logging(log_queue):
    """メインプロセスや子プロセス用の設定。ログをキューに送信するだけ。"""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    queue_handler = QueueHandler(log_queue)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.DEBUG)

    # ▼▼▼ ここから追加 ▼▼▼
    # --- 外部ライブラリのログレベルを調整 ---
    # 大量のデバッグ情報を出すライブラリは、INFOレベル以上のみ表示する
    logging.getLogger("PIL").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.INFO)
    logging.getLogger("ultralytics").setLevel(logging.INFO)
    # ▲▲▲ 追加ここまで ▲▲▲

def listener_process(log_queue):
    """ログキューからメッセージを受け取り、ファイルとコンソールに出力する。"""
    # このプロセス専用のロガーを設定
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # ▼▼▼ ここから追加 ▼▼▼
    # --- 外部ライブラリのログレベルを調整 ---
    logging.getLogger("PIL").setLevel(logging.INFO)
    logging.getLogger("matplotlib").setLevel(logging.INFO)
    logging.getLogger("ultralytics").setLevel(logging.INFO)
    # ▲▲▲ 追加ここまで ▲▲▲
    
    # コンソール出力用ハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LOG_FORMAT)
    
    # ファイル出力用ハンドラ
    file_handler = logging.FileHandler('app_analysis.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(LOG_FORMAT)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)

    root_logger.info("ロギングリスナープロセスを開始しました。")

    while True:
        try:
            record = log_queue.get()
            if record is None:
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)