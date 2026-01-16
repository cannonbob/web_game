"""
Complete example of image difference detection with location extraction.

This script demonstrates how to:
1. Detect differences between two images
2. Extract and cluster change locations
3. Visualize and export results

Usage:
    python main.py
"""

import cv2
import numpy as np
from detector import MultiScaleImageDiff
from extractor import ClusteredChangeExtractor

def create_test_images():
    """Create synthetic test images if real images aren't available."""
    print("Creating synthetic test images...")
    
    # Create base image
    img1 = np.ones((400, 600, 3), dtype=np.uint8) * 128
    
    # Add some shapes to base image
    cv2.rectangle(img1, (50, 50), (150, 150), (255, 100, 100), -1)
    cv2.circle(img1, (400, 100), 50, (100, 255, 100), -1)
    cv2.rectangle(img1, (200, 250), (350, 350), (100, 100, 255), -1)
    cv2.circle(img1, (500, 300), 30, (255, 255, 100), -1)
    
    # Create modified version with changes
    img2 = img1.copy()
    
    # Make some changes
    cv2.rectangle(img2, (50, 50), (150, 150), (128, 128, 128), -1)  # Remove rectangle
    cv2.circle(img2, (400, 100), 50, (255, 255, 100), -1)  # Change circle color
    cv2.rectangle(img2, (450, 250), (550, 320), (255, 100, 255), -1)  # Add new rectangle
    cv2.circle(img2, (100, 300), 25, (200, 200, 200), -1)  # Add new circle
    
    # Add some scattered small changes
    for i in range(8):
        x, y = np.random.randint(50, 550), np.random.randint(50, 350)
        cv2.circle(img2, (x, y), 5, (255, 255, 255), -1)
    
    # Save test images
    cv2.imwrite('test_original.jpg', img1)
    cv2.imwrite('test_modified.jpg', img2)
    print("Created: test_original.jpg and test_modified.jpg")
    
    return img1, img2

def main():
    """Main function demonstrating the complete workflow."""
    
    print("=== Image Difference Detection with Clustering ===\n")
    
    # Step 1: Load or create images
    img1_path = 'test_original.jpg'
    img2_path = 'test_modified.jpg'
    
    try:
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        
        if img1 is None or img2 is None:
            print("Test images not found. Creating new ones...")
            img1, img2 = create_test_images()
        else:
            print(f"Loaded existing images: {img1.shape} and {img2.shape}")
    
    except Exception as e:
        print(f"Error loading images: {e}")
        print("Creating synthetic test images...")
        img1, img2 = create_test_images()
    
    # Step 2: Initialize detector and extractor
    print("\nInitializing detector and extractor...")
    detector = MultiScaleImageDiff(blur_kernel=1, morph_kernel=3)
    extractor = ClusteredChangeExtractor(min_area=50, connectivity=2)
    
    # Step 3: Detect differences
    print("\n=== DETECTING DIFFERENCES ===")
    diff_map = detector.multiscale_difference(img1, img2)
    print(f"Difference map created with range: {diff_map.min():.3f} to {diff_map.max():.3f}")
    
    # Step 4: Extract locations with clustering
    print("\n=== EXTRACTING LOCATIONS (WITH CLUSTERING) ===")
    
    # Try morphological clustering (recommended)
    print("\n--- Morphological Clustering ---")
    locations_morph = extractor.extract_clustered_locations(
        diff_map, 
        threshold=0.1, 
        clustering_method='morphological',
        cluster_kernel_size=25
    )
    
    print("Morphological clustering results:")
    extractor.print_results(locations_morph)
    
    # Try distance-based clustering for comparison
    print("\n--- Distance-Based Clustering ---")
    locations_dist = extractor.extract_clustered_locations(
        diff_map, 
        threshold=0.1, 
        clustering_method='distance',
        cluster_distance=80
    )
    
    print("Distance-based clustering results:")
    extractor.print_results(locations_dist)
    
    # Step 5: Create visualizations
    print("\n=== CREATING VISUALIZATIONS ===")
    
    # Visualize morphological clustering results
    vis_morph = extractor.visualize_locations(
        img1, locations_morph, 'results_morphological.jpg'
    )
    
    # Visualize distance clustering results
    vis_dist = extractor.visualize_locations(
        img1, locations_dist, 'results_distance.jpg'
    )
    
    # Step 6: Export results
    print("\n=== EXPORTING RESULTS ===")
    
    # Export the better result (usually morphological)
    better_locations = locations_morph if len(locations_morph['bounding_boxes']) <= len(locations_dist['bounding_boxes']) else locations_dist
    better_method = "morphological" if better_locations == locations_morph else "distance"
    
    extractor.export_to_json(better_locations, f'change_locations_{better_method}.json')
    
    # Step 7: Print final summary
    print(f"\n=== FINAL SUMMARY ===")
    print(f"Best clustering method: {better_method}")
    print(f"Total change regions found: {len(better_locations['bounding_boxes'])}")
    
    if better_locations['bounding_boxes']:
        print(f"\nChange locations:")
        for bbox in better_locations['bounding_boxes']:
            print(f"  Region {bbox['id']}: ({bbox['x']}, {bbox['y']}) "
                  f"size {bbox['width']}×{bbox['height']} "
                  f"area {bbox['area']} pixels")
    
    print(f"\nFiles created:")
    print(f"- results_{better_method}.jpg (visualization)")
    print(f"- change_locations_{better_method}.json (coordinate data)")
    
    return better_locations

