# ファイル名: services/analysis_utils.py (新規作成)

import numpy as np
from constants import ALL_VARIABLES
def calculate_emotion_features(blendshapes_result):
    """
    MediaPipeのBlendshapes(表情)の出力から、感情に関する特徴量を計算する。
    """
    features = {}
    if not blendshapes_result:
        return features

    # MediaPipeのカテゴリ名を、私たちが使っている定数名に変換する辞書
    emotion_map = {
        'mouthShrugUpper': 'contempt', 'mouthSmile': 'happy',
        'eyeLookInLeft': 'left_eye', 'eyeLookInRight': 'right_eye',
        # 必要に応じて他のマッピングを追加
    }
    
    # 計算しやすいように、カテゴリ名をキー、スコアを値とする辞書に変換
    blendshapes = {shape.category_name: shape.score for shape in blendshapes_result[0]}

    for mp_name, const_name in emotion_map.items():
        if mp_name in blendshapes:
            features[const_name] = blendshapes.get(mp_name, 0.0)
            
    return features

def calculate_head_pose_features(transformation_matrix_result):
    """
    MediaPipeの変換行列から、頭の向き(roll, pitch, yaw)を計算する。
    """
    features = {}
    if not transformation_matrix_result:
        return features

    matrix = transformation_matrix_result[0]
    sy = np.sqrt(matrix[0,0] * matrix[0,0] +  matrix[1,0] * matrix[1,0])
    
    singular = sy < 1e-6
    if not singular:
        x = np.arctan2(matrix[2,1], matrix[2,2])
        y = np.arctan2(-matrix[2,0], sy)
        z = np.arctan2(matrix[1,0], matrix[0,0])
    else:
        x = np.arctan2(-matrix[1,2], matrix[1,1])
        y = np.arctan2(-matrix[2,0], sy)
        z = 0
    
    features['roll'] = np.degrees(x)
    features['pitch'] = np.degrees(y)
    features['yaw'] = np.degrees(z)

    return features