# ファイル名: utils/camera_utils.py (修正)

import cv2
import logging
from pygrabber.dshow_graph import FilterGraph

logger = logging.getLogger(__name__)

def get_available_cameras():
    """
    システムで利用可能なカメラデバイスのインデックスと名前を辞書で返す。

    Returns:
        dict: {int: str}形式の辞書 (例: {0: 'HD USB Camera', 1: 'Integrated Camera'})
    """
    devices = FilterGraph().get_input_devices()
    available_cameras = {}
    for device_index, device_name in enumerate(devices):
        available_cameras[device_index] = device_name
        
    logger.info(f"利用可能なカメラ: {available_cameras}")
    return available_cameras