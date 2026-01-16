"""
Automatic filtering to remove false positive changes based on various criteria.
"""

import cv2
import numpy as np
from detector import MultiScaleImageDiff
from extractor import ClusteredChangeExtractor

class AutoChangeFilter:
    """Automatically filter out likely false positive changes."""
    
    def __init__(self):
        pass
    
    def filter_changes(self, img1, img2, locations, criteria=None):
        """
        Filter changes based on multiple criteria.
        
        Args:
            img1, img2: Original images
            locations: Dictionary with bounding boxes
            criteria: Dictionary with filtering parameters
        
        Returns:
            Filtered locations dictionary
        """
        if criteria is None:
            criteria = self.get_default_criteria()
        
        if 'bounding_boxes' not in locations or len(locations['bounding_boxes']) == 0:
            return locations
        
        original_boxes = locations['bounding_boxes']
        filtered_boxes = []
        
        print(f"\n=== AUTOMATIC FILTERING ===")
        print(f"Starting with {len(original_boxes)} detected changes")
        print(f"Applying filters: {list(criteria.keys())}")
        
        for bbox in original_boxes:
            if self._passes_all_filters(img1, img2, bbox, criteria):
                filtered_boxes.append(bbox)
        
        print(f"After filtering: {len(filtered_boxes)} changes remain")
        print(f"Removed {len(original_boxes) - len(filtered_boxes)} likely false positives")
        
        # Update locations
        filtered_locations = {
            'bounding_boxes': filtered_boxes,
            'summary': self._calculate_summary(filtered_boxes),
            'filter_criteria': criteria,
            'original_count': len(original_boxes)
        }
        
        return filtered_locations
    
    def get_default_criteria(self):
        """Get default filtering criteria that work well for most images."""
        return {
            'min_area': 50,           # Minimum area in pixels
            'max_area': 20000,        # Maximum area in pixels  
            'min_dimension': 5,       # Minimum width or height
            'max_aspect_ratio': 10,   # Max width/height ratio (removes thin lines)
            'min_intensity_diff': 15, # Minimum average intensity difference
            'edge_distance': 10       # Minimum distance from image edges
        }
    
    def get_strict_criteria(self):
        """Get strict criteria for reducing false positives."""
        return {
            'min_area': 100,
            'max_area': 15000,
            'min_dimension': 8,
            'max_aspect_ratio': 8,
            'min_intensity_diff': 20,
            'edge_distance': 20
        }
    
    def get_loose_criteria(self):
        """Get loose criteria for keeping more changes."""
        return {
            'min_area': 25,
            'max_area': 50000,
            'min_dimension': 3,
            'max_aspect_ratio': 20,
            'min_intensity_diff': 10,
            'edge_distance': 5
        }
    
    def _passes_all_filters(self, img1, img2, bbox, criteria):
        """Check if a bounding box passes all filtering criteria."""
        
        # Size filters
        if bbox['area'] < criteria.get('min_area', 0):
            return False
        
        if bbox['area'] > criteria.get('max_area', float('inf')):
            return False
        
        # Dimension filters
        min_dim = criteria.get('min_dimension', 0)
        if bbox['width'] < min_dim or bbox['height'] < min_dim:
            return False
        
        # Aspect ratio filter (remove very thin lines)
        max_aspect = criteria.get('max_aspect_ratio', float('inf'))
        aspect_ratio = max(bbox['width'] / bbox['height'], bbox['height'] / bbox['width'])
        if aspect_ratio > max_aspect:
            return False
        
        # Edge distance filter (remove changes too close to image borders)
        edge_dist = criteria.get('edge_distance', 0)
        img_height, img_width = img1.shape[:2]
        if (bbox['x'] < edge_dist or 
            bbox['y'] < edge_dist or 
            bbox['x'] + bbox['width'] > img_width - edge_dist or
            bbox['y'] + bbox['height'] > img_height - edge_dist):
            return False
        
        # Intensity difference filter
        min_intensity = criteria.get('min_intensity_diff', 0)
        if min_intensity > 0:
            avg_intensity_diff = self._calculate_intensity_difference(img1, img2, bbox)
            if avg_intensity_diff < min_intensity:
                return False
        
        return True
    
    def _calculate_intensity_difference(self, img1, img2, bbox):
        """Calculate average intensity difference in the bounding box region."""
        x, y, w, h = bbox['x'], bbox['y'], bbox['width'], bbox['height']
        
        # Extract regions
        region1 = img1[y:y+h, x:x+w]
        region2 = img2[y:y+h, x:x+w]
        
        # Convert to grayscale if needed
        if len(region1.shape) == 3:
            region1 = cv2.cvtColor(region1, cv2.COLOR_BGR2GRAY)
            region2 = cv2.cvtColor(region2, cv2.COLOR_BGR2GRAY)
        
        # Calculate average absolute difference
        diff = np.abs(region1.astype(np.float32) - region2.astype(np.float32))
        return np.mean(diff)
    
    def _calculate_summary(self, bounding_boxes):
        """Calculate summary statistics."""
        if not bounding_boxes:
            return {
                'total_regions': 0,
                'total_changed_pixels': 0,
                'largest_change_area': 0,
                'average_change_area': 0
            }
        
        areas = [bbox['area'] for bbox in bounding_boxes]
        return {
            'total_regions': len(bounding_boxes),
            'total_changed_pixels': sum(areas),
            'largest_change_area': max(areas),
            'average_change_area': sum(areas) / len(areas)
        }
    
    def analyze_changes(self, img1, img2, locations):
        """Analyze the characteristics of detected changes to help tune filters."""
        
        if 'bounding_boxes' not in locations or len(locations['bounding_boxes']) == 0:
            print("No changes to analyze")
            return
        
        bboxes = locations['bounding_boxes']
        
        # Calculate statistics
        areas = [bbox['area'] for bbox in bboxes]
        widths = [bbox['width'] for bbox in bboxes]
        heights = [bbox['height'] for bbox in bboxes]
        aspect_ratios = [max(bbox['width']/bbox['height'], bbox['height']/bbox['width']) for bbox in bboxes]
        
        # Calculate intensity differences
        intensity_diffs = []
        for bbox in bboxes:
            intensity_diff = self._calculate_intensity_difference(img1, img2, bbox)
            intensity_diffs.append(intensity_diff)
        
        print(f"\n=== CHANGE ANALYSIS ===")
        print(f"Total changes: {len(bboxes)}")
        print(f"")
        print(f"Area statistics:")
        print(f"  Min: {min(areas)} pixels")
        print(f"  Max: {max(areas)} pixels")
        print(f"  Mean: {np.mean(areas):.1f} pixels")
        print(f"  Median: {np.median(areas):.1f} pixels")
        print(f"")
        print(f"Dimension statistics:")
        print(f"  Width range: {min(widths)} - {max(widths)} pixels")
        print(f"  Height range: {min(heights)} - {max(heights)} pixels")
        print(f"  Max aspect ratio: {max(aspect_ratios):.1f}")
        print(f"")
        print(f"Intensity difference statistics:")
        print(f"  Min: {min(intensity_diffs):.1f}")
        print(f"  Max: {max(intensity_diffs):.1f}")
        print(f"  Mean: {np.mean(intensity_diffs):.1f}")
        print(f"  Median: {np.median(intensity_diffs):.1f}")
        print(f"")
        
        # Suggest filter values
        print(f"Suggested filter values to remove bottom 25% of changes:")
        print(f"  min_area: {int(np.percentile(areas, 25))}")
        print(f"  min_intensity_diff: {int(np.percentile(intensity_diffs, 25))}")
        print(f"")
        print(f"Suggested filter values to remove bottom 50% of changes:")
        print(f"  min_area: {int(np.percentile(areas, 50))}")
        print(f"  min_intensity_diff: {int(np.percentile(intensity_diffs, 50))}")
        
        return {
            'areas': areas,
            'intensity_diffs': intensity_diffs,
            'aspect_ratios': aspect_ratios,
            'widths': widths,
            'heights': heights
        }

