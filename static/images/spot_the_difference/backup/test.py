import cv2
from detector import MultiScaleImageDiff
from extractor import ChangeLocationExtractor

# Load the images first
img1 = cv2.imread('anne.png')
img2 = cv2.imread('anne_bling.png')

# Then use the loaded arrays
detector = MultiScaleImageDiff()
diff_map = detector.multiscale_difference(img1, img2)

# Extract locations
extractor = ChangeLocationExtractor(min_area=10, connectivity=2)
locations = extractor.extract_locations(diff_map, threshold=0.1, output_format='bboxes')

print(f"Found {len(locations['bounding_boxes'])} change regions")
for bbox in locations['bounding_boxes']:
    print(f"Change at ({bbox['x']}, {bbox['y']}) size {bbox['width']}x{bbox['height']}")