import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim

class MultiScaleImageDiff:
    """Multi-scale image difference detector for finding changes of all sizes."""
    
    def __init__(self, blur_kernel=3, morph_kernel=3):
        self.blur_kernel = blur_kernel
        self.morph_kernel = morph_kernel
    
    def multiscale_difference(self, img1, img2, scales=[1.0, 0.5, 0.25], weights=[0.6, 0.3, 0.1]):
        """
        Detect differences at multiple scales and combine results.
        
        Args:
            img1, img2: Input images (numpy arrays)
            scales: List of scales to analyze
            weights: Weights for combining results from different scales
        
        Returns:
            2D numpy array with difference values (0-1 range)
        """
        # Ensure images are same size
        h, w = min(img1.shape[0], img2.shape[0]), min(img1.shape[1], img2.shape[1])
        img1 = img1[:h, :w]
        img2 = img2[:h, :w]
        
        combined_diff = np.zeros((h, w), dtype=np.float32)
        
        for scale, weight in zip(scales, weights):
            # Calculate scaled dimensions
            new_h, new_w = int(h * scale), int(w * scale)
            
            # Resize images
            scaled_img1 = cv2.resize(img1, (new_w, new_h), interpolation=cv2.INTER_AREA)
            scaled_img2 = cv2.resize(img2, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # Calculate difference at this scale
            diff = self._calculate_difference(scaled_img1, scaled_img2)
            
            # Resize difference back to original size
            diff_resized = cv2.resize(diff, (w, h), interpolation=cv2.INTER_LINEAR)
            
            # Add to combined result with weight
            combined_diff += diff_resized * weight
        
        # Normalize and apply post-processing
        combined_diff = np.clip(combined_diff, 0, 1)
        return self._postprocess_difference(combined_diff)
    
    def adaptive_threshold_difference(self, img1, img2, base_threshold=0.1):
        """
        Use adaptive thresholding based on local image statistics.
        
        Args:
            img1, img2: Input images
            base_threshold: Base threshold value
        
        Returns:
            2D numpy array with difference values
        """
        # Convert to grayscale if needed
        if len(img1.shape) == 3:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            gray1, gray2 = img1, img2
        
        # Calculate absolute difference
        diff = cv2.absdiff(gray1, gray2).astype(np.float32) / 255.0
        
        # Calculate local mean using gaussian blur
        local_mean = cv2.GaussianBlur(diff, (15, 15), 0)
        
        # Adaptive threshold: base threshold + fraction of local activity
        adaptive_thresh = base_threshold + local_mean * 0.5
        
        # Apply adaptive threshold
        result = (diff > adaptive_thresh).astype(np.float32)
        
        return self._postprocess_difference(result)
    
    def structural_similarity_difference(self, img1, img2, window_size=11):
        """
        Use structural similarity (SSIM) for perceptually meaningful differences.
        
        Args:
            img1, img2: Input images
            window_size: Window size for SSIM calculation
        
        Returns:
            2D numpy array with difference values
        """
        # Convert to grayscale if needed
        if len(img1.shape) == 3:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            gray1, gray2 = img1, img2
        
        # Calculate SSIM
        ssim_map = ssim(gray1, gray2, 
                       win_size=window_size, 
                       full=True, 
                       data_range=255)[1]
        
        # Convert to dissimilarity (1 - SSIM)
        diff = 1 - ssim_map
        
        # Threshold to get binary difference
        from skimage import filters
        threshold = filters.threshold_otsu(diff)
        binary_diff = (diff > threshold * 0.5).astype(np.float32)
        
        return self._postprocess_difference(binary_diff)
    
    def _calculate_difference(self, img1, img2):
        """Calculate basic difference between two images."""
        if len(img1.shape) == 3:
            # For color images, calculate difference in each channel
            diff = np.sqrt(np.sum((img1.astype(np.float32) - img2.astype(np.float32))**2, axis=2))
            diff = diff / (255 * np.sqrt(3))  # Normalize
        else:
            # For grayscale images
            diff = np.abs(img1.astype(np.float32) - img2.astype(np.float32)) / 255.0
        
        return diff
    
    def _postprocess_difference(self, diff):
        """Apply noise reduction and morphological operations."""
        # Apply Gaussian blur for noise reduction
        if self.blur_kernel > 0:
            diff = cv2.GaussianBlur(diff, (self.blur_kernel, self.blur_kernel), 0)
        
        # Apply morphological opening to remove small noise
        if self.morph_kernel > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                             (self.morph_kernel, self.morph_kernel))
            diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, kernel)
        
        return diff
    
    def detect_from_files(self, img1_path, img2_path, method='multiscale'):
        """
        Convenience method to detect differences from file paths.
        
        Args:
            img1_path, img2_path: Image file paths
            method: Detection method ('multiscale', 'adaptive', 'structural')
        
        Returns:
            Difference map and loaded images
        """
        # Load images
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        
        if img1 is None or img2 is None:
            raise ValueError("Could not load one or both images")
        
        # Apply selected method
        if method == 'multiscale':
            diff_map = self.multiscale_difference(img1, img2)
        elif method == 'adaptive':
            diff_map = self.adaptive_threshold_difference(img1, img2)
        elif method == 'structural':
            diff_map = self.structural_similarity_difference(img1, img2)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return diff_map, img1, img2