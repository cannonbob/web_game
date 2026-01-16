import cv2
import numpy as np
from skimage import measure, morphology
import json
import pandas as pd
from typing import List, Dict, Tuple, Union

class ChangeLocationExtractor:
    """Extract precise locations of image changes from difference maps."""
    
    def __init__(self, min_area=5, connectivity=2):
        """
        Initialize the location extractor.
        
        Args:
            min_area: Minimum area (in pixels) for a change region to be considered
            connectivity: Connectivity for connected component analysis (1 for 4-conn, 2 for 8-conn)
        """
        self.min_area = min_area
        self.connectivity = connectivity  # skimage uses 1 or 2 (not 4 or 8)
    
    def extract_locations(self, difference_map, threshold=0.1, output_format='all'):
        """
        Extract change locations from a difference map.
        
        Args:
            difference_map: 2D numpy array with difference values (0-1 range)
            threshold: Threshold for considering a pixel as changed
            output_format: 'pixels', 'bboxes', 'contours', 'centroids', or 'all'
        
        Returns:
            Dictionary containing requested location information
        """
        # Create binary mask from difference map
        binary_mask = (difference_map > threshold).astype(np.uint8)
        
        # Apply morphological operations to clean up small noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
        
        results = {}
        
        if output_format in ['pixels', 'all']:
            results['pixels'] = self._extract_pixel_coordinates(binary_mask)
        
        if output_format in ['bboxes', 'all']:
            results['bounding_boxes'] = self._extract_bounding_boxes(binary_mask)
        
        if output_format in ['contours', 'all']:
            results['contours'] = self._extract_contours(binary_mask)
        
        if output_format in ['centroids', 'all']:
            results['centroids'] = self._extract_centroids(binary_mask)
        
        if output_format in ['regions', 'all']:
            results['regions'] = self._extract_regions(binary_mask)
        
        return results
    
    def _extract_pixel_coordinates(self, binary_mask):
        """Extract all changed pixel coordinates."""
        y_coords, x_coords = np.where(binary_mask > 0)
        pixels = [{'x': int(x), 'y': int(y)} for x, y in zip(x_coords, y_coords)]
        return pixels
    
    def _extract_bounding_boxes(self, binary_mask):
        """Extract bounding boxes around change regions."""
        # Find connected components
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        
        bounding_boxes = []
        for i, region in enumerate(regions):
            if region.area >= self.min_area:
                minr, minc, maxr, maxc = region.bbox
                bbox = {
                    'id': i,
                    'x': int(minc),
                    'y': int(minr),
                    'width': int(maxc - minc),
                    'height': int(maxr - minr),
                    'area': int(region.area),
                    'center_x': int(region.centroid[1]),
                    'center_y': int(region.centroid[0])
                }
                bounding_boxes.append(bbox)
        
        return bounding_boxes
    
    def _extract_contours(self, binary_mask):
        """Extract contour points for each change region."""
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        contour_data = []
        for i, contour in enumerate(contours):
            if cv2.contourArea(contour) >= self.min_area:
                # Simplify contour to reduce number of points
                epsilon = 0.02 * cv2.arcLength(contour, True)
                simplified_contour = cv2.approxPolyDP(contour, epsilon, True)
                
                points = [{'x': int(point[0][0]), 'y': int(point[0][1])} 
                         for point in simplified_contour]
                
                contour_info = {
                    'id': i,
                    'points': points,
                    'area': float(cv2.contourArea(contour)),
                    'perimeter': float(cv2.arcLength(contour, True))
                }
                contour_data.append(contour_info)
        
        return contour_data
    
    def _extract_centroids(self, binary_mask):
        """Extract centroids of change regions."""
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        
        centroids = []
        for i, region in enumerate(regions):
            if region.area >= self.min_area:
                centroid = {
                    'id': i,
                    'x': float(region.centroid[1]),
                    'y': float(region.centroid[0]),
                    'area': int(region.area)
                }
                centroids.append(centroid)
        
        return centroids
    
    def _extract_regions(self, binary_mask):
        """Extract detailed region properties."""
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        
        region_data = []
        for i, region in enumerate(regions):
            if region.area >= self.min_area:
                minr, minc, maxr, maxc = region.bbox
                
                region_info = {
                    'id': i,
                    'area': int(region.area),
                    'perimeter': float(region.perimeter),
                    'eccentricity': float(region.eccentricity),
                    'solidity': float(region.solidity),
                    'extent': float(region.extent),
                    'orientation': float(region.orientation),
                    'major_axis_length': float(region.major_axis_length),
                    'minor_axis_length': float(region.minor_axis_length),
                    'centroid': {
                        'x': float(region.centroid[1]),
                        'y': float(region.centroid[0])
                    },
                    'bbox': {
                        'x': int(minc),
                        'y': int(minr),
                        'width': int(maxc - minc),
                        'height': int(maxr - minr)
                    }
                }
                region_data.append(region_info)
        
        return region_data
    
    def export_to_json(self, locations, filename):
        """Export location data to JSON file."""
        with open(filename, 'w') as f:
            json.dump(locations, f, indent=2)
        print(f"Locations exported to {filename}")
    
    def export_to_csv(self, locations, filename):
        """Export bounding boxes to CSV file."""
        if 'bounding_boxes' in locations:
            df = pd.DataFrame(locations['bounding_boxes'])
            df.to_csv(filename, index=False)
            print(f"Bounding boxes exported to {filename}")
        else:
            print("No bounding boxes found in locations data")
    
    def visualize_locations(self, original_image, locations, save_path=None):
        """Visualize detected change locations on the original image."""
        vis_image = original_image.copy()
        
        # Draw bounding boxes
        if 'bounding_boxes' in locations:
            for bbox in locations['bounding_boxes']:
                cv2.rectangle(vis_image, 
                            (bbox['x'], bbox['y']), 
                            (bbox['x'] + bbox['width'], bbox['y'] + bbox['height']), 
                            (0, 255, 0), 2)
                
                # Add label
                label = f"ID:{bbox['id']} ({bbox['width']}x{bbox['height']})"
                cv2.putText(vis_image, label, 
                          (bbox['x'], bbox['y'] - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Draw centroids
        if 'centroids' in locations:
            for centroid in locations['centroids']:
                cv2.circle(vis_image, 
                         (int(centroid['x']), int(centroid['y'])), 
                         5, (255, 0, 0), -1)
        
        # Draw contours
        if 'contours' in locations:
            for contour_data in locations['contours']:
                points = np.array([[p['x'], p['y']] for p in contour_data['points']], 
                                dtype=np.int32)
                cv2.polylines(vis_image, [points], True, (0, 0, 255), 2)
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
            print(f"Visualization saved to {save_path}")
        
        return vis_image

# Integration with MultiScaleImageDiff
class IntegratedChangeDetector:
    """Combined change detection and location extraction."""
    
    def __init__(self):
        from your_previous_code import MultiScaleImageDiff  # Import your detector
        self.detector = MultiScaleImageDiff()
        self.extractor = ChangeLocationExtractor()
    
    def detect_and_locate(self, img1_path, img2_path, method='multiscale', 
                         threshold=0.1, output_formats=['bboxes', 'centroids']):
        """
        Complete pipeline: detect changes and extract their locations.
        
        Args:
            img1_path, img2_path: Image file paths
            method: Detection method ('multiscale', 'adaptive', etc.)
            threshold: Threshold for location extraction
            output_formats: List of desired output formats
        
        Returns:
            Dictionary with detection results and locations
        """
        # Load images
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        
        # Detect differences
        if method == 'multiscale':
            diff_map = self.detector.multiscale_difference(img1, img2)
        elif method == 'adaptive':
            diff_map = self.detector.adaptive_threshold_difference(img1, img2)
        elif method == 'structural':
            diff_map = self.detector.structural_similarity_difference(img1, img2)
        elif method == 'gradient':
            diff_map = self.detector.gradient_based_difference(img1, img2)
        
        # Extract locations
        locations = {}
        for fmt in output_formats:
            locations.update(self.extractor.extract_locations(diff_map, threshold, fmt))
        
        # Create visualization
        vis_image = self.extractor.visualize_locations(img1, locations)
        
        return {
            'difference_map': diff_map,
            'locations': locations,
            'visualization': vis_image,
            'summary': self._create_summary(locations)
        }
    
    def _create_summary(self, locations):
        """Create a summary of detected changes."""
        summary = {
            'total_regions': 0,
            'total_changed_pixels': 0,
            'largest_change_area': 0,
            'average_change_area': 0
        }
        
        if 'bounding_boxes' in locations:
            bboxes = locations['bounding_boxes']
            summary['total_regions'] = len(bboxes)
            
            if bboxes:
                areas = [bbox['area'] for bbox in bboxes]
                summary['total_changed_pixels'] = sum(areas)
                summary['largest_change_area'] = max(areas)
                summary['average_change_area'] = sum(areas) / len(areas)
        
        return summary

# Example usage functions
def example_basic_usage():
    """Basic example of extracting change locations."""
    
    # Assuming you have a difference map from your detector
    # diff_map = your_detector.multiscale_difference(img1, img2)
    
    extractor = ChangeLocationExtractor(min_area=10)
    
    # Extract all types of location data
    # locations = extractor.extract_locations(diff_map, threshold=0.1)
    
    # Or extract specific types
    # bboxes_only = extractor.extract_locations(diff_map, threshold=0.1, output_format='bboxes')
    
    print("Example usage:")
    print("1. extractor = ChangeLocationExtractor(min_area=10)")
    print("2. locations = extractor.extract_locations(diff_map, threshold=0.1)")
    print("3. extractor.export_to_json(locations, 'changes.json')")
    print("4. extractor.export_to_csv(locations, 'changes.csv')")

def example_complete_pipeline():
    """Example of complete detection and location extraction pipeline."""
    
    print("\nComplete Pipeline Example:")
    print("detector = IntegratedChangeDetector()")
    print("results = detector.detect_and_locate('img1.jpg', 'img2.jpg')")
    print("print('Found', results['summary']['total_regions'], 'change regions')")
    print()
    print("# Access specific location data:")
    print("bounding_boxes = results['locations']['bounding_boxes']")
    print("centroids = results['locations']['centroids']")
    print()
    print("# Export results:")
    print("with open('change_report.json', 'w') as f:")
    print("    json.dump(results['locations'], f, indent=2)")

def create_location_report(locations):
    """Create a detailed text report of change locations."""
    
    report = "=== CHANGE DETECTION REPORT ===\n\n"
    
    if 'bounding_boxes' in locations:
        bboxes = locations['bounding_boxes']
        report += f"Total Change Regions: {len(bboxes)}\n\n"
        
        for i, bbox in enumerate(bboxes):
            report += f"Region {i+1}:\n"
            report += f"  Location: ({bbox['x']}, {bbox['y']})\n"
            report += f"  Size: {bbox['width']} × {bbox['height']} pixels\n"
            report += f"  Area: {bbox['area']} pixels\n"
            report += f"  Center: ({bbox['center_x']}, {bbox['center_y']})\n\n"
    
    if 'regions' in locations:
        regions = locations['regions']
        report += "Detailed Region Properties:\n"
        for region in regions:
            report += f"  Region {region['id']}: "
            report += f"Eccentricity={region['eccentricity']:.3f}, "
            report += f"Solidity={region['solidity']:.3f}\n"
    
    return report

# Utility functions for different coordinate formats
def convert_to_opencv_format(bboxes):
    """Convert bounding boxes to OpenCV rectangle format."""
    opencv_rects = []
    for bbox in bboxes:
        rect = (bbox['x'], bbox['y'], bbox['width'], bbox['height'])
        opencv_rects.append(rect)
    return opencv_rects

def convert_to_yolo_format(bboxes, image_width, image_height):
    """Convert bounding boxes to YOLO format (normalized coordinates)."""
    yolo_boxes = []
    for bbox in bboxes:
        # Convert to YOLO format: (center_x, center_y, width, height) normalized
        center_x = (bbox['x'] + bbox['width'] / 2) / image_width
        center_y = (bbox['y'] + bbox['height'] / 2) / image_height
        norm_width = bbox['width'] / image_width
        norm_height = bbox['height'] / image_height
        
        yolo_boxes.append([center_x, center_y, norm_width, norm_height])
    
    return yolo_boxes

def filter_changes_by_size(locations, min_area=None, max_area=None):
    """Filter change locations by area criteria."""
    if 'bounding_boxes' not in locations:
        return locations
    
    filtered_bboxes = []
    for bbox in locations['bounding_boxes']:
        if min_area and bbox['area'] < min_area:
            continue
        if max_area and bbox['area'] > max_area:
            continue
        filtered_bboxes.append(bbox)
    
    locations['bounding_boxes'] = filtered_bboxes
    return locations

if __name__ == "__main__":
    example_basic_usage()
    example_complete_pipeline()
    
    # Example of creating a location report
    print("\n" + "="*50)
    print("SAMPLE OUTPUT FORMATS:")
    print("="*50)
    
    sample_locations = {
        'bounding_boxes': [
            {'id': 0, 'x': 100, 'y': 50, 'width': 80, 'height': 60, 'area': 4800, 'center_x': 140, 'center_y': 80},
            {'id': 1, 'x': 300, 'y': 200, 'width': 25, 'height': 30, 'area': 750, 'center_x': 312, 'center_y': 215}
        ]
    }
    
    print(create_location_report(sample_locations))