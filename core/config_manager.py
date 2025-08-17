# ファイル名: core/config_manager.py

import json
import os
from dataclasses import dataclass, field, asdict

# (データクラスの定義は変更ありません)
@dataclass
class FFTInitialViewConfig:
    variable_group: str = "all"
    show_fit_line: bool = True

@dataclass
class RealtimeSettingsConfig:
    video_source: str = "0"
    yolo_model_path: str = "models/yolov8n.pt"
    mediapipe_model_path: str = "models/face_landmarker.task"
    device: str = "cpu"

@dataclass
class AnalysisParametersConfig:
    UPDATE_INTERVAL_MS: int = 1000
    SLIDING_WINDOW_SECONDS: int = 30

@dataclass
class AppConfig:
    """アプリケーション設定全体を保持するデータクラス"""
    fft_initial_view: FFTInitialViewConfig = field(default_factory=FFTInitialViewConfig)
    realtime_settings: RealtimeSettingsConfig = field(default_factory=RealtimeSettingsConfig)
    analysis_parameters: AnalysisParametersConfig = field(default_factory=AnalysisParametersConfig)

    @classmethod
    def from_dict(cls, data):
        return cls(
            fft_initial_view=FFTInitialViewConfig(**data.get("fft_initial_view", {})),
            realtime_settings=RealtimeSettingsConfig(**data.get("realtime_settings", {})),
            analysis_parameters=AnalysisParametersConfig(**data.get("analysis_parameters", {}))
        )

class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config: AppConfig = self.load_config()

    def get_default_config(self):
        """デフォルト設定をAppConfigインスタンスとして返す"""
        return AppConfig()

    def load_config(self):
        """
        設定ファイルを読み込み、インスタンスのconfig属性を更新する。
        """
        if not os.path.exists(self.config_file):
            print(f"INFO: 設定ファイル '{self.config_file}' が見つかりません。デフォルト設定で作成します。")
            default_config = self.get_default_config()
            self.save_config(default_config) # オブジェクトを渡す
            return default_config
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                print(f"INFO: 設定ファイル '{self.config_file}' を読み込みました。")
                # 【修正】読み込んだデータでインスタンスのconfigを更新
                self.config = AppConfig.from_dict(config_data)
                return self.config
        except (json.JSONDecodeError, IOError) as e:
            print(f"ERROR: 設定ファイルの読み込みに失敗しました: {e}。デフォルト設定を使用します。")
            return self.get_default_config()

    def save_config(self, config_obj: AppConfig):
        """【修正】AppConfigオブジェクトを受け取り、JSONファイルに保存する"""
        self.config = config_obj  # インスタンスのconfigをまず更新
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(config_obj), f, indent=4, ensure_ascii=False)
            print(f"INFO: 設定を '{self.config_file}' に保存しました。")
        except IOError as e:
            print(f"ERROR: 設定ファイルの保存に失敗しました: {e}")