"""OCR configuration for Tesseract"""
import os
from typing import Dict, Any


class OCRConfig:
    """Configuration for Tesseract OCR"""
    
    # Tesseract configuration string
    # --oem 3: Use default OCR Engine Mode (LSTM + Legacy)
    # --psm 6: Assume a single uniform block of text
    # -l deu+eng: Use German and English language packs
    TESSERACT_CONFIG = '--oem 3 --psm 6 -l deu+eng'
    
    # Confidence threshold for OCR results
    CONFIDENCE_THRESHOLD = 0.6
    
    # Image preprocessing settings
    IMAGE_MAX_WIDTH = 2000
    IMAGE_MAX_HEIGHT = 2000
    IMAGE_DPI = 300
    
    # Supported file formats
    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'pdf']
    MAX_FILE_SIZE_MB = 10
    
    @classmethod
    def get_tesseract_cmd(cls) -> str:
        """Get Tesseract command path based on OS"""
        # For Windows
        if os.name == 'nt':
            # Try user-level installation first
            user_path = os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe')
            if os.path.exists(user_path):
                return user_path
            # Fall back to system-level installation
            return r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        # For Linux/Mac
        return 'tesseract'
    
    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return {
            'tesseract_config': cls.TESSERACT_CONFIG,
            'confidence_threshold': cls.CONFIDENCE_THRESHOLD,
            'image_max_width': cls.IMAGE_MAX_WIDTH,
            'image_max_height': cls.IMAGE_MAX_HEIGHT,
            'supported_formats': cls.SUPPORTED_FORMATS,
            'max_file_size_mb': cls.MAX_FILE_SIZE_MB
        }

