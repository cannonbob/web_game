import cv2
import numpy as np
from skimage import measure
import json

class ClusteredChangeExtractor:
    """Extract and cluster change locations from difference maps."""
    
    def __init__(self, min_area=20, connectivity=2):
        """
        Initialize the extractor.
        
        Args:
            min_area: Minimum area (pixels) for a change region
            connectivity: Connectivity for connected components (1=4-conn, 2=8-conn)
        """
        self.min_area = min_area
        self.connectivity = connectivity
    
    def extract_clustered_locations(self, difference_map, threshold=0.1, 
                                  clustering_method='morphological', 
                                  cluster_kernel_size=20, 
                                  cluster_distance=80):
        """
        Extract and cluster change locations.
        
        Args:
            difference_map: 2D difference array (0-1 values)
            threshold: Threshold for considering a pixel changed
            clustering_method: 'morphological' or 'distance'
            cluster_kernel_size: Size for morphological clustering
            cluster_distance: Max distance for distance-based clustering
        
        Returns:
            Dictionary with clustered locations
        """
        print(f"Processing difference map with shape: {difference_map.shape}")
        print(f"Difference range: {difference_map.min():.3f} to {difference_map.max():.3f}")
        
        # Create binary mask
        binary_mask = (difference_map > threshold).astype(np.uint8)
        initial_pixels = np.sum(binary_mask)
        print(f"Initial changed pixels: {initial_pixels}")
        
        if initial_pixels == 0:
            return {'bounding_boxes': [], 'summary': {'total_regions': 0}}
        
        # Apply clustering
        if clustering_method == 'morphological':
            clustered_mask = self._morphological_clustering(binary_mask, cluster_kernel_size)
            locations = self._extract_regions_from_mask(clustered_mask)
        elif clustering_method == 'distance':
            locations = self._distance_based_clustering(binary_mask, cluster_distance)
        else:
            # No clustering - just extract individual regions
            locations = self._extract_regions_from_mask(binary_mask)
        
        # Add summary statistics
        locations['summary'] = self._calculate_summary(locations['bounding_boxes'])
        
        return locations
    
    def _morphological_clustering(self, binary_mask, kernel_size):
        """Use morphological operations to connect nearby changes."""
        print(f"Applying morphological clustering with kernel size {kernel_size}")
        
        # Clean up small noise first
        small_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, small_kernel)
        
        # Dilate to connect nearby regions
        large_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                               (kernel_size, kernel_size))
        dilated_mask = cv2.dilate(cleaned_mask, large_kernel, iterations=1)
        
        # Fill holes in dilated regions
        filled_mask = self._fill_holes(dilated_mask)
        
        final_pixels = np.sum(filled_mask)
        print(f"After morphological clustering: {final_pixels} pixels in clustered regions")
        
        return filled_mask
    
    def _distance_based_clustering(self, binary_mask, max_distance):
        """Cluster regions based on distance between centers."""
        # Get individual regions first
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        regions = [r for r in regions if r.area >= self.min_area]
        
        if len(regions) == 0:
            return {'bounding_boxes': []}
        
        print(f"Found {len(regions)} initial regions for distance clustering")
        
        # Extract centroids
        centroids = np.array([list(region.centroid[::-1]) for region in regions])  # (x, y)
        
        # Group regions that are close together
        clusters = []
        assigned = set()
        
        for i, region in enumerate(regions):
            if i in assigned:
                continue
            
            # Find all regions within max_distance
            cluster_indices = [i]
            assigned.add(i)
            
            for j in range(len(regions)):
                if j != i and j not in assigned:
                    distance = np.sqrt(np.sum((centroids[i] - centroids[j]) ** 2))
                    if distance <= max_distance:
                        cluster_indices.append(j)
                        assigned.add(j)
            
            # Create cluster bounding box
            cluster_regions = [regions[idx] for idx in cluster_indices]
            cluster_bbox = self._merge_regions(cluster_regions, len(clusters))
            clusters.append(cluster_bbox)
        
        print(f"Distance clustering created {len(clusters)} clusters")
        return {'bounding_boxes': clusters}
    
    def _extract_regions_from_mask(self, mask):
        """Extract bounding boxes from a binary mask."""
        labeled_image = measure.label(mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        
        bounding_boxes = []
        for i, region in enumerate(regions):
            if region.area >= self.min_area:
                bbox = self._region_to_bbox(region, i)
                bounding_boxes.append(bbox)
        
        print(f"Extracted {len(bounding_boxes)} regions from mask")
        return {'bounding_boxes': bounding_boxes}
    
    def _region_to_bbox(self, region, region_id):
        """Convert a region to bounding box format."""
        minr, minc, maxr, maxc = region.bbox
        return {
            'id': region_id,
            'x': int(minc),
            'y': int(minr),
            'width': int(maxc - minc),
            'height': int(maxr - minr),
            'area': int(region.area),
            'center_x': int(region.centroid[1]),
            'center_y': int(region.centroid[0])
        }
    
    def _merge_regions(self, regions, cluster_id):
        """Merge multiple regions into a single bounding box."""
        if not regions:
            return None
        
        # Find overall bounding box
        min_r = min(region.bbox[0] for region in regions)
        min_c = min(region.bbox[1] for region in regions)
        max_r = max(region.bbox[2] for region in regions)
        max_c = max(region.bbox[3] for region in regions)
        
        total_area = sum(region.area for region in regions)
        
        # Calculate center as average of individual centroids
        avg_x = sum(region.centroid[1] for region in regions) / len(regions)
        avg_y = sum(region.centroid[0] for region in regions) / len(regions)
        
        return {
            'id': cluster_id,
            'x': int(min_c),
            'y': int(min_r),
            'width': int(max_c - min_c),
            'height': int(max_r - min_r),
            'area': int(total_area),
            'center_x': int(avg_x),
            'center_y': int(avg_y),
            'region_count': len(regions)
        }
    
    def _fill_holes(self, binary_image):
        """Fill holes in binary image using contour filling."""
        filled = binary_image.copy()
        contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.fillPoly(filled, contours, 1)
        return filled
    
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
    
    def visualize_locations(self, original_image, locations, save_path=None):
        """
        Create visualization with bounding boxes drawn on original image.
        
        Args:
            original_image: Original image array
            locations: Dictionary with bounding_boxes
            save_path: Optional path to save visualization
        
        Returns:
            Image with drawn bounding boxes
        """
        vis_image = original_image.copy()
        
        if 'bounding_boxes' not in locations:
            print("No bounding boxes found in locations")
            return vis_image
        
        # Colors for different regions
        colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), 
                 (255, 0, 255), (0, 255, 255), (128, 255, 128)]
        
        for i, bbox in enumerate(locations['bounding_boxes']):
            color = colors[i % len(colors)]
            
            # Draw bounding box
            cv2.rectangle(vis_image, 
                        (bbox['x'], bbox['y']), 
                        (bbox['x'] + bbox['width'], bbox['y'] + bbox['height']), 
                        color, 3)
            
            # Add label
            label = f"R{bbox['id']} ({bbox['width']}x{bbox['height']})"
            cv2.putText(vis_image, label, 
                      (bbox['x'], bbox['y'] - 10), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Draw center point
            cv2.circle(vis_image, 
                     (bbox['center_x'], bbox['center_y']), 
                     8, color, -1)
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
            print(f"Visualization saved to {save_path}")
        
        return vis_image
    
    def export_to_json(self, locations, filename):
        """Export location data to JSON file."""
        # Add timestamp and metadata
        export_data = {
            'timestamp': str(np.datetime64('now')),
            'extractor_settings': {
                'min_area': self.min_area,
                'connectivity': self.connectivity
            },
            'locations': locations
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        print(f"Locations exported to {filename}")
    
    def print_results(self, locations):
        """Print a summary of the results."""
        if 'bounding_boxes' not in locations:
            print("No results found")
            return
        
        bboxes = locations['bounding_boxes']
        summary = locations.get('summary', {})
        
        print(f"\n=== CHANGE DETECTION RESULTS ===")
        print(f"Total clustered regions: {len(bboxes)}")
        
        if summary:
            print(f"Total changed pixels: {summary.get('total_changed_pixels', 'N/A')}")
            print(f"Largest change area: {summary.get('largest_change_area', 'N/A')} pixels")
            print(f"Average change area: {summary.get('average_change_area', 'N/A'):.1f} pixels")
        
        print(f"\nDetailed regions:")
        for bbox in bboxes:
            region_count = bbox.get('region_count', 1)
            cluster_info = f" (merged from {region_count} regions)" if region_count > 1 else ""
            print(f"  Region {bbox['id']}: ({bbox['x']}, {bbox['y']}) "
                  f"size {bbox['width']}×{bbox['height']} "
                  f"area {bbox['area']} pixels{cluster_info}")