def simple_usage_example():
    """Simple example for quick usage."""
    
    print("\n=== SIMPLE USAGE EXAMPLE ===\n")
    
    # Quick detection and location extraction
    detector = MultiScaleImageDiff()
    extractor = ClusteredChangeExtractor(min_area=30)
    
    # Replace these with your actual image paths
    img1_path = 'your_original_image.jpg'
    img2_path = 'your_modified_image.jpg'
    
    try:
        # One-liner detection
        diff_map, img1, img2 = detector.detect_from_files(img1_path, img2_path, method='multiscale')
        
        # One-liner location extraction with clustering
        locations = extractor.extract_clustered_locations(
            diff_map, threshold=0.1, clustering_method='morphological'
        )
        
        # Print results
        extractor.print_results(locations)
        
        # Save visualization
        extractor.visualize_locations(img1, locations, 'simple_results.jpg')
        
        # Export data
        extractor.export_to_json(locations, 'simple_locations.json')
        
        return locations
        
    except Exception as e:
        print(f"Simple example failed (need real images): {e}")
        print("Run main() function instead to use test images")
        return None

def compare_methods():
    """Compare different detection methods."""
    
    print("\n=== COMPARING DETECTION METHODS ===\n")
    
    # Create test images
    img1, img2 = create_test_images()
    
    detector = MultiScaleImageDiff()
    extractor = ClusteredChangeExtractor(min_area=30)
    
    methods = ['multiscale', 'adaptive', 'structural']
    results = {}
    
    for method in methods:
        print(f"\n--- Testing {method.upper()} method ---")
        
        try:
            # Detect differences
            if method == 'multiscale':
                diff_map = detector.multiscale_difference(img1, img2)
            elif method == 'adaptive':
                diff_map = detector.adaptive_threshold_difference(img1, img2)
            elif method == 'structural':
                diff_map = detector.structural_similarity_difference(img1, img2)
            
            # Extract locations
            locations = extractor.extract_clustered_locations(
                diff_map, threshold=0.1, clustering_method='morphological'
            )
            
            results[method] = locations
            
            print(f"{method} method found {len(locations['bounding_boxes'])} regions")
            
            # Save visualization
            extractor.visualize_locations(img1, locations, f'comparison_{method}.jpg')
            
        except Exception as e:
            print(f"Error with {method} method: {e}")
    
    return results

if __name__ == "__main__":
    # Run the complete example
    print("Running complete workflow...")
    locations = main()
    
    # Uncomment to run other examples:
    # simple_usage_example()
    # compare_methods()
    
    print("\n=== DONE ===")
    print("Check the created image files to see the detected changes!")