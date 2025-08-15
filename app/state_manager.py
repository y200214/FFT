# ファイル名: state_manager.py (新規作成)

class StateManager:
    """
    アプリケーション全体の状態を一元管理するクラス。
    状態が変更された際に、登録されたリスナー（コールバック関数）を呼び出す機能を持つ。
    """
    def __init__(self):
        self._state = {
            "mode": "csv",          # 'csv' or 'realtime'
            "is_running": False,
            "is_paused": False,
            "is_realtime_sync": True, # リアルタイム表示に追従しているか
            "selected_focus_id": "全員",
            # 他のUIやアプリケーションの状態もここに追加できる
        }
        self._listeners = []

    def add_listener(self, listener):
        """状態変更を通知してほしい関数（リスナー）を登録する。"""
        self._listeners.append(listener)

    def get_state(self, key):
        """現在の状態を取得する。"""
        return self._state.get(key)

    def set_state(self, new_state):
        """状態を更新し、変更があった場合にリスナーに通知する。"""
        # 辞書をマージして状態を更新
        self._state.update(new_state)
        self._notify_listeners()

    def _notify_listeners(self):
        """登録された全てのリスナーに現在の状態を渡して呼び出す。"""
        for listener in self._listeners:
            listener(self._state.copy()) # 状態のコピーを渡す