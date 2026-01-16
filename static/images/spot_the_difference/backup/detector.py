import cv2
import numpy as np
from skimage import filters, morphology, measure
from skimage.metrics import structural_similarity as ssim
import matplotlib.pyplot as plt

class MultiScaleImageDiff:
    def __init__(self, blur_kernel=3, morph_kernel=3):
        self.blur_kernel = blur_kernel
        self.morph_kernel = morph_kernel
        
    def multiscale_difference(self, img1, img2, scales=[1.0, 0.5, 0.25], weights=[0.6, 0.3, 0.1]):
        """
        Detect differences at multiple scales and combine results.
        This is the key to detecting both large and small changes effectively.
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
        Good for handling varying lighting and texture conditions.
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
        Excellent for detecting changes that matter to human perception.
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
        threshold = filters.threshold_otsu(diff)
        binary_diff = (diff > threshold * 0.5).astype(np.float32)
        
        return self._postprocess_difference(binary_diff)
    
    def gradient_based_difference(self, img1, img2, threshold=0.1):
        """
        Compare gradient/edge information between images.
        Excellent for detecting structural changes.
        """
        # Convert to grayscale if needed
        if len(img1.shape) == 3:
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        else:
            gray1, gray2 = img1, img2
        
        # Calculate gradients using Sobel operator
        grad1_x = cv2.Sobel(gray1, cv2.CV_64F, 1, 0, ksize=3)
        grad1_y = cv2.Sobel(gray1, cv2.CV_64F, 0, 1, ksize=3)
        grad1_mag = np.sqrt(grad1_x**2 + grad1_y**2)
        
        grad2_x = cv2.Sobel(gray2, cv2.CV_64F, 1, 0, ksize=3)
        grad2_y = cv2.Sobel(gray2, cv2.CV_64F, 0, 1, ksize=3)
        grad2_mag = np.sqrt(grad2_x**2 + grad2_y**2)
        
        # Calculate difference in gradient magnitudes
        grad_diff = np.abs(grad1_mag - grad2_mag)
        grad_diff = grad_diff / grad_diff.max()  # Normalize
        
        # Apply threshold
        result = (grad_diff > threshold).astype(np.float32)
        
        return self._postprocess_difference(result)
    
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
    
    def analyze_differences(self, img1_path, img2_path, method='multiscale', 
                          show_results=True, save_results=False):
        """
        Complete analysis pipeline for image difference detection.
        
        Parameters:
        - img1_path, img2_path: paths to images
        - method: 'multiscale', 'adaptive', 'structural', 'gradient', or 'all'
        - show_results: whether to display results
        - save_results: whether to save result images
        """
        # Load images
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        
        if img1 is None or img2 is None:
            raise ValueError("Could not load one or both images")
        
        results = {}
        
        if method == 'multiscale' or method == 'all':
            diff = self.multiscale_difference(img1, img2)
            results['multiscale'] = diff
            
        if method == 'adaptive' or method == 'all':
            diff = self.adaptive_threshold_difference(img1, img2)
            results['adaptive'] = diff
            
        if method == 'structural' or method == 'all':
            diff = self.structural_similarity_difference(img1, img2)
            results['structural'] = diff
            
        if method == 'gradient' or method == 'all':
            diff = self.gradient_based_difference(img1, img2)
            results['gradient'] = diff
        
        if show_results:
            self._display_results(img1, img2, results)
        
        if save_results:
            self._save_results(results)
        
        return results
    
    def _display_results(self, img1, img2, results):
        """Display original images and difference results."""
        n_results = len(results)
        fig, axes = plt.subplots(2, n_results + 1, figsize=(4*(n_results+1), 8))
        
        if n_results == 1:
            axes = axes.reshape(2, -1)
        
        # Show original images
        axes[0, 0].imshow(cv2.cvtColor(img1, cv2.COLOR_BGR2RGB))
        axes[0, 0].set_title('Original Image')
        axes[0, 0].axis('off')
        
        axes[1, 0].imshow(cv2.cvtColor(img2, cv2.COLOR_BGR2RGB))
        axes[1, 0].set_title('Modified Image')
        axes[1, 0].axis('off')
        
        # Show difference results
        for i, (method_name, diff) in enumerate(results.items(), 1):
            # Show difference map
            axes[0, i].imshow(diff, cmap='hot', vmin=0, vmax=1)
            axes[0, i].set_title(f'{method_name.title()} Difference')
            axes[0, i].axis('off')
            
            # Show highlighted differences on original
            highlighted = img1.copy()
            mask = (diff > 0.1).astype(np.uint8)
            highlighted[mask > 0] = [0, 0, 255]  # Red highlights
            
            axes[1, i].imshow(cv2.cvtColor(highlighted, cv2.COLOR_BGR2RGB))
            axes[1, i].set_title(f'{method_name.title()} Highlighted')
            axes[1, i].axis('off')
            
            # Calculate statistics
            total_pixels = diff.size
            changed_pixels = np.sum(diff > 0.1)
            change_percentage = (changed_pixels / total_pixels) * 100
            
            print(f"{method_name.title()} Method:")
            print(f"  Changed pixels: {changed_pixels} ({change_percentage:.2f}%)")
            print(f"  Average change intensity: {np.mean(diff[diff > 0.1]):.3f}")
            print()
        
        plt.tight_layout()
        plt.show()
    
    def _save_results(self, results):
        """Save difference results to files."""
        for method_name, diff in results.items():
            filename = f"difference_{method_name}.png"
            # Convert to 8-bit for saving
            diff_8bit = (diff * 255).astype(np.uint8)
            cv2.imwrite(filename, diff_8bit)
            print(f"Saved {filename}")

# Example usage and testing
def example_usage():
    """Example of how to use the MultiScaleImageDiff class."""
    
    # Initialize the detector
    detector = MultiScaleImageDiff(blur_kernel=3, morph_kernel=3)
    
    # Example 1: Multi-scale analysis (recommended for most cases)
    print("Multi-scale Analysis:")
    print("This method analyzes images at multiple resolutions to detect")
    print("both large structural changes and fine detail differences.")
    print()
    
    # Example 2: Compare all methods
    # results = detector.analyze_differences('image1.jpg', 'image2.jpg', 
    #                                       method='all', show_results=True)
    
    # Example 3: Fine-tune parameters for specific use case
    print("Parameter Tuning Guidelines:")
    print("- blur_kernel: 0-5, higher values reduce noise but may miss fine details")
    print("- morph_kernel: 1-10, higher values remove small scattered differences")
    print("- For very noisy images: increase blur_kernel to 5")
    print("- For clean images with fine details: set blur_kernel to 0-1")
    print("- For images with many small irrelevant changes: increase morph_kernel")
    print()
    
    # Example 4: Batch processing
    def batch_process_images(image_pairs, method='multiscale'):
        """Process multiple image pairs."""
        results = []
        for img1_path, img2_path in image_pairs:
            try:
                result = detector.analyze_differences(img1_path, img2_path, 
                                                    method=method, show_results=False)
                results.append(result)
                print(f"Processed: {img1_path} vs {img2_path}")
            except Exception as e:
                print(f"Error processing {img1_path} vs {img2_path}: {e}")
        return results
    
    print("Usage Examples:")
    print("1. detector.analyze_differences('img1.jpg', 'img2.jpg', method='multiscale')")
    print("2. detector.analyze_differences('img1.jpg', 'img2.jpg', method='all')")
    print("3. results = detector.multiscale_difference(img1_array, img2_array)")

# Additional utility functions
def create_synthetic_test_images():
    """Create synthetic test images to demonstrate different types of changes."""
    
    # Create base image
    base = np.zeros((400, 400, 3), dtype=np.uint8)
    base.fill(128)  # Gray background
    
    # Add some patterns
    cv2.rectangle(base, (50, 50), (150, 150), (255, 0, 0), -1)
    cv2.circle(base, (300, 100), 50, (0, 255, 0), -1)
    cv2.line(base, (200, 200), (350, 350), (0, 0, 255), 5)
    
    # Create modified version with different types of changes
    modified = base.copy()
    
    # Large change: remove rectangle
    cv2.rectangle(modified, (50, 50), (150, 150), (128, 128, 128), -1)
    
    # Medium change: change circle color
    cv2.circle(modified, (300, 100), 50, (255, 255, 0), -1)
    
    # Small change: add small dots
    for i in range(10):
        x, y = np.random.randint(200, 350, 2)
        cv2.circle(modified, (x, y), 2, (255, 255, 255), -1)
    
    # Very small change: modify line slightly
    cv2.line(modified, (200, 200), (355, 345), (0, 0, 255), 5)
    
    # Add noise to test robustness
    noise = np.random.normal(0, 10, modified.shape).astype(np.int16)
    modified = np.clip(modified.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    return base, modified

if __name__ == "__main__":
    example_usage()
    
    # Create and test with synthetic images
    print("\nTesting with synthetic images:")
    base_img, modified_img = create_synthetic_test_images()
    
    # Save test images
    cv2.imwrite('test_original.jpg', base_img)
    cv2.imwrite('test_modified.jpg', modified_img)
    
    # Test the detector
    detector = MultiScaleImageDiff()
    results = detector.analyze_differences('anne.png', 'anne_bling.png', 
                                         method='all', show_results=True)