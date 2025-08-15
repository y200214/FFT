# ファイル名: app/ui_manager.py (修正後)

import tkinter as tk
import pandas as pd
from core.constants import SLIDING_WINDOW_SECONDS
import logging

from app.views.clustering_view import ClusteringView
from app.views.heatmap_view import HeatmapView
from app.views.kmeans_view import KmeansView
from app.views.radar_view import RadarView
from app.views.spectrum_view import SpectrumView


logger = logging.getLogger(__name__)

class UIManager:
    def __init__(self, app):
        self.app = app
        self.controller = app.controller

    def update_active_view(self):
        """
        現在表示されているタブのビューのみを、最新のデータで更新する。
        """
        model = self.controller.model
        if model.is_empty():
            return

        logger.debug("アクティブビューの更新を開始します。")

        # 1. アクティブなタブの情報を取得
        try:
            selected_tab_id = self.app.notebook.select()
            active_widget = self.app.nametowidget(selected_tab_id)
            active_view_key = next((key for key, view in self.app.views.items() if view == active_widget), None)
        except (tk.TclError, StopIteration):
            logger.warning("アクティブなビューの取得に失敗しました。")
            return

        if not active_view_key:
            return

        # 2. フォーカスIDに基づいてデータをフィルタリング
        filtered_slopes, filtered_spectrums = self._get_filtered_data(model)

        # 3. 描画に必要な期間（秒数）を計算
        full_duration = model.full_history[-1]['timestamp']
        target_index = len(model.full_history) - 1
        start_index = max(0, target_index - SLIDING_WINDOW_SECONDS + 1)
        sliding_duration = full_duration - model.full_history[start_index]['timestamp']

        # 4. アクティブなビューのupdate_plotメソッドを、適切なデータで呼び出す
        try:
            view_to_update = self.app.views[active_view_key]
            df_full = filtered_slopes.get('full')
            df_sliding = filtered_slopes.get('sliding')

            if isinstance(view_to_update, (ClusteringView, KmeansView, HeatmapView)):
                view_to_update.update_plot(df_full, df_sliding, full_duration, sliding_duration)
            elif isinstance(view_to_update, RadarView):
                view_to_update.update_plot(filtered_slopes)
            elif isinstance(view_to_update, SpectrumView):
                view_to_update.update_plot(filtered_spectrums)
            
            logger.debug(f"アクティブビュー '{active_view_key}' の更新が完了しました。")
        except Exception as e:
            logger.error(f"'{active_view_key}'の更新中にエラーが発生しました: {e}", exc_info=True)

    def _get_filtered_data(self, model):
        """Modelのデータから、フォーカス対象IDのデータのみを抽出する"""
        focused_ids = self.controller.focused_ids
        if not focused_ids:
            return model.last_slope_dfs, model.last_power_spectrums

        filtered_slopes = {}
        for key, df in model.last_slope_dfs.items():
            if df is not None and not df.empty:
                filtered_slopes[key] = df[df.index.isin(focused_ids)]
            else:
                filtered_slopes[key] = pd.DataFrame()

        filtered_spectrums = {}
        for key, ps_data in model.last_power_spectrums.items():
            filtered_spectrums[key] = {id_name: data for id_name, data in ps_data.items() if id_name in focused_ids}
            
        return filtered_slopes, filtered_spectrums

    def update_playback_controls(self, current_index=None):
        """再生スライダーと時間表示ラベルを更新する。"""
        model = self.controller.model
        mode = self.controller.state_manager.get_state('mode')
        
        total_steps = 100 # デフォルト値
        current_step = 0
        total_duration_sec = 0.0
        current_time_sec = 0.0

        if mode == 'csv' and model.csv_replay_data is not None:
            df = model.csv_replay_data
            total_steps = len(df) - 1
            # ▼▼▼ current_index を正しく参照するように修正 ▼▼▼
            current_step = current_index if current_index is not None else self.controller.replay_idx
            
            if total_steps > 0:
                total_duration_sec = df.index.max()
            if 0 <= current_step < len(df):
                current_time_sec = df.index[current_step]
            # ▼▼▼ CSV読み込み直後の初回描画ではスライダーを0に設定 ▼▼▼
            else:
                current_step = 0
                current_time_sec = 0.0

        self.app.slider.config(to=total_steps if total_steps > 0 else 100)
        self.app.slider.set(current_step)
        self.app.total_time_var.set(f"/ {total_duration_sec:.1f} s")
        self.app.elapsed_time_var.set(f"経過時間: {current_time_sec:.1f} s")

    def update_focus_id_list(self, ids):
        logger.info(f"フォーカスIDリストを更新します。IDs: {ids}")
        current_selection = self.app.focus_id_listbox.curselection()
        self.app.focus_id_listbox.delete(0, tk.END)
        for i, person_id in enumerate(ids):
            self.app.focus_id_listbox.insert(tk.END, f"{i+1} ({person_id})")
        for i in current_selection:
            if i < self.app.focus_id_listbox.size():
                self.app.focus_id_listbox.selection_set(i)

    def clear_all_graphs(self):
        logger.info("全てのグラフをクリアします。")
        empty_df = pd.DataFrame()
        empty_dfs = {'full': empty_df, 'sliding': empty_df}
        empty_ps = {'full': {}, 'sliding': {}}
        
        for view in self.app.views.values():
            if hasattr(view, 'update_plot'):
                if isinstance(view, (ClusteringView, KmeansView, HeatmapView)):
                    view.update_plot(empty_df, empty_df, 0, 0)
                elif isinstance(view, RadarView):
                    view.update_plot(empty_dfs)
                elif isinstance(view, SpectrumView):
                    view.update_plot(empty_ps)

    def update_ui_by_state(self, state):
        """StateManagerの状態に基づいてUI要素（主にボタン）を更新する。"""
        logger.debug(f"UIの状態更新を開始します。現在の状態: {state}")
        is_running = state.get('is_running', False)
        is_paused = state.get('is_paused', False)
        mode = state.get('mode', 'csv')
        
        is_idle = not is_running and not is_paused
        can_start = is_idle and (mode == 'realtime' or (mode == 'csv' and self.controller.model.csv_replay_data is not None))
        
        # ▼▼▼ 「一括解析」ボタンの状態管理をここに集約 ▼▼▼
        can_batch_analysis = is_idle and (mode == 'csv' and self.controller.model.csv_replay_data is not None)
        self.app.batch_button.config(state=tk.NORMAL if can_batch_analysis else tk.DISABLED)
        
        self.app.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)
        
        self.app.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)
        self.app.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)
        self.app.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.app.pause_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.app.pause_button.config(text="再開" if is_paused else "一時停止")
        self.app.reset_button.config(state=tk.NORMAL if is_idle else tk.DISABLED)
        self.app.load_csv_button.config(state=tk.NORMAL if is_idle else tk.DISABLED)
        
        for widget in self.app.mode_frame.winfo_children():
            if isinstance(widget, tk.Radiobutton):
                widget.config(state=tk.NORMAL if is_idle else tk.DISABLED)














