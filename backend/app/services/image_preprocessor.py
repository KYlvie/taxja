"""Image preprocessing for OCR optimization"""
import cv2
import numpy as np
from typing import Tuple, Optional
from PIL import Image
import io

from app.core.ocr_config import OCRConfig


class ImagePreprocessor:
    """Preprocess images to improve OCR accuracy"""

    def __init__(self):
        self.config = OCRConfig()

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Apply full preprocessing pipeline to image

        Args:
            image: Input image as numpy array (BGR format from OpenCV)

        Returns:
            Preprocessed image ready for OCR
        """
        # 1. Resize to optimal size
        image = self.resize_image(image)

        # 2. Convert to grayscale
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 3. Deskew image
        image = self.deskew(image)

        # 4. Remove noise
        image = self.remove_noise(image)

        # 5. Enhance contrast and brightness
        image = self.enhance_contrast(image)

        return image

    def resize_image(self, image: np.ndarray) -> np.ndarray:
        """
        Resize image to optimal size for OCR

        Args:
            image: Input image

        Returns:
            Resized image
        """
        height, width = image.shape[:2]
        max_width = self.config.IMAGE_MAX_WIDTH
        max_height = self.config.IMAGE_MAX_HEIGHT

        # Calculate scaling factor
        if width > max_width or height > max_height:
            scale = min(max_width / width, max_height / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            # Use INTER_AREA for downscaling (better quality)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

        # Upscale if image is too small (< 1000px width)
        elif width < 1000:
            scale = 1000 / width
            new_width = int(width * scale)
            new_height = int(height * scale)

            # Use INTER_CUBIC for upscaling (better quality)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

        return image

    def enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Enhance contrast and brightness using adaptive histogram equalization

        Args:
            image: Grayscale input image

        Returns:
            Enhanced image
        """
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(image)

        return enhanced

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Deskew image by detecting and correcting rotation angle

        Args:
            image: Grayscale input image

        Returns:
            Deskewed image
        """
        # Detect edges
        edges = cv2.Canny(image, 50, 150, apertureSize=3)

        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return image

        # Calculate average angle
        angles = []
        for line in lines:
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            # Filter out vertical lines
            if abs(angle) < 45:
                angles.append(angle)

        if not angles:
            return image

        # Calculate median angle
        median_angle = np.median(angles)

        # Only deskew if angle is significant (> 0.5 degrees)
        if abs(median_angle) > 0.5:
            # Rotate image
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            image = cv2.warpAffine(
                image,
                rotation_matrix,
                (width, height),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )

        return image

    def remove_noise(self, image: np.ndarray) -> np.ndarray:
        """
        Remove noise from image using morphological operations

        Args:
            image: Grayscale input image

        Returns:
            Denoised image
        """
        # Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(image, 9, 75, 75)

        # Apply morphological opening to remove small noise
        kernel = np.ones((2, 2), np.uint8)
        denoised = cv2.morphologyEx(denoised, cv2.MORPH_OPEN, kernel)

        return denoised

    def binarize(self, image: np.ndarray, method: str = "adaptive") -> np.ndarray:
        """
        Convert image to binary (black and white)

        Args:
            image: Grayscale input image
            method: Binarization method ('adaptive', 'otsu', or 'simple')

        Returns:
            Binary image
        """
        if method == "adaptive":
            # Adaptive thresholding (better for varying lighting)
            binary = cv2.adaptiveThreshold(
                image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
        elif method == "otsu":
            # Otsu's thresholding (automatic threshold selection)
            _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            # Simple thresholding
            _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)

        return binary

    def preprocess_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """
        Preprocess image from bytes

        Args:
            image_bytes: Image file as bytes

        Returns:
            Preprocessed image
        """
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode image")

        return self.preprocess(image)

    def preprocess_from_pil(self, pil_image: Image.Image) -> np.ndarray:
        """
        Preprocess PIL Image

        Args:
            pil_image: PIL Image object

        Returns:
            Preprocessed image
        """
        # Convert PIL to OpenCV format
        image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        return self.preprocess(image)

    def get_image_quality_score(self, image: np.ndarray) -> float:
        """
        Calculate image quality score (0.0 to 1.0)

        Args:
            image: Input image

        Returns:
            Quality score (higher is better)
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Calculate sharpness using Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Normalize to 0-1 range (empirically determined thresholds)
        # Good images typically have variance > 100
        quality_score = min(laplacian_var / 500.0, 1.0)

        return quality_score

    def suggest_improvements(self, image: np.ndarray) -> list[str]:
        """
        Suggest improvements for low-quality images

        Args:
            image: Input image

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Check image size
        height, width = image.shape[:2]
        if width < 800 or height < 600:
            suggestions.append("Image resolution is low. Try taking a higher resolution photo.")

        # Check sharpness
        quality_score = self.get_image_quality_score(image)
        if quality_score < 0.3:
            suggestions.append("Image is blurry. Hold the camera steady and ensure good focus.")

        # Check brightness
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        mean_brightness = np.mean(gray)
        if mean_brightness < 80:
            suggestions.append("Image is too dark. Ensure good lighting conditions.")
        elif mean_brightness > 200:
            suggestions.append("Image is too bright. Avoid direct light or flash.")

        # Check contrast
        std_brightness = np.std(gray)
        if std_brightness < 30:
            suggestions.append("Image has low contrast. Ensure document is clearly visible.")

        return suggestions

