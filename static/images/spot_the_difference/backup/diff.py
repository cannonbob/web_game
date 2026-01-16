# Use the integrated detector that handles everything
from change_location_extractor import IntegratedChangeDetector

detector = IntegratedChangeDetector()
results = detector.detect_and_locate('original_image.jpg', 'modified_image.jpg', 
                                   method='multiscale', threshold=0.1)

# Access the locations directly
bboxes = results['locations']['bounding_boxes']
print(f"Found {len(bboxes)} change regions")

# Export results
detector.extractor.export_to_json(results['locations'], 'change_locations.json')