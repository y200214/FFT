# ファイル名: launcher.py

import multiprocessing
import matplotlib.pyplot as plt
from app.app_main import AppMainWindow
import platform
import logging
from utils.logger_config import setup_queue_logging, listener_process

def main():
    log_queue = multiprocessing.Queue(-1) #キューサイズを無制限に
    
    # ▼▼▼ メインプロセスのロギングを「キューに送るだけ」に設定 ▼▼▼
    setup_queue_logging(log_queue) 

    # ログリスナーを別プロセスで開始 (これは変更なし)
    log_listener = multiprocessing.Process(target=listener_process, args=(log_queue,))
    log_listener.daemon = True
    log_listener.start()
    
    logger = logging.getLogger(__name__)
    logger.info("Main application process started.")
    
    app = AppMainWindow(log_queue)
    app.mainloop()
    
    logger.info("Application is closing. Shutting down listener.")
    log_queue.put(None)
    log_listener.join()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    
    # 日本語フォント設定
    system_name = platform.system()
    if system_name == "Windows":
        plt.rcParams['font.family'] = 'Meiryo'
    elif system_name == "Darwin":
        plt.rcParams['font.family'] = 'Hiragino Sans'
    else:
        plt.rcParams['font.family'] = 'IPAexGothic'

    main()