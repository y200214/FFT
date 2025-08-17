# ファイル名: views/ui_manager.py
import tkinter as tk
import pandas as pd
from tkinter import messagebox

class UIManager:
    def __init__(self, app_instance):
        """
        UIの更新と管理を担当するクラス。

        Args:
            app_instance (AppMainWindow): メインアプリケーションのインスタンス
        """
        self.app = app_instance
        self.controller = app_instance.controller
        self.views = app_instance.views # 各グラフViewへの参照を保持
        self.analysis_params = self.controller.config_manager.config.analysis_parameters
        self.sliding_window = self.analysis_params.SLIDING_WINDOW_SECONDS


    def show_info(self, title, message):
        """情報メッセージボックスを表示する"""
        messagebox.showinfo(title, message)

    def show_warning(self, title, message):
        """警告メッセージボックスを表示する"""
        messagebox.showwarning(title, message)

    def show_error(self, title, message):
        """エラーメッセージボックスを表示する"""
        messagebox.showerror(title, message)

    def update_focus_listbox(self, ids):
        """フォーカスIDリストボックスを更新する"""
        self.app.focus_id_listbox.delete(0, tk.END)
        for i, id_name in enumerate(ids):
            display_text = f"{i + 1} ({id_name})"
            self.app.focus_id_listbox.insert(tk.END, display_text)
        # リスト更新後、全選択状態にしておく
        self.app.focus_id_listbox.selection_set(0, tk.END)

    def ask_yes_no(self, title, message):
        """確認(Yes/No)メッセージボックスを表示し、結果を返す"""
        return messagebox.askyesno(title, message)

    def update_active_view(self, model_data):
        """
        現在アクティブなタブのビューを、最新のデータで更新する。
        """
        # リアルタイムモードの場合、常に映像を更新する
        if self.controller.current_mode_handler.__class__.__name__ == 'RealtimeHandler':
            latest_frame = self.controller.current_mode_handler.get_latest_frame()
            if latest_frame is not None:
                self.views["video"].update_frame(latest_frame)
                
        if not model_data.full_history:
            return

        # アクティブなタブのウィジェットを取得する
        active_view_key = None
        try:
            selected_tab_id = self.app.notebook.select()
            if selected_tab_id:
                active_widget = self.app.notebook.nametowidget(selected_tab_id)
                # ウィジェットオブジェクトを直接比較して、どのビューがアクティブかを探す
                for key, view_widget in self.views.items():
                    if view_widget == active_widget:
                        active_view_key = key
                        break
        except tk.TclError:
            return # ウィンドウ終了時などのエラーは無視

        # アクティブなビューが見つからなければ、何もせず終了
        if not active_view_key:
            return
            
        # 2. フィルタリングされたデータを準備
        df_full_filtered, df_sliding_filtered, ps_filtered = self._get_filtered_data(model_data)

        # 3. 期間（秒数）を計算
        current_timestamp = model_data.full_history[-1].get('timestamp', 0)
        full_duration = current_timestamp
        sliding_duration = self.sliding_window

        # 4. アクティブなViewに応じて、適切なデータを渡して更新
        if 'clustering' in active_view_key.lower():
            self.views["clustering"].update_plot(df_full_filtered, df_sliding_filtered, full_duration, sliding_duration)
        
        elif 'spectrum' in active_view_key.lower():
            self.views["spectrum"].update_plot(ps_filtered)

        elif 'radar' in active_view_key.lower():
            radar_dfs = {'sliding': df_sliding_filtered, 'full': df_full_filtered}
            self.views["radar"].update_plot(radar_dfs)

        elif 'kmeans' in active_view_key.lower():
            self.views["kmeans"].update_plot(df_full_filtered, df_sliding_filtered, full_duration, sliding_duration)

        elif 'heatmap' in active_view_key.lower():
            self.views["heatmap"].update_plot(df_full_filtered, df_sliding_filtered, full_duration, sliding_duration)

    def _get_filtered_data(self, model_data):
        """
        Modelのデータから、現在フォーカスされているIDでフィルタリングしたデータを取得する。
        """
        df_full = model_data.last_slope_dfs.get('full', pd.DataFrame())
        df_sliding = model_data.last_slope_dfs.get('sliding', pd.DataFrame())
        ps_data = model_data.last_power_spectrums

        focused_ids = self.controller.focused_ids
        if focused_ids:
            df_full_filtered = df_full[df_full.index.isin(focused_ids)]
            df_sliding_filtered = df_sliding[df_sliding.index.isin(focused_ids)]
            
            ps_sliding_filtered = {id_name: data for id_name, data in ps_data.get('sliding', {}).items() if id_name in focused_ids}
            ps_full_filtered = {id_name: data for id_name, data in ps_data.get('full', {}).items() if id_name in focused_ids}
            ps_filtered = {'sliding': ps_sliding_filtered, 'full': ps_full_filtered}
        else:
            df_full_filtered, df_sliding_filtered = df_full, df_sliding
            ps_filtered = ps_data

        return df_full_filtered, df_sliding_filtered, ps_filtered

    def update_slider_and_time(self, model_data, history_index):
        """スライダーと時間表示を更新する"""
        if self.controller.is_realtime_mode:
            current_max_index = len(model_data.full_history) - 1
            if current_max_index > 0:
                self.app.slider.config(to=current_max_index)
                self.app.slider.set(current_max_index)
        
        try:
            playback_time = model_data.full_history[history_index]['timestamp']
            self.app.elapsed_time_var.set(f"経過時間: {playback_time:.1f}s")

            # 再生時間の手入力ボックスも更新
            if not self.controller.is_realtime_mode:
                total_time = model_data.full_history[-1]['timestamp']
                self.app.time_input_var.set(f"{playback_time:.1f}")
                self.app.total_time_var.set(f"s / {total_time:.1f}s")
        except (IndexError, KeyError):
            pass

    def update_control_buttons_state(self):
        """
        Controllerの状態に基づいて、再生コントロールボタンの有効/無効を切り替える。
        """
        handler = self.controller.current_mode_handler
        is_running = handler.is_running
        is_paused = handler.is_paused

        if not is_running:
            # 停止中
            self.app.start_button.config(state="normal")
            self.app.stop_button.config(state="disabled")
            self.app.pause_button.config(state="disabled", text="一時停止")
        else:
            # 実行中
            self.app.start_button.config(state="disabled")
            self.app.stop_button.config(state="normal")
            self.app.pause_button.config(state="normal")
            if is_paused:
                self.app.pause_button.config(text="再開")
            else:
                self.app.pause_button.config(text="一時停止")

    def clear_all_views(self):
        """全てのグラフを空の状態で再描画する"""
        empty_df = pd.DataFrame()
        empty_ps = {}
        
        self.views["clustering"].update_plot(empty_df, empty_df, 0, 0)
        self.views["kmeans"].update_plot(empty_df, empty_df, 0, 0)
        self.views["heatmap"].update_plot(empty_df, empty_df, 0, 0)
        self.views["radar"].update_plot({'sliding': empty_df, 'full': empty_df})
        self.views["spectrum"].update_plot(empty_ps)

    def update_focus_listbox(self, ids):
        """フォーカスIDリストボックスを更新する"""
        self.app.focus_id_listbox.delete(0, tk.END)
        for i, id_name in enumerate(ids):
            display_text = f"{i + 1} ({id_name})"
            self.app.focus_id_listbox.insert(tk.END, display_text)
        # リスト更新後、全選択状態にしておく
        self.app.focus_id_listbox.selection_set(0, tk.END)

    def clear_focus_listbox_selection(self):
        """フォーカスIDリストボックスの選択をすべて解除する"""
        self.app.focus_id_listbox.selection_clear(0, tk.END)

    def set_rt_button_state(self, state):
        """リアルタイム復帰ボタンの状態を設定する"""
        self.app.rt_button.config(state=state)

    def set_pause_button_state(self, text, command):
        """一時停止ボタンのテキストとコマンドを更新する"""
        self.app.pause_button.config(text=text, command=command)

    def clear_time_inputs(self):
        """時間入力ボックスをクリアする"""
        self.app.time_input_var.set("")
        self.app.total_time_var.set("")

    def reset_ui_state(self):
        """UIの状態を初期値にリセットする"""
        self.app.slider.set(0)
        self.app.slider.config(to=100)
        self.app.progress_var.set(0)
        self.app.elapsed_time_var.set("経過時間: 0.0s")
        self.app.time_input_var.set("")
        self.app.total_time_var.set("")
        self.app.focus_id_listbox.delete(0, tk.END)
        self.app.batch_button.config(state="disabled")
        self.app.rt_button.config(state="disabled")