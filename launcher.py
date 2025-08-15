# ファイル名: launcher.py

import multiprocessing
import matplotlib.pyplot as plt
from app.app_main import AppMainWindow
import platform
import logging # loggingをインポート
from utils.logger_config import setup_queue_logging, listener_process

def main():
    # ログメッセージをプロセス間で共有するためのキューを作成
    log_queue = multiprocessing.Queue(-1)
    
    # メインプロセスのロギングを「キューにログを送るだけ」の状態に設定
    setup_queue_logging(log_queue) 

    # ログを実際にファイルやコンソールに出力するリスナーを別プロセスで開始
    log_listener = multiprocessing.Process(target=listener_process, args=(log_queue,))
    log_listener.daemon = True
    log_listener.start()
    
    # ロガーを取得して、メインプロセスの開始を記録
    logger = logging.getLogger(__name__)
    logger.info("メインアプリケーションプロセスを開始します。")
    
    # GUIアプリケーションのメインウィンドウを作成
    app = AppMainWindow(log_queue)
    app.mainloop()
    
    # アプリケーション終了時にリスナープロセスも終了させる
    logger.info("アプリケーションを終了します。リスナーをシャットダウンします。")
    log_queue.put(None)
    log_listener.join()

if __name__ == '__main__':
    multiprocessing.freeze_support() # Windowsでプロセスを正しく動作させるために必要
    
    # 日本語フォント設定
    system_name = platform.system()
    if system_name == "Windows":
        plt.rcParams['font.family'] = 'Meiryo'
    elif system_name == "Darwin": # macOS
        plt.rcParams['font.family'] = 'Hiragino Sans'
    else: # Linuxなど
        plt.rcParams['font.family'] = 'IPAexGothic'

    main()
