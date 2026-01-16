import cv2
import numpy as np
from skimage import measure, morphology
from sklearn.cluster import DBSCAN
from scipy.spatial.distance import pdist, squareform
import json

class ClusteredChangeExtractor:
    """Enhanced change location extractor with clustering capabilities."""
    
    def __init__(self, min_area=10, connectivity=2, clustering_method='morphological'):
        """
        Initialize the clustered extractor.
        
        Args:
            min_area: Minimum area for a change region
            connectivity: Connectivity for connected components (1 or 2)
            clustering_method: 'morphological', 'distance', 'dbscan', or 'hierarchical'
        """
        self.min_area = min_area
        self.connectivity = connectivity
        self.clustering_method = clustering_method
    
    def extract_clustered_locations(self, difference_map, threshold=0.1, 
                                  cluster_distance=50, min_cluster_size=2,
                                  dilation_kernel_size=15):
        """
        Extract and cluster change locations.
        
        Args:
            difference_map: 2D difference array
            threshold: Threshold for change detection
            cluster_distance: Maximum distance for clustering nearby changes
            min_cluster_size: Minimum number of regions to form a cluster
            dilation_kernel_size: Size of morphological dilation kernel
        
        Returns:
            Dictionary with clustered locations
        """
        print(f"Processing difference map with shape: {difference_map.shape}")
        print(f"Using clustering method: {self.clustering_method}")
        
        # Create binary mask
        binary_mask = (difference_map > threshold).astype(np.uint8)
        print(f"Initial changed pixels: {np.sum(binary_mask)}")
        
        if self.clustering_method == 'morphological':
            clustered_mask = self._morphological_clustering(binary_mask, dilation_kernel_size)
        elif self.clustering_method == 'distance':
            return self._distance_based_clustering(binary_mask, cluster_distance)
        elif self.clustering_method == 'dbscan':
            return self._dbscan_clustering(binary_mask, cluster_distance, min_cluster_size)
        elif self.clustering_method == 'hierarchical':
            return self._hierarchical_clustering(binary_mask, cluster_distance)
        else:
            clustered_mask = binary_mask
        
        # Extract regions from clustered mask
        return self._extract_regions_from_mask(clustered_mask)
    
    def _morphological_clustering(self, binary_mask, kernel_size):
        """Use morphological operations to connect nearby changes."""
        print(f"Applying morphological clustering with kernel size {kernel_size}")
        
        # First, clean up noise with opening
        small_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, small_kernel)
        
        # Then dilate to connect nearby regions
        large_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, 
                                               (kernel_size, kernel_size))
        dilated_mask = cv2.dilate(cleaned_mask, large_kernel, iterations=1)
        
        # Fill holes in the dilated regions
        filled_mask = self._fill_holes(dilated_mask)
        
        print(f"After morphological clustering: {np.sum(filled_mask)} pixels in clustered regions")
        return filled_mask
    
    def _distance_based_clustering(self, binary_mask, max_distance):
        """Cluster bounding boxes based on distance between centers."""
        # First get individual regions
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        
        # Filter by minimum area
        regions = [r for r in regions if r.area >= self.min_area]
        
        if len(regions) == 0:
            return {'bounding_boxes': [], 'clusters': []}
        
        # Extract centroids
        centroids = np.array([list(region.centroid[::-1]) for region in regions])  # (x, y)
        
        # Calculate distance matrix
        if len(centroids) > 1:
            distances = squareform(pdist(centroids))
            
            # Group regions that are close together
            clusters = []
            visited = set()
            
            for i, region in enumerate(regions):
                if i in visited:
                    continue
                
                # Find all regions within max_distance
                cluster_indices = [i]
                visited.add(i)
                
                for j in range(len(regions)):
                    if j != i and j not in visited and distances[i, j] <= max_distance:
                        cluster_indices.append(j)
                        visited.add(j)
                
                # Create cluster bounding box
                cluster_regions = [regions[idx] for idx in cluster_indices]
                cluster_bbox = self._merge_regions(cluster_regions)
                clusters.append({
                    'cluster_id': len(clusters),
                    'region_count': len(cluster_indices),
                    'regions': cluster_indices,
                    'bbox': cluster_bbox
                })
        else:
            # Single region
            region = regions[0]
            bbox = self._region_to_bbox(region, 0)
            clusters = [{'cluster_id': 0, 'region_count': 1, 'regions': [0], 'bbox': bbox}]
        
        return {'bounding_boxes': [cluster['bbox'] for cluster in clusters], 'clusters': clusters}
    
    def _dbscan_clustering(self, binary_mask, eps, min_samples):
        """Use DBSCAN clustering on region centroids."""
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        regions = [r for r in regions if r.area >= self.min_area]
        
        if len(regions) == 0:
            return {'bounding_boxes': [], 'clusters': []}
        
        # Extract centroids
        centroids = np.array([list(region.centroid[::-1]) for region in regions])
        
        # Apply DBSCAN
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(centroids)
        labels = clustering.labels_
        
        # Group regions by cluster
        clusters = []
        unique_labels = set(labels)
        
        for label in unique_labels:
            if label == -1:  # Noise points
                continue
            
            cluster_indices = [i for i, l in enumerate(labels) if l == label]
            cluster_regions = [regions[idx] for idx in cluster_indices]
            cluster_bbox = self._merge_regions(cluster_regions)
            
            clusters.append({
                'cluster_id': len(clusters),
                'region_count': len(cluster_indices),
                'regions': cluster_indices,
                'bbox': cluster_bbox
            })
        
        return {'bounding_boxes': [cluster['bbox'] for cluster in clusters], 'clusters': clusters}
    
    def _hierarchical_clustering(self, binary_mask, max_distance):
        """Simple hierarchical clustering by iteratively merging closest regions."""
        labeled_image = measure.label(binary_mask, connectivity=self.connectivity)
        regions = list(measure.regionprops(labeled_image))
        regions = [r for r in regions if r.area >= self.min_area]
        
        if len(regions) == 0:
            return {'bounding_boxes': [], 'clusters': []}
        
        # Convert regions to bounding boxes
        bboxes = [self._region_to_bbox(region, i) for i, region in enumerate(regions)]
        
        # Iteratively merge closest bboxes
        while True:
            if len(bboxes) <= 1:
                break
            
            min_distance = float('inf')
            merge_pair = None
            
            # Find closest pair
            for i in range(len(bboxes)):
                for j in range(i + 1, len(bboxes)):
                    dist = self._bbox_distance(bboxes[i], bboxes[j])
                    if dist < min_distance:
                        min_distance = dist
                        merge_pair = (i, j)
            
            # If closest pair is too far, stop merging
            if min_distance > max_distance:
                break
            
            # Merge the closest pair
            i, j = merge_pair
            merged_bbox = self._merge_bboxes(bboxes[i], bboxes[j])
            
            # Remove old bboxes and add merged one
            bboxes = [bbox for k, bbox in enumerate(bboxes) if k not in [i, j]]
            bboxes.append(merged_bbox)
        
        return {'bounding_boxes': bboxes, 'clusters': []}
    
    def _extract_regions_from_mask(self, mask):
        """Extract bounding boxes from a binary mask."""
        labeled_image = measure.label(mask, connectivity=self.connectivity)
        regions = measure.regionprops(labeled_image)
        
        bounding_boxes = []
        for i, region in enumerate(regions):
            if region.area >= self.min_area:
                bbox = self._region_to_bbox(region, i)
                bounding_boxes.append(bbox)
        
        print(f"Final result: {len(bounding_boxes)} clustered regions")
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
    
    def _merge_regions(self, regions):
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
            'id': 0,
            'x': int(min_c),
            'y': int(min_r),
            'width': int(max_c - min_c),
            'height': int(max_r - min_r),
            'area': int(total_area),
            'center_x': int(avg_x),
            'center_y': int(avg_y)
        }
    
    def _merge_bboxes(self, bbox1, bbox2):
        """Merge two bounding boxes."""
        min_x = min(bbox1['x'], bbox2['x'])
        min_y = min(bbox1['y'], bbox2['y'])
        max_x = max(bbox1['x'] + bbox1['width'], bbox2['x'] + bbox2['width'])
        max_y = max(bbox1['y'] + bbox1['height'], bbox2['y'] + bbox2['height'])
        
        return {
            'id': 0,
            'x': min_x,
            'y': min_y,
            'width': max_x - min_x,
            'height': max_y - min_y,
            'area': bbox1['area'] + bbox2['area'],
            'center_x': (bbox1['center_x'] + bbox2['center_x']) // 2,
            'center_y': (bbox1['center_y'] + bbox2['center_y']) // 2
        }
    
    def _bbox_distance(self, bbox1, bbox2):
        """Calculate distance between two bounding box centers."""
        dx = bbox1['center_x'] - bbox2['center_x']
        dy = bbox1['center_y'] - bbox2['center_y']
        return np.sqrt(dx * dx + dy * dy)
    
    def _fill_holes(self, binary_image):
        """Fill holes in binary image."""
        # Copy the image
        filled = binary_image.copy()
        
        # Find contours
        contours, _ = cv2.findContours(filled, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Fill contours
        cv2.fillPoly(filled, contours, 1)
        
        return filled
    
    def visualize_clustered_locations(self, original_image, locations, save_path=None):
        """Visualize clustered change locations."""
        vis_image = original_image.copy()
        
        if 'bounding_boxes' in locations:
            for i, bbox in enumerate(locations['bounding_boxes']):
                # Use different colors for different clusters
                colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), 
                         (255, 0, 255), (0, 255, 255), (128, 128, 128)]
                color = colors[i % len(colors)]
                
                # Draw bounding box
                cv2.rectangle(vis_image, 
                            (bbox['x'], bbox['y']), 
                            (bbox['x'] + bbox['width'], bbox['y'] + bbox['height']), 
                            color, 3)
                
                # Add label
                label = f"Cluster {bbox['id']} ({bbox['width']}x{bbox['height']})"
                cv2.putText(vis_image, label, 
                          (bbox['x'], bbox['y'] - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Draw center point
                cv2.circle(vis_image, 
                         (bbox['center_x'], bbox['center_y']), 
                         8, color, -1)
        
        if save_path:
            cv2.imwrite(save_path, vis_image)
            print(f"Clustered visualization saved to {save_path}")
        
        return vis_image

# Example usage with different clustering methods
def compare_clustering_methods(img1, img2, difference_map):
    """Compare different clustering methods."""
    
    methods = {
        'morphological': {'dilation_kernel_size': 20},
        'distance': {'cluster_distance': 50},
        'dbscan': {'cluster_distance': 30, 'min_cluster_size': 2},
        'hierarchical': {'cluster_distance': 60}
    }
    
    results = {}
    
    for method_name, params in methods.items():
        print(f"\n--- Testing {method_name.upper()} clustering ---")
        
        extractor = ClusteredChangeExtractor(
            min_area=20, 
            connectivity=2, 
            clustering_method=method_name
        )
        
        if method_name == 'morphological':
            locations = extractor.extract_clustered_locations(
                difference_map, threshold=0.1, 
                dilation_kernel_size=params['dilation_kernel_size']
            )
        else:
            locations = extractor.extract_clustered_locations(
                difference_map, threshold=0.1,
                cluster_distance=params['cluster_distance'],
                min_cluster_size=params.get('min_cluster_size', 2)
            )
        
        results[method_name] = locations
        
        if 'bounding_boxes' in locations:
            print(f"Found {len(locations['bounding_boxes'])} clustered regions")
            for bbox in locations['bounding_boxes']:
                print(f"  Region {bbox['id']}: ({bbox['x']}, {bbox['y']}) "
                      f"{bbox['width']}×{bbox['height']} area={bbox['area']}")
        
        # Save visualization
        vis_image = extractor.visualize_clustered_locations(
            img1, locations, f'clustered_{method_name}.jpg'
        )
    
    return results

# Main function for testing
def main_with_clustering():
    """Main function demonstrating clustering capabilities."""
    
    print("=== Clustered Change Detection ===\n")
    
    # Load images (replace paths)
    img1_path = 'test_original.jpg'
    img2_path = 'test_modified.jpg'
    
    try:
        img1 = cv2.imread(img1_path)
        img2 = cv2.imread(img2_path)
        
        if img1 is None or img2 is None:
            print("Creating synthetic test images...")
            img1, img2 = create_complex_test_images()
        
        # Simple detector for testing
        from working_example import SimpleMultiScaleDetector
        detector = SimpleMultiScaleDetector()
        
        # Detect differences
        diff_map = detector.multiscale_difference(img1, img2)
        
        # Method 1: Morphological clustering (recommended for most cases)
        print("=== MORPHOLOGICAL CLUSTERING (Recommended) ===")
        extractor = ClusteredChangeExtractor(min_area=50, clustering_method='morphological')
        locations = extractor.extract_clustered_locations(
            diff_map, threshold=0.1, dilation_kernel_size=25
        )
        
        print(f"Morphological clustering found {len(locations['bounding_boxes'])} regions")
        extractor.visualize_clustered_locations(img1, locations, 'morphological_clusters.jpg')
        
        # Method 2: Distance-based clustering
        print("\n=== DISTANCE-BASED CLUSTERING ===")
        extractor2 = ClusteredChangeExtractor(min_area=20, clustering_method='distance')
        locations2 = extractor2.extract_clustered_locations(
            diff_map, threshold=0.1, cluster_distance=80
        )
        
        print(f"Distance clustering found {len(locations2['bounding_boxes'])} regions")
        extractor2.visualize_clustered_locations(img1, locations2, 'distance_clusters.jpg')
        
        # Export best results
        if len(locations['bounding_boxes']) > 0:
            with open('clustered_changes.json', 'w') as f:
                json.dump(locations, f, indent=2)
            print("\nResults saved to clustered_changes.json and visualization images")
        
        return locations
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def create_complex_test_images():
    """Create test images with scattered changes to demonstrate clustering."""
    img1 = np.ones((500, 700, 3), dtype=np.uint8) * 128
    
    # Add scattered small changes
    for i in range(15):
        x, y = np.random.randint(50, 650), np.random.randint(50, 450)
        size = np.random.randint(10, 30)
        color = tuple(np.random.randint(0, 255, 3).tolist())
        cv2.circle(img1, (x, y), size, color, -1)
    
    # Add some larger shapes
    cv2.rectangle(img1, (100, 100), (200, 200), (255, 100, 100), -1)
    cv2.rectangle(img1, (400, 300), (500, 400), (100, 255, 100), -1)
    
    # Create modified version with many small scattered changes
    img2 = img1.copy()
    
    # Remove some circles and add new ones nearby (to test clustering)
    for i in range(25):
        x, y = np.random.randint(50, 650), np.random.randint(50, 450)
        size = np.random.randint(5, 15)
        cv2.circle(img2, (x, y), size, (255, 255, 255), -1)
    
    # Modify the larger shapes
    cv2.rectangle(img2, (100, 100), (180, 180), (128, 128, 128), -1)
    cv2.rectangle(img2, (420, 320), (480, 380), (100, 100, 255), -1)
    
    cv2.imwrite('test_original.jpg', img1)
    cv2.imwrite('test_modified.jpg', img2)
    print("Created complex test images with scattered changes")
    
    return img1, img2

if __name__ == "__main__":
    main_with_clustering()