# ファイル名: save_manager.py 

import tkinter as tk
from tkinter import filedialog
import threading
import os
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

from app.views.progress_dialog import ProgressDialog
from .constants import ALL_VARIABLES

class SaveManager:
    def __init__(self, controller):
        """
        ファイル保存に関する全ての処理を担当するクラス。
        """
        self.controller = controller
        self.app = controller.app
        self.model = controller.model

    def save_all_plots(self):
        """【司令塔】スライダー位置のデータのスナップショットを保存する"""
        if not self.model.full_history:
            self.app.show_error("保存エラー", "保存できるデータがありません。")
            return

        # 1. Modelにキャッシュされている最新の計算結果を取得する
        slope_dfs_to_save = self.model.last_slope_dfs
        power_spectrums_to_save = self.model.last_power_spectrums
        
        # 2. 計算結果が存在するかチェック
        if not slope_dfs_to_save or not power_spectrums_to_save or 'full' not in slope_dfs_to_save:
            self.app.show_error("保存エラー", "特徴量の計算結果が見つかりません。\nスライダーを動かすか解析を実行してください。")
            return
        
        # 3. 保存するタイムスタンプをスライダーの位置から取得
        save_index = int(self.app.slider.get())
        if save_index >= len(self.model.full_history):
            self.app.show_error("保存エラー", "無効なデータ点を指しています。")
            return
        save_timestamp = self.model.full_history[save_index]['timestamp']

        # 4. 保存先フォルダを選択
        base_path = filedialog.askdirectory(title="保存先の親フォルダを選択してください")
        if not base_path:
            print("INFO: グラフの保存がキャンセルされました。")
            return

        # 5. 保存処理を別スレッドで実行
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_folder = os.path.join(base_path, f"解析結果_{timestamp_str}")
        os.makedirs(output_folder, exist_ok=True)
        print(f"INFO: 全てのグラフを '{output_folder}' に保存します。")

        self.controller.is_saving_cancelled = False
        self.controller.save_plots_complete = False
        self.controller.save_plots_error = None
        self.controller.save_progress = 0
        num_ids = len(self.model.active_ids)
        num_spectrum_vars = len(ALL_VARIABLES)
        total_steps = 1 + 1 + 1 + (num_ids * num_spectrum_vars) + num_ids
        
        self.progress_dialog = ProgressDialog(self.app, title="グラフ保存中", cancel_callback=self._cancel_save)
        self.progress_dialog.progress_bar.config(maximum=total_steps)
        self.controller.save_total_steps = total_steps

        save_thread = threading.Thread(
            target=self._perform_save_thread,
            args=(output_folder, save_timestamp, slope_dfs_to_save, power_spectrums_to_save),
            daemon=True
        )
        save_thread.start()
        self._check_save_status()

    def _perform_save_thread(self, output_folder, timestamp, slope_dfs_to_save, power_spectrums_to_save):
        """【作業員】受け取ったスナップショットデータを元にファイル保存を実行する"""
        
        matplotlib.use('Agg') # バックエンドをGUI不要の'Agg'に切り替え
        import matplotlib.pyplot as plt # pyplotをこのスレッドで再インポート

        try:
            def progress_callback():
                self.controller.save_progress += 1

            if self.controller.is_saving_cancelled: return
            df_to_save = slope_dfs_to_save.get('full')
            if df_to_save is not None and not df_to_save.empty:
                filepath = os.path.join(output_folder, "features.csv")
                df_to_save.to_csv(filepath, encoding='utf-8-sig')
            progress_callback()

            if self.controller.is_saving_cancelled: return
            results_list = []
            spectrum_data = power_spectrums_to_save.get('full', {})
            for id_name, var_data in spectrum_data.items():
                for var_name, spec_tuple in var_data.items():
                    _freq, _amp, slope, intercept = spec_tuple
                    if slope is not None and intercept is not None:
                        results_list.append({'ID': id_name, 'Variable': var_name, 'Slope': slope, 'Intercept': intercept})
            if results_list:
                pd.DataFrame(results_list).to_csv(os.path.join(output_folder, "slopes_and_intercepts.csv"), index=False, encoding='utf-8-sig')
            progress_callback()

            # 各Viewの保存メソッドを呼び出す
            views = self.app.views
            if self.controller.is_saving_cancelled: return
            if "clustering" in views:
                views["clustering"].save_plot(output_folder, timestamp, slope_dfs_to_save.get('full'))

            if self.controller.is_saving_cancelled: return
            if "spectrum" in views:
                views["spectrum"].save_plot(output_folder, power_spectrums_to_save, progress_callback, timestamp, lambda: self.controller.is_saving_cancelled)
            
            if self.controller.is_saving_cancelled: return
            if "radar" in views:
                views["radar"].save_plot(output_folder, slope_dfs_to_save, progress_callback, timestamp, lambda: self.controller.is_saving_cancelled)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.controller.save_plots_error = e
        finally:
            self.controller.save_plots_complete = True
            matplotlib.use('TkAgg')            

    def _check_save_status(self):
        """【監視員】保存処理の進捗と完了/キャンセルを監視し、UIに反映する"""
        if self.controller.save_plots_complete or self.controller.is_saving_cancelled:
            if self.progress_dialog:
                self.progress_dialog.close()

            if self.controller.is_saving_cancelled:
                self.app.show_info("キャンセル", "保存処理がキャンセルされました。")
            elif self.controller.save_plots_error:
                self.app.show_error("エラー", f"グラフの保存中にエラーが発生しました:\n{self.controller.save_plots_error}")
            else:
                self.app.show_info("成功", "グラフが正常に保存されました。")
        else:
            progress_text = f"処理中... ({self.controller.save_progress} / {self.controller.save_total_steps})"
            if self.progress_dialog:
                self.progress_dialog.update_progress(self.controller.save_progress, progress_text)
            self.app.after(100, self._check_save_status)

    def _cancel_save(self):
        """保存処理のキャンセルを要求する (ProgressDialogから呼ばれる)"""
        self.controller.is_saving_cancelled = True
        if self.progress_dialog:
            self.progress_dialog.label.config(text="キャンセルしています...")
            self.progress_dialog.cancel_button.config(state="disabled")