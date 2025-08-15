# ファイル名: app/ui_manager.py

import tkinter as tk
from core.constants import SLIDING_WINDOW_SECONDS

class UIManager:
    """
    UIの更新と管理を専門に担当するクラス。
    Controllerからの指示を受けて、各種UI部品の状態を変更する。
    """
    def __init__(self, app):
        self.app = app
        self.controller = app.controller

    def update_ui_by_state(self, state):
        """StateManagerの状態に基づいてUI要素（主にボタン）を更新する。"""
        is_running = state.get('is_running', False)
        is_paused = state.get('is_paused', False)
        mode = state.get('mode', 'csv')
        
        is_idle = not is_running and not is_paused
        can_start = is_idle and (mode == 'realtime' or (mode == 'csv' and self.controller.model.csv_replay_data is not None))
        
        self.app.start_button.config(state=tk.NORMAL if can_start else tk.DISABLED)
        self.app.stop_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.app.pause_button.config(state=tk.NORMAL if is_running else tk.DISABLED)
        self.app.pause_button.config(text="再開" if is_paused else "一時停止")
        self.app.reset_button.config(state=tk.NORMAL if is_idle else tk.DISABLED)
        self.app.load_csv_button.config(state=tk.NORMAL if is_idle else tk.DISABLED)
        
        for widget in self.app.mode_frame.winfo_children():
            if isinstance(widget, tk.Radiobutton):
                widget.config(state=tk.NORMAL if is_idle else tk.DISABLED)

    def update_all_views(self):
        """
        全てのグラフ（View）を最新のデータで更新する。
        これが最も重要な画面更新処理。
        """
        # 登録されている全てのView（グラフ）の更新メソッドを呼び出す
        for view in self.app.views.values():
            if hasattr(view, 'update_view') and callable(view.update_view):
                view.update_view()

    def update_playback_controls(self):
        """再生スライダーと時間表示ラベルを更新する。"""
        model = self.controller.model
        if model.is_empty():
            return

        total_duration = model.get_total_duration()
        current_time = model.get_current_time()

        # スライダーの最大値と現在値を設定
        if self.app.slider.cget('to') != total_duration:
            self.app.slider.config(to=total_duration)
        self.app.slider.set(current_time)

        # 時間表示ラベルを更新
        self.app.total_time_var.set(f"/ {total_duration:.1f} s")
        self.app.elapsed_time_var.set(f"経過時間: {current_time:.1f} s")

    def update_focus_id_list(self, ids):
        """フォーカス対象IDのリストボックスを更新する。"""
        self.app.focus_id_listbox.delete(0, tk.END)
        for person_id in ids:
            self.app.focus_id_listbox.insert(tk.END, person_id)

    def clear_all_graphs(self):
        """全てのグラフをクリアする"""
        for view in self.app.views.values():
            if hasattr(view, 'clear_plot') and callable(view.clear_plot):
                view.clear_plot()