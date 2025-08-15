# ファイル名: views/config_dialog.py (新規作成)

import tkinter as tk
from tkinter import ttk

class ConfigDialog(tk.Toplevel):
    def __init__(self, parent, config_manager):
        """
        設定ダイアログのウィンドウを作成する。

        Args:
            parent: 親ウィンドウ (AppMainWindow)
            config_manager: 設定を管理するConfigManagerのインスタンス
        """
        super().__init__(parent)
        self.transient(parent) # 親ウィンドウの上に表示されるようにする
        self.grab_set() # このウィンドウにフォーカスを固定する

        self.title("設定")
        self.geometry("400x400") # ◀◀◀ 縦幅を少し広げる
        
        self.config_manager = config_manager
        self.config_data = self.config_manager.config.copy()

        # --- UIで使う変数 ---
        self.fft_variable_group = tk.StringVar(value=self.config_data.get('fft_initial_view', {}).get('variable_group', 'all'))
        self.fft_show_fit_line = tk.BooleanVar(value=self.config_data.get('fft_initial_view', {}).get('show_fit_line', True))
        # ▼▼▼ リアルタイム設定用の変数を追加 ▼▼▼
        self.rt_video_source = tk.StringVar(value=self.config_data.get('realtime_processing', {}).get('video_source', '0'))

        self._setup_ui()

    def _setup_ui(self):
        """UI要素を作成して配置する"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- FFTグラフ設定フレーム ---
        fft_frame = ttk.LabelFrame(main_frame, text="FFTグラフの初期表示設定", padding=10)
        fft_frame.pack(fill=tk.X, pady=5)

        # 変数グループのラジオボタン
        ttk.Label(fft_frame, text="変数グループ:").pack(anchor='w')
        ttk.Radiobutton(fft_frame, text="全て", variable=self.fft_variable_group, value="all").pack(anchor='w', padx=20)
        ttk.Radiobutton(fft_frame, text="感情のみ", variable=self.fft_variable_group, value="emotion").pack(anchor='w', padx=20)
        ttk.Radiobutton(fft_frame, text="行動のみ", variable=self.fft_variable_group, value="behavior").pack(anchor='w', padx=20)

        # 近似直線のチェックボックス
        ttk.Checkbutton(
            fft_frame,
            text="近似直線を表示する",
            variable=self.fft_show_fit_line
        ).pack(anchor='w', pady=(10, 0))
        
        # リアルタイム解析設定
        rt_frame = ttk.LabelFrame(main_frame, text="リアルタイム解析設定", padding=10)
        rt_frame.pack(fill=tk.X, pady=10)

        ttk.Label(rt_frame, text="ビデオソース (カメラ番号 or ファイルパス):").pack(anchor='w')
        ttk.Entry(rt_frame, textvariable=self.rt_video_source).pack(fill=tk.X, padx=5, pady=2)

        # --- 下部のボタンフレーム ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="キャンセル", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="保存", command=self._on_save).pack(side=tk.RIGHT)


    def _on_save(self):
        # --- FFT設定の保存 (既存) ---
        if 'fft_initial_view' not in self.config_data: self.config_data['fft_initial_view'] = {}
        self.config_data['fft_initial_view']['variable_group'] = self.fft_variable_group.get()
        self.config_data['fft_initial_view']['show_fit_line'] = self.fft_show_fit_line.get()
        
        # ▼▼▼ リアルタイム設定の保存ロジックを追加 ▼▼▼
        if 'realtime_processing' not in self.config_data: self.config_data['realtime_processing'] = {}
        self.config_data['realtime_processing']['video_source'] = self.rt_video_source.get()

        self.config_manager.save_config(self.config_data)
        self.destroy()

    def _on_cancel(self):
        """「キャンセル」ボタンが押されたときの処理"""
        self.destroy() # 何もせずウィンドウを閉じる