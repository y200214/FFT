# ファイル名: controller.py
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import multiprocessing # service_managerにQueueを渡すために必要
import queue
import time
from collections import deque
import pandas as pd

# 外部ファイルをインポート
from core.constants import ALL_VARIABLES, SLIDING_WINDOW_SECONDS, UPDATE_INTERVAL_MS
from core.model import AnalysisModel
from core.data_processor import DataProcessor
from core.config_manager import ConfigManager
from core.save_manager import SaveManager
from services.capture_service import capture_process_entrypoint
from .views.progress_dialog import ProgressDialog
from .views.config_dialog import ConfigDialog
from .state_manager import StateManager
from .service_manager import RealtimeServiceManager

class AppController:
    def __init__(self, app, log_queue):
        self.app = app
        self.log_queue = log_queue
        self.model = AnalysisModel()
        self.data_processor = DataProcessor()
        self.config_manager = ConfigManager()
        # Controller自身が状態を持つのではなく、StateManagerに委任する
        self.state_manager = StateManager()
        
        # リアルタイム処理用のデータキューはServiceManagerに渡すために必要
        self.realtime_data_queue = multiprocessing.Queue()
        # リアルタイム処理の管理をServiceManagerに委任する
        self.service_manager = RealtimeServiceManager(self.realtime_data_queue, self.log_queue)
        
        self.save_manager = SaveManager(self)
        
        # 定期的な処理のセットアップ
        self.app.after(100, self.check_realtime_data_queue)

    def _on_mode_change(self):
        """モードが変更されたことをUIManagerに通知する"""
        # 実際のUI更新はUIManagerが担当
        self.app.ui_manager.update_widget_states(self.state)

    def load_csvs(self):
            """CSVファイルを読み込み、Modelに渡す"""
            filepaths = filedialog.askopenfilenames(
                title="再生するCSVファイルを選択（複数選択可）", 
                filetypes=[("CSV files", "*.csv")]
            )
            if not filepaths: return
            
            success, ids = self.model.load_csv_data(filepaths)
            
            if not success:
                self.app.show_error("エラー", "ファイルの読み込みまたはIDの推定に失敗しました。")
            else:

                
                # フォーカス用リストボックスの中身を更新
                self.app.focus_id_listbox.delete(0, tk.END)
                # 表示形式を「番号 (ID名)」に変更
                for i, id_name in enumerate(ids):
                    display_text = f"{i + 1} ({id_name})"
                    self.app.focus_id_listbox.insert(tk.END, display_text)
                
                self.focus_on_all_ids()
            self._on_mode_change()

    def start_processing(self):
        """CSVまたはリアルタイム処理を開始する"""
        mode = self.state_manager.get_state('mode')
        if mode == 'csv':
            self._start_csv_replay()
        else: # realtime
            self._start_realtime_processing()

        # 状態を「実行中」に更新
        self.state_manager.set_state({"is_running": True, "is_paused": False})

    def stop_processing(self):
        """全ての処理を停止する"""
        if self.service_manager.is_running():
            self.service_manager.stop()
            
        # CSVリプレイのタイマーも止める（必要に応じて）
        if hasattr(self, '_csv_replay_timer') and self._csv_replay_timer:
            self.app.after_cancel(self._csv_replay_timer)
            self._csv_replay_timer = None # キャンセル後はNoneに戻す

        self.state_manager.set_state({"is_running": False, "is_paused": False})

    def reset_application(self):
        """アプリケーションの状態をリセットする"""
        self.stop_processing()
        self.model.reset() # Modelをリセット
        self.app.clear_all_graphs() # Viewをリセット
        self.state_manager.set_state({ # Stateをリセット
            "is_running": False, 
            "is_paused": False, 
            "selected_focus_id": "全員"
        })
        self.app.update_focus_id_list(self.model.active_ids)
        print("INFO: アプリケーションをリセットしました。")

    def _start_realtime_processing(self):
        """【内部処理】リアルタイムサービスを開始する (修正)"""
        if not self.service_manager.is_running():
            self.service_manager.start()

    def start_analysis(self):
        """解析を開始する"""
        if self.state not in ["IDLE", "PAUSED"]:
            return

        mode = self.app.mode.get()
        
        if mode == 'csv':
            if self.model.csv_replay_data is None:
                self.app.show_info("情報", "再生するCSVファイルが読み込まれていません。")
                return
            self.state = 'CSV_REPLAYING'
            print(f"CSVリプレイを開始します。対象ID: {self.model.active_ids}")

        elif mode == 'realtime':
            self.state = 'REALTIME_RUNNING'
            # (必要に応じて)リアルタイム解析用のIDを準備
            # self.model.active_ids = ["ID_Realtime_1"] 
            self.start_capture_service() # メソッドを呼び出す
            self.logger.info("リアルタイム解析を開始します。")

        self.is_running = True
        self.is_paused = False
        self.model.full_history = []
        self.csv_replay_index = 0
        
        self.app.ui_manager.update_widget_states(self.state)
        self.start_update_loop()

    def stop_analysis(self):
        """解析を停止する"""
        if self.state == "IDLE": return

        if self.state == 'REALTIME_RUNNING':
            self.stop_capture_service() # メソッドを呼び出す

        self.state = "IDLE"
        self.is_running = False
        self.is_paused = False
        self.stop_update_loop()
        
        self.app.ui_manager.update_widget_states(self.state)
        print("解析を停止しました。")

    def start_capture_service(self):
        """映像処理を別プロセスで開始する"""
        if self._capture_process and self._capture_process.is_alive():
            self.logger.info("CaptureServiceは既に実行中です。")
            return

        self.capture_running.set()
        self._capture_process = multiprocessing.Process(
            target=capture_process_entrypoint,
            args=(self.realtime_data_queue, self.log_queue, self.capture_running),
            daemon=True,
            name="CaptureProcess" # プロセスに名前を付ける
        )
        self._capture_process.start()
        self.logger.info("CaptureServiceを開始しました。")

    def stop_capture_service(self):
        """映像処理を停止する"""
        if self.capture_running:
            self.logger.info("CaptureServiceの停止を要求します。")
            self.capture_running.clear()
        if self._capture_process:
            self._capture_process.join(timeout=3)
            if self._capture_process.is_alive():
                self.logger.warning("CaptureServiceが時間内に終了しなかったため、強制終了します。")
                self._capture_process.terminate()
            self.logger.info("CaptureServiceを停止しました。")
        self._capture_process = None

    def toggle_pause(self):
        """処理の一時停止/再開を切り替える"""
        is_paused_current = self.state_manager.get_state('is_paused')
        self.state_manager.set_state({"is_paused": not is_paused_current})

    def start_update_loop(self):
        """定期的なデータ処理とUI更新ループを開始する"""
        self.stop_update_loop() # 既存のループがあれば停止
        self.process_data_and_update_views()

    def stop_update_loop(self):
        """更新ループを停止する"""
        if self.after_id:
            self.app.after_cancel(self.after_id)
            self.after_id = None
    
    def _process_and_store_features(self, full_slice, sliding_slice=None):
        """
        DataProcessorを使い、特徴量を計算して結果をModelに格納する。
        """
        # --- 全区間データの計算 ---
        # history形式からDataFrameへの変換をDataProcessorに依頼
        df_full = self.data_processor.convert_history_to_df(full_slice, self.model.active_ids)
        # DataFrameから特徴量とスペクトルを計算
        df_full_features, ps_full = self.data_processor.get_features_from_df(df_full, self.model.active_ids)

        # --- スライディング窓データの計算 ---
        df_sliding_features, ps_sliding = pd.DataFrame(), {}
        if sliding_slice:
            df_sliding = self.data_processor.convert_history_to_df(sliding_slice, self.model.active_ids)
            df_sliding_features, ps_sliding = self.data_processor.get_features_from_df(df_sliding, self.model.active_ids)
            
        # --- 計算結果をModelに保存 ---
        self.model.last_slope_dfs = {'sliding': df_sliding_features, 'full': df_full_features}
        self.model.last_power_spectrums = {'sliding': ps_sliding, 'full': ps_full}
        
        # 計算結果を返す (一括解析などで利用)
        return df_full_features, ps_full

    def save_plots(self):
        """
        SaveManagerにグラフ保存処理を依頼する
        """
        self.save_manager.save_all_plots()

    def _on_slider_change(self, event):
        """スライダーが操作されたときの処理"""
        self.stop_update_loop()
        self.is_realtime_mode = False 
        self.is_display_paused = False # スライダー操作時は表示の一時停止を解除

        self.app.rt_button['state'] = 'normal'
        timestamp_index = int(self.app.slider.get())

        # データ処理とUI更新をトリガー
        self.process_data_and_update_views(history_index=timestamp_index)

    def _return_to_realtime(self):
        """リアルタイム表示に復帰する"""
        self.is_display_paused = False
        self.app.pause_button.config(text="一時停止", command=self.toggle_pause)
        self.is_realtime_mode = True
        self.app.rt_button['state'] = 'disabled'
        
        # UI変数をクリアする
        self.app.time_input_var.set("")
        self.app.total_time_var.set("")
        
        # 再生を再開
        self.start_update_loop()

    def reset_all_data(self):
        """
        全てのデータとUIの状態を初期化する
        """
        if self.is_running:
            self.stop_analysis()

        if not messagebox.askyesno("確認", "本当にすべてのデータをリセットしますか？\nこの操作は元に戻せません。"):
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
        self.is_paused = False
        self.csv_replay_index = 0
        self.focused_ids = []
        self.batch_result_df = None

        # UIの状態をリセット (UIManagerに任せる部分以外)
        self.app.slider.set(0)
        self.app.slider.config(to=100)
        self.app.progress_var.set(0)
        self.app.elapsed_time_var.set("経過時間: 0.0s")
        self.app.time_input_var.set("")
        self.app.total_time_var.set("")
        self.app.focus_id_listbox.delete(0, tk.END)
        self.app.batch_button.config(state="disabled")
        self.app.rt_button.config(state="disabled")

        # 全てのグラフをクリアする処理をUIManagerに任せる
        self.app.clear_all_graphs() 
        
        self.app.show_info("完了", "すべてのデータをリセットしました。")

    def on_time_input_enter(self, event=None):
        """ユーザーが再生時間ボックスでEnterを押したときの処理"""
        if not self.model.full_history: return

        try:
            target_time = float(self.app.time_input_var.get())
        except (ValueError, TypeError):
            self.app.show_warning("入力エラー", "数値を入力してください。")
            self._update_time_inputs_to_current() # 入力値を現在のスライダー位置に戻す
            return

        timestamps = [dp['timestamp'] for dp in self.model.full_history]
        
        # 入力値が有効範囲内かチェック
        if not (timestamps[0] <= target_time <= timestamps[-1]):
            self.app.show_warning("入力エラー", f"時間は {timestamps[0]:.1f} から {timestamps[-1]:.1f} の間で入力してください。")
            self._update_time_inputs_to_current()
            return

        # 入力された時間に最も近いデータ点のインデックスを探す
        time_diffs = [abs(ts - target_time) for ts in timestamps]
        closest_index = time_diffs.index(min(time_diffs))

        # スライダーを更新し、全体の再描画をトリガーする
        self.app.slider.set(closest_index)
        self._on_slider_change(event=None)

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
            self.app.show_warning("警告", "先にCSVファイルを読み込んでください。")
            return

        # 2. 状態管理：リアルタイム解析が実行中なら、まず停止する
        if self.is_running:
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

            # Modelに計算を依頼する代わりに、DataProcessorを使用する
            df_full = self.data_processor.convert_history_to_df(all_data_history, self.model.active_ids)
            df_full_features, ps_full = self.data_processor.get_features_from_df(df_full, self.model.active_ids)
            
            # Modelに再生用データを格納
            self.model.full_history = all_data_history
            
            # クラスタリング表示用の一時変数に結果を保存
            self.batch_result_df = df_full_features
            
            # 保存機能で使う、Modelの正式な変数にも結果を格納
            self.model.last_slope_dfs = {'full': df_full_features, 'sliding': pd.DataFrame()}
            self.model.last_power_spectrums = {'full': ps_full, 'sliding': {}}

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

    def _get_data_for_current_mode(self):
        """
        現在のモードに応じて、適切なデータソースから新しいデータを取得する。
        """
        mode = self.app.mode.get()
        if mode == 'csv':
            # 既存のCSVリプレイロジック
            return self._get_next_data_packet()
        elif mode == 'realtime':
            # 【重要】リアルタイムキューからデータを取得する新しいロジック
            try:
                # キューにデータがあれば即座に取得し、なければNoneを返す
                return self.realtime_data_queue.get_nowait()
            except queue.Empty:
                return None
        return None

    def process_data_and_update_views(self, history_index=None):
        """【メインループ】データ処理とUI更新を統括する (修正後)"""
        try:
            # リアルタイム再生モードの場合、新しいデータを取得して履歴に追加
            if self.is_realtime_mode and self.is_running:
                new_data = self._get_data_for_current_mode()
                
                if new_data:
                    if "error" in new_data:
                        self.stop_analysis()
                        self.app.show_error("リアルタイム解析エラー", new_data["error"])
                        return
                     
                    self.model.full_history.append(new_data)
                    # リアルタイムの場合、アクティブIDリストも動的に更新する必要がある
                    current_ids = {k for k in new_data if k.startswith('ID_')}
                    new_ids = [cid for cid in current_ids if cid not in self.model.active_ids]
                    if new_ids:
                        self.model.active_ids.extend(new_ids)
                        self.model.active_ids.sort()
                        # ここでUIのIDリストを更新する処理を呼ぶ
                        self.app.ui_manager.update_focus_id_list(self.model.active_ids)
                        
                elif self.app.mode.get() == 'csv': # CSVリプレイが終端に達した場合
                    self.stop_analysis()
                    self.app.show_info("完了", "CSVファイルの再生が完了しました。")
                    return

            if not self.model.full_history:
                # 次のループを予約して待機
                if self.is_running and history_index is None:
                    self.after_id = self.app.after(100, self.process_data_and_update_views)
                return

            # 表示対象のインデックスとデータを決定
            target_index = history_index if history_index is not None else len(self.model.full_history) - 1
            full_slice_data = self.model.full_history[:target_index + 1]
            sliding_slice_data = self.model.full_history[max(0, target_index - SLIDING_WINDOW_SECONDS + 1) : target_index + 1]

            # 特徴量計算とUI更新
            self._process_and_store_features(full_slice=full_slice_data, sliding_slice=sliding_slice_data)
            if not self.is_display_paused:
                self.app.ui_manager.update_active_view(self.model)
                self.app.ui_manager.update_slider_and_time(self.model, target_index)

        except Exception as e:
            self.logger.error(f"UI更新ループでエラーが発生しました: {e}", exc_info=True)
            pass

        # 次のループを予約
        if self.is_running and history_index is None:
            # リアルタイムの場合は少し短い間隔で更新を試みる
            interval = 100 if self.app.mode.get() == 'realtime' else UPDATE_INTERVAL_MS
            self.after_id = self.app.after(interval, self.process_data_and_update_views)

    def save_features_to_csv(self):
        """
        全区間の分析で得られた特徴量（傾き）をCSVファイルに保存する。
        """
        print("INFO: 特徴量のCSV保存処理を開始します。")
        
        # 1. Modelから保存対象のデータを取得
        df_to_save = self.model.last_slope_dfs.get('full')
        
        # 2. データが存在するかチェック
        if df_to_save is None or df_to_save.empty:
            self.app.show_warning("保存エラー", "保存できる特徴量のデータがありません。\n先に「一括解析」などを実行してください。")
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
                self.app.show_info("成功", f"特徴量ファイルが正常に保存されました。\n場所: {filepath}")
                print(f"INFO: 特徴量ファイルを保存しました: {filepath}")
            else:
                print("INFO: 特徴量の保存がキャンセルされました。")

        except Exception as e:
            print(f"ERROR: 特徴量の保存中にエラーが発生しました: {e}")
            self.app.show_error("保存エラー", f"ファイルの保存中にエラーが発生しました:\n{e}")

    def on_focus_id_change(self, event=None):
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
        

        if self.model.full_history:
            current_index = int(self.app.slider.get())
            self.process_data_and_update_views(history_index=current_index)

    def focus_on_all_ids(self):
        """「全員を選択」ボタンが押されたときの処理"""
        self.focused_ids = [] # 空リスト = 全員
        self.app.focus_id_listbox.selection_clear(0, tk.END) # リストボックスの選択を解除
        print("INFO: フォーカス対象を全員に変更しました。")
        
        self._set_all_spectrum_vars(True)
        
        if self.model.full_history:
            current_index = int(self.app.slider.get())
            self.process_data_and_update_views(history_index=current_index)
            
    def _set_all_spectrum_vars(self, state=True):
        """スペクトルビューの変数チェックボックスをすべてON/OFFする"""
        if "spectrum" in self.app.views:
            self.app.views["spectrum"].set_all_variable_checkboxes(state)

    def _trigger_view_update(self):
        """UIの表示オプション（時間範囲など）の変更時に再描画をトリガーする"""
        if self.model.full_history:
            current_index = int(self.app.slider.get())
            self.process_data_and_update_views(history_index=current_index)

    def open_settings_dialog(self):
        """設定ダイアログを開く"""
        # ConfigDialogクラスのインスタンスを作成する
        # 親ウィンドウ(self.app)と、自身が持つconfig_managerを渡す
        dialog = ConfigDialog(self.app, self.config_manager)
        
        # ダイアログが閉じられるまで待機する
        self.app.wait_window(dialog)
        
        # ダイアログが閉じた後（保存された後）の処理をここに追加できる
        # (今回は特に不要だが、例えば「設定を適用するには再起動が必要です」などのメッセージ表示が可能)
        print("INFO: 設定ダイアログが閉じられました。")

    def _check_batch_analysis_status(self):
        """【UIスレッドで実行】バックグラウンド処理が完了したか定期的にチェックする。"""
        if self.batch_analysis_complete:
            self.app.progress_bar.pack_forget()
            self.app.batch_button.config(state="normal")

            if isinstance(self.batch_result_df, Exception):
                self.app.show_error("エラー", f"一括解析中にエラーが発生しました:\n{self.batch_result_df}")
                return
            
            if self.batch_result_df is None or self.batch_result_df.empty:
                self.app.show_warning("警告", "特徴量の計算結果が空でした。")
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

    def on_app_close(self):
        """アプリケーション終了時の処理"""
        if self.service_manager.is_running():
            self.service_manager.stop()

    def select_and_load_csvs(self):
        """
        ファイルダイアログを開き、選択されたCSVをModelに読み込ませる。
        """
        if self.state_manager.get_state('is_running'):
            self.app.show_error("エラー", "処理実行中はCSVを読み込めません。")
            return

        filepaths = filedialog.askopenfilenames(
            title="CSVファイルを選択",
            filetypes=[("CSVファイル", "*.csv")]
        )
        if not filepaths:
            return

        # Modelにデータのロードを依頼
        success, ids = self.model.load_csv_data(filepaths)
        if success:
            self.app.show_info("成功", f"{len(ids)}個のCSVファイルを読み込みました。")
            self.app.ui_manager.update_focus_id_list(ids)
            # 状態を更新してUI（開始ボタンなど）を有効化する
            self.state_manager.set_state({}) # 空の更新でリスナーをトリガー
        else:
            self.app.show_error("エラー", "有効なCSVデータの読み込みに失敗しました。")

    def set_mode(self, mode):
        """
        UIからのモード変更をStateManagerに通知する
        """
        self.state_manager.set_state({'mode': mode})

    def check_realtime_data_queue(self):
        """
        リアルタイム処理プロセスからのデータキューを定期的にチェックする。
        """
        try:
            # キューに溜まっているデータを全て取得する
            while True:
                data = self.realtime_data_queue.get_nowait()

                # エラー通知が来ていないかチェック
                if isinstance(data, dict) and "error" in data:
                    self.app.show_error("リアルタイム処理エラー", data["error"])
                    self.stop_processing() # エラー発生時は処理を停止
                    break

                # 受け取ったデータをモデルに追加
                self.model.add_history_entry(data)
                
                # スライダー追従モードならUIを更新
                if self.state_manager.get_state('is_realtime_sync'):
                    # 全ビューの更新と、再生コントロールの更新を行う
                    self.app.ui_manager.update_all_views()
                    self.app.ui_manager.update_playback_controls()

        except queue.Empty:
            pass
        finally:
            self.app.after(100, self.check_realtime_data_queue)

    def _start_csv_replay(self):
        """
        CSVデータのリプレイ（再生）を開始する。
        """
        if self.model.csv_replay_data is None:
            self.app.show_error("エラー", "リプレイするCSVデータがありません。")
            return
        
        # タイマー変数を初期化（安全のため）
        self._csv_replay_timer = None
        self.replay_idx = 0
        
        # 最初のフレーム更新を呼び出す
        self._update_replay_ui()

    def _update_replay_ui(self):
        """
        CSVリプレイのUIを1ステップ分更新し、次の更新を予約する。
        """
        if not self.state_manager.get_state('is_running') or self.state_manager.get_state('is_paused'):
            if not self.state_manager.get_state('is_running'):
                return # 停止していたら完全に終了
            self.app.after(100, self._update_replay_ui) # 一時停止なら再予約のみ
            return

        df = self.model.csv_replay_data
        if df is None or self.replay_idx >= len(df):
            self.stop_processing()
            self.app.show_info("完了", "CSVデータのリプレイが完了しました。")
            return

        current_data_row = df.iloc[[self.replay_idx]]
        
        self.model.add_csv_history_entry(current_data_row)
        
        # ★★★ 修正点 ★★★
        # 全ビューの更新と、再生コントロールの更新を行う
        self.app.ui_manager.update_all_views()
        self.app.ui_manager.update_playback_controls()

        self.replay_idx += 1
        
        # 次の更新を予約
        self._csv_replay_timer = self.app.after(100, self._update_replay_ui)


