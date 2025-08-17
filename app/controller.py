# ファイル名: controller.py

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd

# 外部ファイルをインポート
from constants import ALL_VARIABLES, EMOTION_VARS, BEHAVIOR_VARS, REALTIME_ID_PREFIX
from core.config_manager import ConfigManager
from core.data_processor import DataProcessor
# Modelをインポート
from core.model import AnalysisModel
from core.analysis_service import AnalysisService 
from core.save_manager import SaveManager
from app.views.config_dialog import ConfigDialog
from .mode_handler.csv_replay_handler import CsvReplayHandler
from .mode_handler.realtime_handler import RealtimeHandler
from services.process_utils import Status


class AppController:
    def __init__(self, app, status_queue):
        self.app = app
        self.status_queue = status_queue # 【追加】
        self.model = AnalysisModel()
        self.data_processor = DataProcessor()
        self.analysis_service = AnalysisService(self.model, self.data_processor)
        self.config_manager = ConfigManager()
        self.save_manager = SaveManager(self)

        # analysis_parametersを一括で読み込んでおく

        self.analysis_params = self.config_manager.config.analysis_parameters
        self.update_interval = self.analysis_params.UPDATE_INTERVAL_MS
        self.sliding_window = self.analysis_params.SLIDING_WINDOW_SECONDS

        # --- ModeHandlerの初期化 ---
        self.mode_handlers = {
            "csv": CsvReplayHandler(self),
            "realtime": RealtimeHandler(self) # status_queueはRealtimeHandler内でcontroller経由で参照
        }
        self.current_mode_handler = self.mode_handlers["csv"]

        # --- 状態変数の整理 ---
        self.after_id = None
        self.status_check_after_id = None # 【追加】ステータス監視用のID
        self.preview_after_id = None        
        self.is_realtime_mode = False
        self.is_display_paused = False
        self.focused_ids = []

        # --- 一括解析と保存関連の状態変数 (変更なし) ---
        self.is_saving_cancelled = False
        self.batch_analysis_complete = False
        self.batch_result_df = None
        self.save_plots_complete = False
        self.save_plots_error = None
        self.progress_dialog = None
        self.save_progress = 0
        self.save_total_steps = 0

    def _on_mode_change(self):
        # 進行中のループをすべて停止
        self._stop_preview_loop()
        self.stop_update_loop()

        if self.current_mode_handler:
            self.current_mode_handler.on_mode_deselected()

        new_mode = self.app.mode.get()
        self.current_mode_handler = self.mode_handlers[new_mode]
        self.current_mode_handler.on_mode_selected()

    def load_csvs(self):
        """CSVファイルを読み込み、Modelに渡す"""
        filepaths = filedialog.askopenfilenames(
            title="再生するCSVファイルを選択（複数選択可）",
            filetypes=[("CSV files", "*.csv")]
        )
        if not filepaths: return

        success, ids = self.model.load_csv_data(filepaths)

        if not success:
            self.app.ui_manager.show_error("エラー", "ファイルの読み込みまたはIDの推定に失敗しました。")
        else:
            self.app.ui_manager.update_focus_listbox(ids)
            self.focus_on_all_ids()
        self._on_mode_change()

    def start_analysis(self):
        # 【修正】プレビューを停止してから解析を開始
        self._stop_preview_loop()
        self.current_mode_handler.start()
        self.app.ui_manager.update_control_buttons_state()
        if isinstance(self.current_mode_handler, RealtimeHandler):
            self._check_status_queue()

    def stop_analysis(self):
        """解析を停止する"""
        # 【追加】ステータスキューの監視を停止
        if self.status_check_after_id:
            self.app.after_cancel(self.status_check_after_id)
            self.status_check_after_id = None
            
        self.current_mode_handler.stop()
        self.app.ui_manager.update_control_buttons_state()

        if isinstance(self.current_mode_handler, RealtimeHandler):
            self._start_preview_loop()

    def toggle_pause(self):
        """一時停止と再開を切り替える"""
        self.current_mode_handler.toggle_pause()
        self.app.ui_manager.update_control_buttons_state()

    def start_update_loop(self):
        """定期的なデータ処理とUI更新ループを開始する"""
        self.stop_update_loop() # 既存のループがあれば停止
        self.process_data_and_update_views()

    def stop_update_loop(self):
        """更新ループを停止する"""
        if self.after_id:
            self.app.after_cancel(self.after_id)
            self.after_id = None

    def _start_preview_loop(self):
        """【修正】リアルタイムプレビューの映像更新ループを開始する"""
        self._stop_preview_loop()  # 既存のループがあれば停止
        
        def loop():
            # プレビュー中（is_running=Falseのリアルタイムモード）かチェック
            if self.app.mode.get() == "realtime" and not self.current_mode_handler.is_running:
                latest_frame = self.current_mode_handler.get_latest_frame()
                if latest_frame is not None:
                    self.app.views["video"].update_frame(latest_frame)
                # 次の描画を予約
                self.preview_after_id = self.app.after(33, loop) # 約30fps
        
        loop()

    def _stop_preview_loop(self):
        """【修正】プレビューの映像更新ループを停止する"""
        if self.preview_after_id:
            self.app.after_cancel(self.preview_after_id)
            self.preview_after_id = None

    def _process_and_store_features(self, full_slice, sliding_slice=None):
        """
        【変更】AnalysisServiceに処理を委譲する
        """
        return self.analysis_service.process_and_store_features(full_slice, sliding_slice)

    def save_plots(self):
        """SaveManagerにグラフ保存処理を依頼する"""
        # 保存処理を開始する前に、関連する状態フラグをリセットする
        self.is_saving_cancelled = False
        self.save_plots_complete = False
        self.save_plots_error = None
        self.save_progress = 0
        # どの時点のデータで保存するかをスライダーの位置から決定する
        save_index = int(self.app.slider.get())
        if not self.model.full_history or save_index >= len(self.model.full_history):
            self.app.ui_manager.show_error("保存エラー", "保存できる有効なデータがありません。")
            return
        
        timestamp_to_save = self.model.full_history[save_index]['timestamp']
        self.save_manager.save_all_plots(timestamp_to_save)

    def _on_slider_change(self, event):
        """スライダーが操作されたときの処理"""
        self.stop_update_loop()
        self.is_realtime_mode = False
        self.is_display_paused = False

        self.app.ui_manager.set_rt_button_state('normal')
        
        timestamp_index = int(self.app.slider.get())
        self.process_data_and_update_views(history_index=timestamp_index)

    def _return_to_realtime(self):
        """リアルタイム表示に復帰する"""
        self.is_display_paused = False
        self.is_realtime_mode = True
        
        self.app.ui_manager.set_rt_button_state('disabled')
        self.app.ui_manager.set_pause_button_state("一時停止", self.toggle_pause)
        self.app.ui_manager.clear_time_inputs()
        
        self.start_update_loop()

    def reset_all_data(self):
        """
        全てのデータとUIの状態を初期化する
        """
        if self.current_mode_handler.is_running:
            self.stop_analysis()

        if not self.app.ui_manager.ask_yes_no("確認", "本当にすべてのデータをリセットしますか？\nこの操作は元に戻せません。"):
            return

        print("INFO: 全てのデータをリセットします。")

        # Modelのデータをリセット
        self.model.full_history = []
        self.model.active_ids = []
        self.model.time_series_df = None
        self.model.csv_replay_data = None
        self.model.last_power_spectrums = {}
        self.model.last_slope_dfs = {}

        # Controllerの状態変数をリセット
        self.focused_ids = []
        self.batch_result_df = None

        self.app.ui_manager.reset_ui_state() # UIManagerにUIリセットを依頼
        self.app.ui_manager.clear_all_views() 
        self.app.ui_manager.show_info("完了", "すべてのデータをリセットしました。")

    def on_time_input_enter(self, event):
        """ユーザーが再生時間ボックスでEnterを押したときの処理"""
        if not self.model.full_history: return

        try:
            target_time = float(self.app.time_input_var.get())
        except (ValueError, TypeError):
            self.app.ui_manager.show_warning("入力エラー", "数値を入力してください。")
            self._update_time_inputs_to_current()
            return

        timestamps = [dp['timestamp'] for dp in self.model.full_history]
        
        # 入力値が有効範囲内かチェック
        if not (timestamps[0] <= target_time <= timestamps[-1]):
            self.app.ui_manager.show_warning("入力エラー", f"時間は {timestamps[0]:.1f} から {timestamps[-1]:.1f} の間で入力してください。")
            self._update_time_inputs_to_current()
            return

        # 入力された時間に最も近いデータ点のインデックスを探す
        time_diffs = [abs(ts - target_time) for ts in timestamps]
        closest_index = time_diffs.index(min(time_diffs))

        # スライダーを更新し、全体の再描画をトリガーする
        self.app.slider.set(closest_index)
        self._on_slider_change(None)

    def _update_time_inputs_to_current(self):
        """エラー時などに、時間表示を現在のスライダー位置に同期させる"""
        if not self.model.full_history: return
        try:
            current_index = int(self.app.slider.get())
            current_time = self.model.full_history[current_index]['timestamp']
            total_time = self.model.full_history[-1]['timestamp']
            self.app.time_input_var.set(f"{current_time:.1f}")
            self.app.total_time_var.set(f"s / {total_time:.1f}s")
        except (IndexError, KeyError):
            pass

    def _run_batch_analysis(self):
        """
        「一括解析」ボタンが押された際の処理。
        リアルタイム解析を停止し、UIを準備してから、
        時間のかかる解析処理をバックグラウンドで開始。
        """
        # 1. 事前チェック：CSVデータが存在するかModelに確認
        if self.model.csv_replay_data is None or self.model.csv_replay_data.empty:
            self.app.ui_manager.show_warning("警告", "先にCSVファイルを読み込んでください。")
            return

        # 2. 状態管理：リアルタイム解析が実行中なら、まず停止する
        if self.current_mode_handler.is_running:
            self.stop_analysis()

        # 3. UI準備：UIの状態を「解析中」に設定する
        self.app.batch_button.config(state="disabled")
        self.app.progress_bar.pack(fill=tk.X, expand=True, before=self.app.slider)
        self.app.progress_var.set(0)

        # 4. 実処理の実行：重い計算処理を別スレッドで開始する
        print("INFO: 一括解析のバックグラウンド処理を開始します。")
        self.batch_analysis_complete = False
        
        analysis_thread = threading.Thread(
            target=self._perform_batch_analysis_thread,
            daemon=True
        )
        analysis_thread.start()

        self._check_batch_analysis_status()

    def _perform_batch_analysis_thread(self):
        """【バックグラウンドで実行】一括解析の重い計算処理。"""
        try:
            print("INFO: (別スレッド) 一括解析の計算処理を開始します。")
            all_data_history = []
            
            for timestamp, row in self.model.csv_replay_data.iterrows():
                packet = {'timestamp': timestamp}
                for id_name in self.model.active_ids:
                    id_data = {}
                    for var in ALL_VARIABLES:
                        col_name = f"{id_name}_{var}"
                        if col_name in row and not pd.isna(row[col_name]):
                            id_data[var] = row[col_name]
                    if id_data:
                        packet[id_name] = id_data
                all_data_history.append(packet)

            df_full_features = self.analysis_service.perform_batch_analysis(all_data_history)
            self.batch_result_df = df_full_features

        except Exception as e:
            print(f"ERROR: (別スレッド) 一括解析の計算中にエラーが発生しました: {e}")
            self.batch_result_df = e
        finally:
            self.batch_analysis_complete = True
            print("INFO: (別スレッド) 計算処理が完了しました。")

    def _get_next_data_packet(self):
        """CSVリプレイデータから次のデータパケットを取得し、インデックスを進める"""
        if self.model.csv_replay_data is None or self.csv_replay_index >= len(self.model.csv_replay_data):
            return None # データがないか、終端に達した

        current_row = self.model.csv_replay_data.iloc[self.csv_replay_index]
        new_data = {'timestamp': current_row.name}
        for id_name in self.model.active_ids:
            id_data = {}
            for var in ALL_VARIABLES:
                col_name = f"{id_name}_{var}"
                if col_name in current_row and not pd.isna(current_row[col_name]):
                    id_data[var] = current_row[col_name]
                else:
                    id_data[var] = 0
            new_data[id_name] = id_data
        
        self.csv_replay_index += 1
        return new_data

    def process_data_and_update_views(self, history_index=None):
        """【メインループ】データ処理とUI更新を統括する"""
        try:
            # リアルタイム再生モードの場合、新しいデータを取得して履歴に追加
            is_running_in_realtime = (history_index is None and self.current_mode_handler.is_running)

            if is_running_in_realtime:
                new_data = self.current_mode_handler.get_next_data_packet()
                if new_data:
                    self.model.full_history.append(new_data)
                else:
                    self.stop_analysis()
                    self.app.ui_manager.show_info("完了", "再生が完了しました。")
                    return

            if not self.model.full_history:
                return

            target_index = history_index if history_index is not None else len(self.model.full_history) - 1
            full_slice_data = self.model.full_history[:target_index + 1]
            sliding_slice_data = self.model.full_history[max(0, target_index - self.sliding_window + 1) : target_index + 1]

            self._process_and_store_features(full_slice=full_slice_data, sliding_slice=sliding_slice_data)
            if not self.is_display_paused:
                self.app.ui_manager.update_active_view(self.model)
                self.app.ui_manager.update_slider_and_time(self.model, target_index)

        except (queue.Empty, IndexError):
            pass

        if self.current_mode_handler.is_running and history_index is None:
            self.after_id = self.app.after(self.update_interval, self.process_data_and_update_views)

    def save_features_to_csv(self):
        """
        全区間の分析で得られた特徴量（傾き）をCSVファイルに保存する。
        """
        print("INFO: 特徴量のCSV保存処理を開始します。")
        
        # 1. Modelから保存対象のデータを取得
        df_to_save = self.model.last_slope_dfs.get('full')
        
        # 2. データが存在するかチェック
        if df_to_save is None or df_to_save.empty:
            self.app.ui_manager.show_warning("保存エラー", "保存できる特徴量のデータがありません。\n先に「一括解析」などを実行してください。")
            return
        # 3. 保存ダイアログを開き、ユーザーにファイル名と場所を尋ねる
        try:
            filepath = filedialog.asksaveasfilename(
                title="特徴量ファイルを保存",
                defaultextension=".csv",
                filetypes=[("CSVファイル", "*.csv"), ("すべてのファイル", "*.*")],
                initialfile="features.csv" # ファイル名の初期値
            )
            
            # 4. ファイルパスが指定された場合のみ保存を実行
            if filepath:
                df_to_save.to_csv(filepath, encoding='utf-8-sig')
                self.app.ui_manager.show_info("成功", f"特徴量ファイルが正常に保存されました。\n場所: {filepath}")
                print(f"INFO: 特徴量ファイルを保存しました: {filepath}")
            else:
                print("INFO: 特徴量の保存がキャンセルされました。")

        except Exception as e:
            print(f"ERROR: 特徴量の保存中にエラーが発生しました: {e}")
            self.app.ui_manager.show_error("保存エラー", f"ファイルの保存中にエラーが発生しました:\n{e}")

    def on_focus_id_change(self, event):
        """フォーカス対象IDがリストボックスで変更されたときの処理"""
        selected_indices = self.app.focus_id_listbox.curselection()
        
        # 表示テキストから実際のID名を抽出する
        raw_ids = [self.app.focus_id_listbox.get(i) for i in selected_indices]
        parsed_ids = []
        for text in raw_ids:
            try:
                # "1 (ID_0)" のような文字列から "ID_0" を取り出す
                parsed_ids.append(text.split('(')[1][:-1])
            except IndexError:
                print(f"WARN: ID名のパースに失敗しました: {text}")
        self.focused_ids = parsed_ids
        
        print(f"INFO: フォーカス対象を {self.focused_ids} に変更しました。")
        
        self._refresh_views()

    def focus_on_all_ids(self):
        """「全員を選択」ボタンが押されたときの処理"""
        self.focused_ids = [] # 空リスト = 全員
        self.app.ui_manager.clear_focus_listbox_selection()
        print("INFO: フォーカス対象を全員に変更しました。")
        
        self._set_all_spectrum_vars(True)
        
        self._refresh_views()
            
    def _set_all_spectrum_vars(self, state=True):
        """スペクトルビューの変数チェックボックスをすべてON/OFFする"""
        if "spectrum" in self.app.views:
            self.app.views["spectrum"].set_all_variable_checkboxes(state)

    def _trigger_view_update(self):
        """UIの表示オプション（時間範囲など）の変更時に再描画をトリガーする"""
        self._refresh_views()

    def _refresh_views(self):
        """現在のスライダー位置に基づいて全ビューを再描画する"""
        if self.model.full_history:
            current_index = int(self.app.slider.get())
            self.process_data_and_update_views(history_index=current_index)
        
    def _check_batch_analysis_status(self):
        """【UIスレッドで実行】バックグラウンド処理が完了したか定期的にチェックする。"""
        if self.batch_analysis_complete:
            self.app.progress_bar.pack_forget()
            self.app.batch_button.config(state="normal")

            if isinstance(self.batch_result_df, Exception):
                self.app.ui_manager.show_error("エラー", f"一括解析中にエラーが発生しました:\n{self.batch_result_df}")
                return
            
            if self.batch_result_df is None or self.batch_result_df.empty:
                self.app.ui_manager.show_warning("警告", "特徴量の計算結果が空でした。")
                return

            print("INFO: 計算完了を検知。UIを更新します。")
            df_full = self.batch_result_df
            
            duration = self.model.csv_replay_data.index.max() if self.model.csv_replay_data is not None else 0
            
            # UIManager経由で各Viewを更新
            self.app.ui_manager.views["clustering"].update_plot(df_full, pd.DataFrame(), duration, 0)
            self.app.ui_manager.views["radar"].update_plot()
            self.app.ui_manager.views["spectrum"].update_plot()
            self.app.ui_manager.views["kmeans"].update_plot(df_full, pd.DataFrame(), duration, 0)
            self.app.ui_manager.views["heatmap"].update_plot(df_full, pd.DataFrame(), duration, 0)

            if self.model.full_history:
                last_index = len(self.model.full_history) - 1
                self.app.slider.config(to=last_index)
                self.app.slider.set(last_index)
                last_timestamp = self.model.full_history[-1]['timestamp']
                self.app.elapsed_time_var.set(f"経過時間: {last_timestamp:.1f}s")
            self.app.update_idletasks()

            if messagebox.askyesno("完了", "一括解析が完了しました。\n結果をファイルに保存しますか？"):
                self.save_plots()
        else:
            self.after_id = self.app.after(100, self._check_batch_analysis_status)

    def _check_status_queue(self):
        """【追加】リアルタイム処理のステータスキューを定期的にチェックする"""
        try:
            while not self.status_queue.empty():
                msg = self.status_queue.get_nowait()
                
                if msg.status == Status.ERROR:
                    self.app.ui_manager.show_error("リアルタイムエラー", msg.message)
                    self.stop_analysis() # エラー発生時は解析を停止
                elif msg.status == Status.WARNING:
                    self.app.ui_manager.show_warning("警告", msg.message)
                elif msg.status == Status.INFO:
                    self.app.ui_manager.show_info("情報", msg.message)
                elif msg.status == Status.COMPLETED:
                    self.app.ui_manager.show_info("完了", msg.message)
                    self.stop_analysis() # 正常完了時も解析を停止

        except queue.Empty:
            pass
        finally:
            # is_running中のみ、次のチェックを予約
            if self.current_mode_handler.is_running:
                self.status_check_after_id = self.app.after(200, self._check_status_queue)

        self.config_manager.load_config() # ファイルから最新の設定を読み込む
        self.update_interval = self.config_manager.config.analysis_parameters.UPDATE_INTERVAL_MS
        self.sliding_window = self.config_manager.config.analysis_parameters.SLIDING_WINDOW_SECONDS
        
        print("INFO: 設定ダイアログが閉じられ、設定がリロードされました。")

    def open_settings_dialog(self):
        """設定ダイアログを開く"""
        # --- ここから修正 ---
        # controllerのインスタンス(self)を渡すように修正
        dialog = ConfigDialog(self.app, self.config_manager, self)
        # --- 修正ここまで ---
        self.app.wait_window(dialog)
        
        self.analysis_params = self.config_manager.config.analysis_parameters
        self.update_interval = self.analysis_params.UPDATE_INTERVAL_MS
        self.sliding_window = self.analysis_params.SLIDING_WINDOW_SECONDS
        
        if self.app.mode.get() == "realtime":
            self._on_mode_change()
            
        print("INFO: 設定ダイアログが閉じられ、設定がリロードされました。")

    def update_preview_source(self, new_source):
        """【修正】設定ダイアログからの通知でプレビューカメラを更新する"""
        if self.app.mode.get() != "realtime":
            return

        print(f"INFO: プレビューソースを {new_source} に変更します。")
        
        # 1. メモリ上の設定を即時更新
        self.config_manager.config.realtime_settings.video_source = new_source
        
        # 2. CaptureServiceを再起動してカメラの変更を適用
        self.current_mode_handler.on_mode_deselected()
        self.current_mode_handler.on_mode_selected()





