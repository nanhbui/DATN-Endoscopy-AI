
import cv2
import numpy as np
from typing import Tuple, Optional, List


class ImageProcessor:
    """
    Advanced image processing operations for product capture.
    """

    def __init__(self):
        """Initialize image processor."""
        self.sift = cv2.SIFT_create()

    def apply_grabcut(
        self,
        image: np.ndarray,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        iterations: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Apply GrabCut algorithm for background segmentation.

        Args:
            image: Input BGR image
            bbox: Initial bounding box (x, y, w, h). If None, uses image center.
            iterations: Number of GrabCut iterations

        Returns:
            Tuple of (foreground_mask, segmented_image)
        """
        h, w = image.shape[:2]

        # Initialize rectangle
        if bbox is None:
            # Default to center 80% of image
            margin = 0.1
            x = int(w * margin)
            y = int(h * margin)
            width = int(w * (1 - 2 * margin))
            height = int(h * (1 - 2 * margin))
            bbox = (x, y, width, height)

        # Initialize mask
        mask = np.zeros(image.shape[:2], np.uint8)

        # GrabCut models (background and foreground)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        # Apply GrabCut
        cv2.grabCut(
            image,
            mask,
            bbox,
            bgd_model,
            fgd_model,
            iterations,
            cv2.GC_INIT_WITH_RECT
        )

        # Create binary mask (0 or 1)
        # GrabCut assigns: 0=bg, 1=fg, 2=probable_bg, 3=probable_fg
        foreground_mask = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')

        # Apply mask to image
        segmented_image = image * foreground_mask[:, :, np.newaxis]

        return foreground_mask, segmented_image

    def create_transparent_image(
        self,
        image: np.ndarray,
        mask: np.ndarray
    ) -> np.ndarray:
        """
        Create transparent PNG using mask as alpha channel.

        Args:
            image: Input BGR image
            mask: Binary mask (0-255)

        Returns:
            BGRA image with transparency
        """
        # Convert to BGRA
        bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

        # Set alpha channel to mask
        bgra[:, :, 3] = mask

        return bgra

    def refine_mask_with_morphology(
        self,
        mask: np.ndarray,
        kernel_size: int = 5
    ) -> np.ndarray:
        """
        Refine segmentation mask using morphological operations.

        Args:
            mask: Binary mask (0-255)
            kernel_size: Size of morphological kernel

        Returns:
            Refined mask
        """
        # Create morphological kernel
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

        # Apply morphological operations
        # 1. Opening to remove noise
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

        # 2. Closing to fill holes
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # 3. Dilate slightly to expand edges
        mask = cv2.dilate(mask, kernel, iterations=1)

        return mask

    def apply_super_resolution(
        self,
        image: np.ndarray,
        scale_factor: int = 2
    ) -> np.ndarray:
        """
        Apply super-resolution to enhance image quality.

        Args:
            image: Input image
            scale_factor: Upscaling factor (2, 3, or 4)

        Returns:
            Super-resolved image
        """
        # For now, use high-quality bicubic interpolation
        # In production, you could use DNN-based super-resolution models
        h, w = image.shape[:2]
        new_size = (w * scale_factor, h * scale_factor)

        # Bicubic interpolation for smooth upscaling
        upscaled = cv2.resize(image, new_size, interpolation=cv2.INTER_CUBIC)

        # Apply sharpening to enhance details
        upscaled = self.apply_sharpening(upscaled)

        return upscaled

    def apply_sharpening(
        self,
        image: np.ndarray,
        amount: float = 1.5
    ) -> np.ndarray:
        """
        Apply unsharp masking for image sharpening.

        Args:
            image: Input image
            amount: Sharpening amount (1.0 = no change, higher = more sharp)

        Returns:
            Sharpened image
        """
        # Create Gaussian blur
        blurred = cv2.GaussianBlur(image, (5, 5), 1.0)

        # Subtract blurred from original (unsharp mask)
        sharpened = cv2.addWeighted(image, amount, blurred, 1 - amount, 0)

        return sharpened

    def extract_sift_features(
        self,
        image: np.ndarray
    ) -> Tuple[List[cv2.KeyPoint], np.ndarray]:
        """
        Extract SIFT features from image.

        Args:
            image: Input image (BGR or grayscale)

        Returns:
            Tuple of (keypoints, descriptors)
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Detect and compute SIFT features
        keypoints, descriptors = self.sift.detectAndCompute(gray, None)

        return keypoints, descriptors

    def match_features(
        self,
        desc1: np.ndarray,
        desc2: np.ndarray,
        ratio_threshold: float = 0.75
    ) -> List[cv2.DMatch]:
        """
        Match SIFT features between two images using FLANN matcher.

        Args:
            desc1: Descriptors from first image
            desc2: Descriptors from second image
            ratio_threshold: Lowe's ratio test threshold

        Returns:
            List of good matches
        """
        # FLANN parameters
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)

        # Create FLANN matcher
        flann = cv2.FlannBasedMatcher(index_params, search_params)

        # Match descriptors
        matches = flann.knnMatch(desc1, desc2, k=2)

        # Apply Lowe's ratio test
        good_matches = []
        for m, n in matches:
            if m.distance < ratio_threshold * n.distance:
                good_matches.append(m)

        return good_matches

    def align_images(
        self,
        image1: np.ndarray,
        image2: np.ndarray,
        keypoints1: List[cv2.KeyPoint],
        keypoints2: List[cv2.KeyPoint],
        matches: List[cv2.DMatch]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Align two images using matched keypoints.

        Args:
            image1: First image
            image2: Second image
            keypoints1: Keypoints from first image
            keypoints2: Keypoints from second image
            matches: Good matches between images

        Returns:
            Tuple of (aligned_image2, homography_matrix)
        """
        # Extract matched point coordinates
        pts1 = np.float32([keypoints1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        pts2 = np.float32([keypoints2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

        # Find homography matrix
        H, mask = cv2.findHomography(pts2, pts1, cv2.RANSAC, 5.0)

        # Warp image2 to align with image1
        h, w = image1.shape[:2]
        aligned_image = cv2.warpPerspective(image2, H, (w, h))

        return aligned_image, H

    def enhance_contrast(
        self,
        image: np.ndarray,
        clip_limit: float = 2.0,
        tile_size: Tuple[int, int] = (8, 8)
    ) -> np.ndarray:
        """
        Enhance image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).

        Args:
            image: Input image
            clip_limit: Threshold for contrast limiting
            tile_size: Size of grid for histogram equalization

        Returns:
            Contrast-enhanced image
        """
        # Convert to LAB color space
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

        # Split channels
        l, a, b = cv2.split(lab)

        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
        l_enhanced = clahe.apply(l)

        # Merge channels
        lab_enhanced = cv2.merge([l_enhanced, a, b])

        # Convert back to BGR
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        return enhanced
