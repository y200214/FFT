# ファイル名: app_main.py (修正後)

import tkinter as tk
from tkinter import ttk, messagebox
import platform
from core.constants import *
import matplotlib.pyplot as plt
import os

# --- 外部ファイルインポート ---
from .views.clustering_view import ClusteringView
from .views.spectrum_view import SpectrumView
from .views.radar_view import RadarView
from .views.kmeans_view import KmeansView
from .views.heatmap_view import HeatmapView
from .controller import AppController
from app.ui_manager import UIManager

class AppMainWindow(tk.Tk):
    def __init__(self, log_queue=None):
        super().__init__()
        self.title("リアルタイム解析ダッシュボード")
        self.geometry("1400x900")

        # Controllerインスタンスを作成 (log_queueを渡す)
        self.controller = AppController(self, log_queue) 

        # 2. UIで直接使う変数を定義
        self.mode = tk.StringVar(value="csv")
        self.elapsed_time_var = tk.StringVar(value="経過時間: 0.0s")
        self.playback_time_var = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar()
        self.focus_id_var = tk.StringVar(value="全員")
        self.time_range_var = tk.StringVar(value="30秒窓")
        self.time_input_var = tk.StringVar()
        self.total_time_var = tk.StringVar()

        # 1. 先にUIの骨格とViewを作成する
        self._setup_ui_layout()

        # 2. UIManagerを作成する (viewsが必要なので_setup_ui_layoutの後)
        self.ui_manager = UIManager(self)

        # 3. StateManagerとUIManagerを接続する (ui_managerが必要)
        self.controller.state_manager.add_listener(self.ui_manager.update_ui_by_state)
        
        # 4. ボタンなどのUIコントロールをセットアップする
        self._setup_ui_controls()

        # 5. 初期状態をUIに反映
        initial_state = self.controller.state_manager._state
        self.ui_manager.update_ui_by_state(initial_state)

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui_layout(self):
            """UIの骨格（フレームやタブ）、表示専用ラベルを作成する"""
            # --- 1. 最上部のメインコントロールフレーム ---
            # ▼▼▼ self. を付けて名前を付ける ▼▼▼
            self.main_ctrl_frame = ttk.Frame(self)
            self.main_ctrl_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(5,0))

            # --- フォーカス選択パネル (レイアウト) ---
            self.focus_panel = ttk.LabelFrame(self.main_ctrl_frame, text="フォーカス対象ID（複数選択可）")
            self.focus_panel.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.list_frame = ttk.Frame(self.focus_panel) # ▼▼▼ self. を付ける
            self.list_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)

            # --- 2. 上部のコントロールパネル (レイアウト) ---
            top_panel = ttk.Frame(self)
            top_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
            
            control_panel = ttk.LabelFrame(top_panel, text="コントロールパネル")
            control_panel.pack(side=tk.LEFT, fill='y')
            
            # --- 各種コントロールを配置する「箱」を先に作成 ---
            self.mode_frame = ttk.LabelFrame(control_panel, text="モード")
            self.mode_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')

            self.csv_frame = ttk.LabelFrame(control_panel, text="CSVコントロール")
            self.csv_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')

            self.exec_frame = ttk.LabelFrame(control_panel, text="実行コントロール")
            self.exec_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')
            
            self.other_frame = ttk.LabelFrame(control_panel, text="その他")
            self.other_frame.pack(side=tk.LEFT, padx=5, pady=2, fill='y')

            # --- 3. 中央の再生コントロールパネル (レイアウト) ---
            self.center_panel = ttk.Frame(self) # ▼▼▼ self. を付ける
            self.center_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 5))

            playback_info_frame = ttk.Frame(self.center_panel)
            playback_info_frame.pack(fill=tk.X, expand=True)
            
            ttk.Label(playback_info_frame, textvariable=self.elapsed_time_var).pack(side=tk.LEFT)
            
            self.playback_input_frame = ttk.Frame(playback_info_frame) # ▼▼▼ self. を付ける
            self.playback_input_frame.pack(side=tk.RIGHT)
            ttk.Label(self.playback_input_frame, textvariable=self.total_time_var).pack(side=tk.LEFT)

            # --- 4. メインのタブ表示領域 ---
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

    def _setup_ui_controls(self):
            """UIの操作部品（ボタン、スライダー等）を作成し、イベントを接続する"""
            # --- 1. 最上部のコントロール ---
            self.focus_toggle_button = ttk.Button(self.main_ctrl_frame, text="◀ フォーカスパネルを隠す", command=self.toggle_focus_panel)
            self.focus_toggle_button.pack(side=tk.RIGHT, anchor='n', padx=5, pady=5)

            ttk.Button(self.focus_panel, text="全員を選択", command=lambda: None).pack(side=tk.RIGHT, padx=5, pady=5)
            
            # ▼▼▼ self.list_frame を直接使う ▼▼▼
            self.focus_id_listbox = tk.Listbox(self.list_frame, selectmode=tk.MULTIPLE, height=4)
            self.focus_id_listbox.bind("<<ListboxSelect>>", lambda event: None)
            
            scrollbar = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.focus_id_listbox.yview)
            self.focus_id_listbox.config(yscrollcommand=scrollbar.set)
            
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.focus_id_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # --- 2. 上部コントロールパネルのボタン類 ---
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
            
            save_button = ttk.Button(self.exec_frame, text="グラフ保存", command=lambda: self.controller.save_manager.save_all_plots())
            save_button.pack(side=tk.BOTTOM, padx=5, pady=(5,2))

            self.settings_button = ttk.Button(self.other_frame, text="設定...", command=lambda: None)
            self.settings_button.pack(side=tk.LEFT, padx=5, pady=13)

            # --- 3. 中央の再生コントロール ---
            self.slider = ttk.Scale(self.center_panel, from_=0, to=100, orient=tk.HORIZONTAL) # ▼▼▼ self.center_panel を直接使う
            self.slider.pack(fill=tk.X, expand=True, pady=2)
            self.slider.bind("<ButtonRelease-1>", lambda event: None)
            
            # ▼▼▼ self.playback_input_frame を直接使う (エラー箇所) ▼▼▼
            time_entry = ttk.Entry(self.playback_input_frame, textvariable=self.time_input_var, width=6, justify='right')
            time_entry.pack(side=tk.LEFT)
            time_entry.bind("<Return>", lambda event: None)
            
            self.rt_button = ttk.Button(self.center_panel, text="リアルタイム表示に戻る", state="disabled", command=lambda: None) # ▼▼▼ self.center_panel を直接使う
            self.rt_button.pack(pady=2)

    def show_warning(self, title, message):
        messagebox.showwarning(title, message)

    def show_error(self, title, message):
        messagebox.showerror(title, message)
    
    def show_info(self, title, message):
        messagebox.showinfo(title, message)

    def set_focused_id(self, id_name):
        """
        Controllerからの指示で、指定されたIDをフォーカスリストボックスで選択状態にする。
        """
        all_items = list(self.focus_id_listbox.get(0, tk.END))
        target_idx = -1

        # ★★★ 表示形式の変更に対応 ★★★
        # "1 (ID_0)" のような項目から、"(ID_0)" という部分文字列を含むものを探す
        for i, item in enumerate(all_items):
            if f"({id_name})" in item:
                target_idx = i
                break
            
        if target_idx == -1:
            print(f"WARN: 要求されたID '{id_name}' はリストボックスに存在しません。")
            return

        print(f"INFO: ID '{id_name}' にフォーカスします。")

        self.focus_id_listbox.selection_clear(0, tk.END)
        self.focus_id_listbox.selection_set(target_idx)
        self.focus_id_listbox.event_generate("<<ListboxSelect>>")
        self.notebook.select(self.views["spectrum"])

    def toggle_focus_panel(self):
        """フォーカスパネルの表示/非表示を切り替える"""
        if self.focus_panel.winfo_viewable():
            self.focus_panel.pack_forget()
            self.focus_toggle_button.config(text="▶ フォーカスパネルを表示")
        else:
            self.focus_panel.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.focus_toggle_button.config(text="◀ フォーカスパネルを隠す")

    def clear_all_graphs(self):
        """
        UIManagerに全グラフのクリアを指示する
        """
        if hasattr(self, 'ui_manager'):
            self.ui_manager.clear_all_views()

    def _on_closing(self):
        """ウィンドウが閉じられるときの処理"""
        if messagebox.askokcancel("終了の確認", "アプリケーションを終了しますか？"):
            self.controller.on_app_close() # Controllerのクリーンアップ処理を呼び出す
            self.destroy()

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

