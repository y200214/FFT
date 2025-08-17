# ファイル名: launcher.py (新しい起動ファイル)

import multiprocessing
import matplotlib.pyplot as plt 
from app.app_main import AppMainWindow
import logging
from utils.logger_config import setup_logging

# アプリケーションが起動する一番最初に、日本語フォントを設定する
import platform
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.family'] = 'Meiryo'
elif system_name == "Darwin": # Mac
    plt.rcParams['font.family'] = 'Hiragino Sans'
else: # Linux
    plt.rcParams['font.family'] = 'IPAexGothic'
if __name__ == '__main__':
    multiprocessing.freeze_support()
    # アプリケーション起動の最初にロギングを設定
    setup_logging()
    app = AppMainWindow()
    app.mainloop()