# ファイル名: config_manager.py (新規作成)

import json
import os

class ConfigManager:
    def __init__(self, config_file='config.json'):
        """
        設定ファイルを管理するクラス。

        Args:
            config_file (str): 設定ファイル名。
        """
        self.config_file = config_file
        self.config = self.load_config()

    def get_default_config(self):
        """
        デフォルトの設定値を返す。
        """
        return {
            "fft_initial_view": {
                "variable_group": "all",  # "all", "emotion", "behavior"
                "show_fit_line": True
            }
            # 他の設定項目も将来ここに追加できる
        }

    def load_config(self):
        """
        設定ファイルを読み込む。ファイルが存在しない場合はデフォルト設定で作成する。
        """
        if not os.path.exists(self.config_file):
            print(f"INFO: 設定ファイル '{self.config_file}' が見つかりません。デフォルト設定で作成します。")
            default_config = self.get_default_config()
            self.save_config(default_config)
            return default_config
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"INFO: 設定ファイル '{self.config_file}' を読み込みました。")
                return config
        except (json.JSONDecodeError, IOError) as e:
            print(f"ERROR: 設定ファイルの読み込みに失敗しました: {e}。デフォルト設定を使用します。")
            return self.get_default_config()

    def save_config(self, config_data):
        """
        現在の設定データをファイルに保存する。
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.config = config_data # インスタンス内の設定も更新
            print(f"INFO: 設定を '{self.config_file}' に保存しました。")
        except IOError as e:
            print(f"ERROR: 設定ファイルの保存に失敗しました: {e}")

    def get(self, key, default=None):
        """
        指定されたキーの設定値を取得する。
        """
        return self.config.get(key, default)