import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from core.config_manager import AppConfig, FFTInitialViewConfig, RealtimeSettingsConfig, AnalysisParametersConfig
import dataclasses
from utils.camera_utils import get_available_cameras

class ConfigDialog(tk.Toplevel):
    def __init__(self, parent, config_manager, controller): # controller を受け取るように修正
        super().__init__(parent)
        self.transient(parent)
        self.grab_set()

        self.title("設定")
        self.geometry("450x320")
        
        self.config_manager = config_manager
        self.controller = controller # controller をインスタンス変数として保持
        self.config_data = self.config_manager.config

        # --- 利用可能なカメラのリストを取得 ---
        self.available_cameras = get_available_cameras() # {0: "CamA", 1: "CamB"} のような辞書

        # (UIで使う変数の定義は変更なし)
        self.fft_variable_group = tk.StringVar(value=self.config_data.fft_initial_view.variable_group)
        self.fft_show_fit_line = tk.BooleanVar(value=self.config_data.fft_initial_view.show_fit_line)
        self.rt_video_source = tk.StringVar(value=self.config_data.realtime_settings.video_source)
        self.rt_yolo_path = tk.StringVar(value=self.config_data.realtime_settings.yolo_model_path)
        self.rt_mediapipe_path = tk.StringVar(value=self.config_data.realtime_settings.mediapipe_model_path)
        self.rt_device = tk.StringVar(value=self.config_data.realtime_settings.device)
        self.an_update_interval = tk.IntVar(value=self.config_data.analysis_parameters.UPDATE_INTERVAL_MS)
        self.an_sliding_window = tk.IntVar(value=self.config_data.analysis_parameters.SLIDING_WINDOW_SECONDS)

        self._setup_ui()

    def _setup_ui(self):
        """UI要素を作成して配置する"""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Notebookで設定をタブ分け ---
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # --- 1. FFTタブ ---
        fft_tab = ttk.Frame(notebook, padding=10)
        notebook.add(fft_tab, text="FFT表示")
        fft_frame = ttk.LabelFrame(fft_tab, text="FFTグラフの初期表示設定", padding=10)
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

        # --- 2. リアルタイム処理タブ ---
        rt_tab = ttk.Frame(notebook, padding=10)
        notebook.add(rt_tab, text="リアルタイム処理")
        rt_frame = ttk.LabelFrame(rt_tab, text="リアルタイム処理設定", padding=10)
        rt_frame.pack(fill=tk.X, pady=5)

        ttk.Label(rt_frame, text="映像ソース:").grid(row=0, column=0, sticky='w', pady=2)
        
        # 表示用のカメラ名リストを作成
        camera_display_names = list(self.available_cameras.values())
        
        # 現在保存されているカメラ番号(source)から対応する名前を探す
        current_source_index = self.rt_video_source.get()
        current_display_name = ""
        # 辞書のitems()を使ってループ処理
        for index, name in self.available_cameras.items():
            if str(index) == current_source_index:
                current_display_name = name
                break
        
        # もしconfigの値が現在のカメラリストにない場合（例：古い設定）、そのまま番号を表示
        if not current_display_name and current_source_index:
            current_display_name = f"カメラ {current_source_index}"
            if current_display_name not in camera_display_names:
                camera_display_names.insert(0, current_display_name)

        self.selected_camera_name = tk.StringVar(value=current_display_name)
        
        # Comboboxにはカメラ名を表示
        camera_combo = ttk.Combobox(rt_frame, textvariable=self.selected_camera_name, values=camera_display_names, state='readonly')
        camera_combo.grid(row=0, column=1, sticky='we', pady=2)

        # Comboboxの選択が変更されたら _on_camera_select メソッドを呼ぶ
        camera_combo.bind("<<ComboboxSelected>>", self._on_camera_select)

        ttk.Label(rt_frame, text="YOLOモデルパス:").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(rt_frame, textvariable=self.rt_yolo_path).grid(row=1, column=1, sticky='we', pady=2)
        
        ttk.Label(rt_frame, text="MediaPipeモデルパス:").grid(row=2, column=0, sticky='w', pady=2)
        ttk.Entry(rt_frame, textvariable=self.rt_mediapipe_path).grid(row=2, column=1, sticky='we', pady=2)
        
        ttk.Label(rt_frame, text="デバイス:").grid(row=3, column=0, sticky='w', pady=2)
        ttk.Entry(rt_frame, textvariable=self.rt_device).grid(row=3, column=1, sticky='we', pady=2)
        rt_frame.columnconfigure(1, weight=1)

        # --- 3. 解析パラメータタブ ---
        an_tab = ttk.Frame(notebook, padding=10)
        notebook.add(an_tab, text="解析パラメータ")
        an_frame = ttk.LabelFrame(an_tab, text="解析パラメータ設定", padding=10)
        an_frame.pack(fill=tk.X, pady=5)

        ttk.Label(an_frame, text="UI更新間隔 (ms):").grid(row=0, column=0, sticky='w', pady=2)
        ttk.Entry(an_frame, textvariable=self.an_update_interval).grid(row=0, column=1, sticky='we', pady=2)

        ttk.Label(an_frame, text="スライディング窓 (秒):").grid(row=1, column=0, sticky='w', pady=2)
        ttk.Entry(an_frame, textvariable=self.an_sliding_window).grid(row=1, column=1, sticky='we', pady=2)
        an_frame.columnconfigure(1, weight=1)

        # --- 下部のボタンフレーム (変更なし) ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="キャンセル", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="保存", command=self._on_save).pack(side=tk.RIGHT)

    def _on_camera_select(self, event=None):
        """【追加】カメラが選択されたときにプレビューを更新する"""
        selected_name = self.selected_camera_name.get()
        new_source_index = ""
        for index, name in self.available_cameras.items():
            if name == selected_name:
                new_source_index = str(index)
                break
        
        if new_source_index:
            # Controllerにプレビューの更新を指示
            self.controller.update_preview_source(new_source_index)

    def _on_save(self):
        """「保存」ボタンが押されたときの処理"""
        # _on_camera_select でconfigはメモリ上更新済みなので、
        # 現在のUIの状態からAppConfigオブジェクトを再構築して保存する
        try:
            selected_name = self.selected_camera_name.get()
            source_index_to_save = ""
            for index, name in self.available_cameras.items():
                if name == selected_name:
                    source_index_to_save = str(index)
                    break
            
            if source_index_to_save == "":
                messagebox.showwarning("保存エラー", "有効なカメラが選択されていません。")
                return

            updated_config = AppConfig(
                fft_initial_view=FFTInitialViewConfig(
                    variable_group=self.fft_variable_group.get(),
                    show_fit_line=self.fft_show_fit_line.get()
                ),
                realtime_settings=RealtimeSettingsConfig(
                    video_source=source_index_to_save, # 番号を保存
                    yolo_model_path=self.rt_yolo_path.get(),
                    mediapipe_model_path=self.rt_mediapipe_path.get(),
                    device=self.rt_device.get()
                ),
                analysis_parameters=AnalysisParametersConfig(
                    UPDATE_INTERVAL_MS=self.an_update_interval.get(),
                    SLIDING_WINDOW_SECONDS=self.an_sliding_window.get()
                )
            )
            
            self.config_manager.save_config(updated_config)
            self.destroy()
            
        except tk.TclError as e:
            messagebox.showerror("入力エラー", f"数値項目に正しい数値を入力してください。\n{e}")
        except Exception as e:
            messagebox.showerror("保存エラー", f"設定の保存中にエラーが発生しました:\n{e}")

    def _on_cancel(self):
        """「キャンセル」ボタンが押されたときの処理"""
        # キャンセル時は最後に保存した設定に戻す
        self.controller.config_manager.load_config()
        self.controller.update_preview_source(self.config_manager.config.realtime_settings.video_source)
        self.destroy()