def quick_filter_workflow(img1_path, img2_path, filter_level='default'):
    """
    Quick workflow with automatic filtering only.
    
    Args:
        img1_path, img2_path: Image paths
        filter_level: 'loose', 'default', 'strict', or custom criteria dict
    
    Returns:
        Filtered locations
    """
    print("=== QUICK FILTER WORKFLOW ===\n")
    
    # Step 1: Detect and cluster
    print("1. Detecting and clustering changes...")
    detector = MultiScaleImageDiff()
    extractor = ClusteredChangeExtractor(min_area=20)
    
    diff_map, img1, img2 = detector.detect_from_files(img1_path, img2_path)
    locations = extractor.extract_clustered_locations(
        diff_map, threshold=0.1, clustering_method='morphological'
    )
    
    print(f"   Initial detection: {len(locations['bounding_boxes'])} changes")
    
    if len(locations['bounding_boxes']) == 0:
        print("No changes detected!")
        return locations
    
    # Step 2: Analyze changes (optional - helps tune filters)
    filter_obj = AutoChangeFilter()
    print("2. Analyzing change characteristics...")
    filter_obj.analyze_changes(img1, img2, locations)
    
    # Step 3: Apply automatic filtering
    print("3. Applying automatic filters...")
    
    if filter_level == 'loose':
        criteria = filter_obj.get_loose_criteria()
    elif filter_level == 'strict':
        criteria = filter_obj.get_strict_criteria()
    elif filter_level == 'default':
        criteria = filter_obj.get_default_criteria()
    else:
        criteria = filter_level  # Assume it's a custom criteria dict
    
    print(f"   Using {filter_level} filter criteria: {criteria}")
    
    filtered_locations = filter_obj.filter_changes(img1, img2, locations, criteria)
    
    # Step 4: Save results
    print("4. Saving filtered results...")
    
    if filtered_locations['bounding_boxes']:
        extractor.visualize_locations(img1, filtered_locations, f'filtered_{filter_level}.jpg')
        extractor.export_to_json(filtered_locations, f'filtered_{filter_level}.json')
        
        print(f"   Saved: filtered_{filter_level}.jpg and filtered_{filter_level}.json")
        
        print(f"\n=== FINAL RESULTS ===")
        print(f"Filtered changes: {len(filtered_locations['bounding_boxes'])}")
        for bbox in filtered_locations['bounding_boxes']:
            print(f"  Change at ({bbox['x']}, {bbox['y']}) size {bbox['width']}×{bbox['height']}")
    else:
        print("   All changes were filtered out - try 'loose' filter level")
    
    return filtered_locations

