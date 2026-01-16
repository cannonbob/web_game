import cv2
from extractor2 import ClusteredChangeExtractor
import detector

# Your existing detection code
img1 = cv2.imread('anne.png')
img2 = cv2.imread('anne_bling.png')
diff_map = detector.multiscale_difference(img1, img2)

# NEW: Add clustering
extractor = ClusteredChangeExtractor(min_area=50, clustering_method='morphological')
locations = extractor.extract_clustered_locations(diff_map, threshold=0.1, dilation_kernel_size=20)

# Now you get fewer, more meaningful regions
print(f"Found {len(locations['bounding_boxes'])} clustered regions (instead of hundreds)")

for bbox in locations['bounding_boxes']:
    print(f"Change region: ({bbox['x']}, {bbox['y']}) size {bbox['width']}×{bbox['height']}")