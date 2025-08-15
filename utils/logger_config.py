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
    # 既存のハンドラをクリアして、重複してログが出力されるのを防ぐ
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # ログをキューに入れるためのハンドラを設定
    queue_handler = QueueHandler(log_queue)
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.DEBUG) # 最も詳細なDEBUGレベルでログを収集

    # --- 外部ライブラリのログレベルを調整 ---
    # 大量の情報を出すライブラリは、エラーや警告(WARNING)のみに絞る
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)


def listener_process(log_queue):
    """ログキューからメッセージを受け取り、ファイルとコンソールに出力する。"""
    # このプロセス専用のロガーを設定
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # コンソール出力用ハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LOG_FORMAT)
    
    # ファイル出力用ハンドラ (ログを 'app_analysis.log' に追記モード('a')で保存)
    file_handler = logging.FileHandler('app_analysis.log', mode='a', encoding='utf-8')
    file_handler.setFormatter(LOG_FORMAT)

    # 作成したハンドラをルートロガーに追加
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)

    root_logger.info("ロギングリスナープロセスを開始しました。")

    while True:
        try:
            record = log_queue.get()
            if record is None:  # 終了シグナル
                break
            # 受け取ったログメッセージを処理
            logger = logging.getLogger(record.name)
            logger.handle(record)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)