def compare_filter_levels(img1_path, img2_path):
    """Compare results from different filter levels."""
    
    print("=== COMPARING FILTER LEVELS ===\n")
    
    # Detect changes once
    detector = MultiScaleImageDiff()
    extractor = ClusteredChangeExtractor(min_area=20)
    
    diff_map, img1, img2 = detector.detect_from_files(img1_path, img2_path)
    locations = extractor.extract_clustered_locations(
        diff_map, threshold=0.1, clustering_method='morphological'
    )
    
    original_count = len(locations['bounding_boxes'])
    print(f"Original detections: {original_count}")
    
    if original_count == 0:
        print("No changes detected!")
        return
    
    # Test different filter levels
    filter_obj = AutoChangeFilter()
    filter_levels = {
        'loose': filter_obj.get_loose_criteria(),
        'default': filter_obj.get_default_criteria(),
        'strict': filter_obj.get_strict_criteria()
    }
    
    results = {}
    
    for level_name, criteria in filter_levels.items():
        print(f"\n--- {level_name.upper()} FILTERING ---")
        filtered = filter_obj.filter_changes(img1, img2, locations, criteria)
        results[level_name] = filtered
        
        # Save visualization
        if filtered['bounding_boxes']:
            extractor.visualize_locations(img1, filtered, f'compare_{level_name}.jpg')
    
    # Summary
    print(f"\n=== COMPARISON SUMMARY ===")
    print(f"Original: {original_count} changes")
    for level_name, result in results.items():
        count = len(result['bounding_boxes'])
        percentage = (count / original_count * 100) if original_count > 0 else 0
        print(f"{level_name.capitalize()}: {count} changes ({percentage:.1f}% kept)")
    
    return results

if __name__ == "__main__":
    # Example usage
    img1_path = 'anne.png'  # Replace with your paths
    img2_path = 'anne_bling.png'
    
    try:
        # Quick filtering with default settings
        filtered_changes = quick_filter_workflow(img1_path, img2_path, filter_level='default')
        
        # Uncomment to compare different filter levels:
        # compare_filter_levels(img1_path, img2_path)
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your image paths are correct!")