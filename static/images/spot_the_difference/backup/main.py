"""
Complete example of image difference detection with location extraction.

Usage:
    python main.py
"""

import cv2
import numpy as np
from detector import MultiScaleImageDiff
from extractor import ClusteredChangeExtractor

def main():
    """Main function - replace image paths with your own."""
    
    print("=== Image Difference Detection with Clustering ===\n")
    
    # REPLACE THESE WITH YOUR IMAGE PATHS
    img1_path = 'anne.png'
    img2_path = 'anne_bling.png'
    
    try:
        # Step 1: Initialize
        detector = MultiScaleImageDiff()
        extractor = ClusteredChangeExtractor(min_area=50)
        
        # Step 2: Detect differences
        print("Detecting differences...")
        diff_map, img1, img2 = detector.detect_from_files(img1_path, img2_path)
        
        # Step 3: Extract clustered locations
        print("Extracting clustered locations...")
        locations = extractor.extract_clustered_locations(
            diff_map, 
            threshold=0.1, 
            clustering_method='morphological',
            cluster_kernel_size=25
        )
        
        # Step 4: Print results
        extractor.print_results(locations)
        
        # Step 5: Save visualization and data
        extractor.visualize_locations(img1, locations, 'results.jpg')
        extractor.export_to_json(locations, 'locations.json')
        
        print("\nFiles saved: results.jpg and locations.json")
        return locations
        
    except Exception as e:
        print(f"Error: {e}")
        print("Creating test images instead...")
        return create_test_example()

def create_test_example():
    """Create test images if your images don't exist."""
    
    # Create test images
    img1 = np.ones((400, 600, 3), dtype=np.uint8) * 128
    cv2.rectangle(img1, (50, 50), (150, 150), (255, 100, 100), -1)
    cv2.circle(img1, (400, 100), 50, (100, 255, 100), -1)
    
    img2 = img1.copy()
    cv2.rectangle(img2, (50, 50), (150, 150), (128, 128, 128), -1)  # Change
    cv2.circle(img2, (450, 250), 30, (255, 100, 255), -1)  # New circle
    
    # Save test images
    cv2.imwrite('test_original.jpg', img1)
    cv2.imwrite('test_modified.jpg', img2)
    print("Created test_original.jpg and test_modified.jpg")
    
    # Run detection
    detector = MultiScaleImageDiff()
    extractor = ClusteredChangeExtractor(min_area=50)
    
    diff_map = detector.multiscale_difference(img1, img2)
    locations = extractor.extract_clustered_locations(
        diff_map, threshold=0.1, clustering_method='morphological'
    )
    
    extractor.print_results(locations)
    extractor.visualize_locations(img1, locations, 'test_results.jpg')
    
    return locations

if __name__ == "__main__":
    main()