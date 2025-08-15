# ファイル名: core/model.py

import pandas as pd
from core import data_loader
import logging # loggingを追加

logger = logging.getLogger(__name__)

class AnalysisModel:
    def __init__(self):
        """
        アプリケーション全体で共有するデータを保持するクラス。
        計算ロジックは持たない。
        """
        self.full_history = []
        self.active_ids = []
        self.time_series_df = None
        self.csv_replay_data = None
        self.last_power_spectrums = {}
        self.last_slope_dfs = {}

    def load_csv_data(self, filepaths):
        """CSVを読み込み、自身のデータとして保持する"""
        df, ids = data_loader.load_csvs(filepaths)
        if df is not None and not df.empty:
            self.active_ids = ids
            self.time_series_df = df
            self.csv_replay_data = df
            return True, ids
        else:
            self.active_ids = []
            self.time_series_df = None
            self.csv_replay_data = None
            return False, []

    def reset(self):
        """保持しているすべてのデータをリセットする"""
        logger.info("モデルのデータをリセットします。")
        self.full_history = []
        self.active_ids = []
        self.time_series_df = None
        self.csv_replay_data = None
        self.last_power_spectrums = {}
        self.last_slope_dfs = {}

    # ▼▼▼ このメソッドを丸ごと追加 ▼▼▼
    def add_history_entry(self, data_packet):
        """解析履歴に新しいデータ点を1つ追加する"""
        self.full_history.append(data_packet)

    def is_empty(self):
        """再生・解析用のデータが空かどうかを返す"""
        return not self.full_history