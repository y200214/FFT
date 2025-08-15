# ファイル名: app_main.py (修正後)

import tkinter as tk
from tkinter import ttk, messagebox
import platform
from core.constants import *
import matplotlib.pyplot as plt
import os
import logging

# --- 外部ファイルインポート ---
from .views.clustering_view import ClusteringView
from .views.spectrum_view import SpectrumView
from .views.radar_view import RadarView
from .views.kmeans_view import KmeansView
from .views.heatmap_view import HeatmapView
from .controller import AppController
from .ui_manager import UIManager

logger = logging.getLogger(__name__)

class AppMainWindow(tk.Tk):
    def __init__(self, log_queue=None):
        super().__init__()
        logger.info("メインウィンドウの初期化を開始します。")
        self.title("リアルタイム解析ダッシュボード")
        self.geometry("1400x900")

        self.controller = AppController(self, log_queue) 

        self.mode = tk.StringVar(value="csv")
        self.elapsed_time_var = tk.StringVar(value="経過時間: 0.0s")
        self.playback_time_var = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar()
        self.focus_id_var = tk.StringVar(value="全員")
        self.time_range_var = tk.StringVar(value="30秒窓")
        self.time_input_var = tk.StringVar()
        self.total_time_var = tk.StringVar()

        self._setup_ui_layout()
        self.ui_manager = UIManager(self)
        self.controller.state_manager.add_listener(self.ui_manager.update_ui_by_state)        
        self._setup_ui_controls()

        initial_state = self.controller.state_manager._state
        self.ui_manager.update_ui_by_state(initial_state)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        logger.info("メインウィンドウの初期化が完了しました。")

    def _setup_ui_layout(self):
        logger.debug("UIレイアウトのセットアップを開始します。")
        self.main_ctrl_frame = ttk.Frame(self)
        self.main_ctrl_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5,0))

        self.focus_panel = ttk.LabelFrame(self.main_ctrl_frame, text="フォーカス対象ID（複数選択可）")
        self.focus_panel.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.list_frame = ttk.Frame(self.focus_panel)
        self.list_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

        top_panel = ttk.Frame(self)
        top_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        control_panel = ttk.LabelFrame(top_panel, text="コントロールパネル")
        control_panel.pack(side=tk.LEFT, fill='y')
        
        self.mode_frame = ttk.LabelFrame(control_panel, text="モード")
        self.mode_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')

        self.csv_frame = ttk.LabelFrame(control_panel, text="CSVコントロール")
        self.csv_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')

        self.exec_frame = ttk.LabelFrame(control_panel, text="実行コントロール")
        self.exec_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')
        
        self.other_frame = ttk.LabelFrame(control_panel, text="その他")
        self.other_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')

        # --- 3. 中央の再生コントロールパネル (レイアウト) ---
        self.center_panel = ttk.Frame(self)
        self.center_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))

        # --- 時間範囲選択 ---
        time_range_frame = ttk.Frame(self.center_panel)
        time_range_frame.pack(pady=2)
        ttk.Label(time_range_frame, text="表示範囲:").pack(side=tk.LEFT)
        ttk.Radiobutton(time_range_frame, text="30秒窓", variable=self.time_range_var, value="30秒窓", command=self.controller._trigger_view_update).pack(side=tk.LEFT)
        ttk.Radiobutton(time_range_frame, text="全区間", variable=self.time_range_var, value="全区間", command=self.controller._trigger_view_update).pack(side=tk.LEFT)
        
        playback_info_frame = ttk.Frame(self.center_panel)
        playback_info_frame.pack(fill=tk.X, expand=True)
        
        ttk.Label(playback_info_frame, textvariable=self.elapsed_time_var).pack(side=tk.LEFT)
        
        self.playback_input_frame = ttk.Frame(playback_info_frame)
        self.playback_input_frame.pack(side=tk.RIGHT)

        time_entry = ttk.Entry(self.playback_input_frame, textvariable=self.time_input_var, width=6, justify='right')
        time_entry.pack(side=tk.LEFT)
        time_entry.bind("<Return>", self.controller.on_time_input_enter)
        
        ttk.Label(self.playback_input_frame, textvariable=self.total_time_var).pack(side=tk.LEFT)

        self.slider = ttk.Scale(self.center_panel, from_=0, to=100, orient=tk.HORIZONTAL)
        self.slider.pack(fill=tk.X, expand=True, pady=2)
        self.slider.bind("<ButtonRelease-1>", self.controller._on_slider_change)
        
        self.rt_button = ttk.Button(self.center_panel, text="リアルタイム表示に戻る", state="disabled", command=self.controller._return_to_realtime)
        self.rt_button.pack(pady=2)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.views = {
            "clustering": ClusteringView(self.notebook, self.controller),
            "spectrum": SpectrumView(self.notebook, self.controller),
            "radar": RadarView(self.notebook, self.controller),
            "kmeans": KmeansView(self.notebook, self.controller),
            "heatmap": HeatmapView(self.notebook, self.controller)
        }
        self.notebook.add(self.views["clustering"], text="階層クラスタリング") 
        self.notebook.add(self.views["spectrum"], text="パワースペクトル")
        self.notebook.add(self.views["radar"], text="レーダーチャート")
        self.notebook.add(self.views["kmeans"], text="k-means法")
        self.notebook.add(self.views["heatmap"], text="ヒートマップ")
        logger.debug("UIレイアウトのセットアップが完了しました。")

    def _setup_ui_controls(self):
        logger.debug("UIコントロールのセットアップを開始します。")
        self.focus_toggle_button = ttk.Button(self.main_ctrl_frame, text="◀ フォーカスパネルを隠す", command=self.toggle_focus_panel)
        self.focus_toggle_button.pack(side=tk.RIGHT, anchor='n', padx=5, pady=5)

        ttk.Button(self.focus_panel, text="全員を選択", command=self.controller.focus_on_all_ids).pack(side=tk.RIGHT, padx=5, pady=5)
        
        self.focus_id_listbox = tk.Listbox(self.list_frame, selectmode=tk.MULTIPLE, height=4)
        self.focus_id_listbox.bind("<<ListboxSelect>>", self.controller.on_focus_id_change)
        
        scrollbar = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.focus_id_listbox.yview)
        self.focus_id_listbox.config(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.focus_id_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Radiobutton(self.mode_frame, text="リアルタイム", variable=self.mode, value="realtime", command=lambda: self.controller.set_mode("realtime")).pack(anchor='w')
        ttk.Radiobutton(self.mode_frame, text="CSV", variable=self.mode, value="csv", command=lambda: self.controller.set_mode("csv")).pack(anchor='w')

        self.load_csv_button = ttk.Button(self.csv_frame, text="CSV読込...", command=self.controller.select_and_load_csvs)
        self.load_csv_button.pack(side=tk.TOP, padx=5, pady=2)
        self.batch_button = ttk.Button(self.csv_frame, text="一括解析", state="disabled")
        self.batch_button.pack(side=tk.TOP, padx=5, pady=2)

        button_frame = ttk.Frame(self.exec_frame)
        button_frame.pack(pady=2)

        self.start_button = ttk.Button(button_frame, text="解析開始", command=self.controller.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.pause_button = ttk.Button(button_frame, text="一時停止", command=self.controller.toggle_pause)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(button_frame, text="停止", command=self.controller.stop_processing)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.reset_button = ttk.Button(button_frame, text="リセット", command=self.controller.reset_application)
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        save_button = ttk.Button(self.exec_frame, text="グラフ保存", command=self.controller.save_plots)
        save_button.pack(side=tk.BOTTOM, padx=5, pady=(5,2))

        self.settings_button = ttk.Button(self.other_frame, text="設定...", command=self.controller.open_settings_dialog)
        self.settings_button.pack(side=tk.LEFT, padx=5, pady=13)

        playback_info_frame = ttk.Frame(self.center_panel)
        playback_info_frame.pack(fill=tk.X, expand=True)
        
        ttk.Label(playback_info_frame, textvariable=self.elapsed_time_var).pack(side=tk.LEFT)
        
        playback_input_frame = ttk.Frame(playback_info_frame)
        playback_input_frame.pack(side=tk.RIGHT)


        # 入力ボックスを先に配置
        time_entry = ttk.Entry(playback_input_frame, textvariable=self.time_input_var, width=6, justify='right')
        time_entry.pack(side=tk.LEFT)
        time_entry.bind("<Return>", self.controller.on_time_input_enter)
        
        # 「s / △△s」のラベルを後に配置
        ttk.Label(playback_input_frame, textvariable=self.total_time_var).pack(side=tk.LEFT)

        self.slider = ttk.Scale(self.center_panel, from_=0, to=100, orient=tk.HORIZONTAL)
        self.slider.pack(fill=tk.X, expand=True, pady=2)
        self.slider.bind("<ButtonRelease-1>", self.controller._on_slider_change)
        
        self.rt_button = ttk.Button(self.center_panel, text="リアルタイム表示に戻る", state="disabled", command=self.controller._return_to_realtime)
        self.rt_button.pack(pady=2)

        logger.debug("UIコントロールのセットアップが完了しました。")

    def show_warning(self, title, message):
        messagebox.showwarning(title, message)

    def show_error(self, title, message):
        messagebox.showerror(title, message)
    
    def show_info(self, title, message):
        messagebox.showinfo(title, message)

    def set_focused_id(self, id_name):
        all_items = list(self.focus_id_listbox.get(0, tk.END))
        target_idx = -1
        for i, item in enumerate(all_items):
            if f"({id_name})" in item:
                target_idx = i
                break
        if target_idx == -1:
            logger.warning(f"要求されたID '{id_name}' はリストボックスに存在しません。")
            return
        logger.info(f"ID '{id_name}' にフォーカスします。")
        self.focus_id_listbox.selection_clear(0, tk.END)
        self.focus_id_listbox.selection_set(target_idx)
        self.focus_id_listbox.event_generate("<<ListboxSelect>>")
        self.notebook.select(self.views["spectrum"])

    def toggle_focus_panel(self):
        if self.focus_panel.winfo_viewable():
            self.focus_panel.pack_forget()
            self.focus_toggle_button.config(text="▶ フォーカスパネルを表示")
        else:
            self.focus_panel.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.focus_toggle_button.config(text="◀ フォーカスパネルを隠す")

    def clear_all_graphs(self):
        if hasattr(self, 'ui_manager'):
            self.ui_manager.clear_all_graphs()

    def _on_closing(self):
        logger.info("ウィンドウのクローズボタンが押されました。")
        if messagebox.askokcancel("終了の確認", "アプリケーションを終了しますか？"):
            logger.info("アプリケーションの終了が確認されました。クリーンアップ処理を開始します。")
            self.controller.on_app_close()
            self.destroy()
        else:
            logger.info("アプリケーションの終了はキャンセルされました。")

# --- 起動部分 ---
if __name__ == '__main__':
    # 日本語フォント設定
    system_name = platform.system()
    if system_name == "Windows":
        plt.rcParams['font.family'] = 'Meiryo'
    elif system_name == "Darwin":
        plt.rcParams['font.family'] = 'Hiragino Sans'
    else:
        # Linux等でのフォント設定例
        plt.rcParams['font.family'] = 'IPAexGothic' 
    plt.rcParams['axes.unicode_minus'] = False

    app = AppMainWindow()
    app.mainloop()

