"""
Simple coordinate extraction from manual review results.
This focuses on getting clean coordinate data without visualization.
"""

import json
import cv2
from review import ManualChangeReviewer

def review_for_coordinates_only(img1_path, img2_path, existing_json_path=None):
    """
    Get coordinates of approved changes without generating visualization images.
    
    Args:
        img1_path, img2_path: Image file paths
        existing_json_path: Optional path to existing detection results
    
    Returns:
        List of coordinate dictionaries for approved changes
    """
    
    if existing_json_path:
        print(f"Loading existing results from {existing_json_path}")
        locations = load_locations_from_json(existing_json_path)
    else:
        print("Running detection with original good parameters...")
        locations = detect_with_original_params(img1_path, img2_path)
    
    if not locations or len(locations.get('bounding_boxes', [])) == 0:
        print("No changes found to review!")
        return []
    
    print(f"Starting review of {len(locations['bounding_boxes'])} changes...")
    print("Focus: Getting coordinates only (no visualization files will be created)")
    
    # Load images for review
    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)
    
    if img1 is None or img2 is None:
        print("Error: Could not load images!")
        return []
    
    # Manual review
    reviewer = ManualChangeReviewer()
    approved_locations = reviewer.review_changes(img1, img2, locations)
    
    # Extract just the coordinates
    approved_coords = approved_locations.get('bounding_boxes', [])
    
    # Save coordinates to JSON (no visualization)
    output_data = {
        'approved_coordinates': approved_coords,
        'total_approved': len(approved_coords),
        'original_count': len(locations['bounding_boxes']),
        'rejection_count': len(approved_locations.get('rejected_boxes', [])),
        'image_paths': {
            'original': img1_path,
            'modified': img2_path
        }
    }
    
    with open('approved_coordinates.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n=== COORDINATE EXTRACTION COMPLETE ===")
    print(f"Approved changes: {len(approved_coords)}")
    print(f"Coordinates saved to: approved_coordinates.json")
    print(f"No visualization images created (as requested)")
    
    # Print coordinates for immediate use
    if approved_coords:
        print(f"\n=== APPROVED COORDINATES ===")
        for i, coord in enumerate(approved_coords):
            print(f"Change {i+1}: x={coord['x']}, y={coord['y']}, "
                  f"width={coord['width']}, height={coord['height']}, "
                  f"area={coord['area']}")
    
    return approved_coords

def load_locations_from_json(json_path):
    """Load detection results from JSON file."""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Handle different JSON formats
        if 'locations' in data:
            return data['locations']
        elif 'bounding_boxes' in data:
            return data
        else:
            print("Could not find bounding_boxes in JSON file")
            return None
            
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return None

def detect_with_original_params(img1_path, img2_path):
    """Run detection with the original good parameters."""
    from detector import MultiScaleImageDiff
    from extractor import ClusteredChangeExtractor
    
    # Original good parameters
    detector = MultiScaleImageDiff(blur_kernel=3, morph_kernel=3)
    extractor = ClusteredChangeExtractor(min_area=50, connectivity=2)
    
    diff_map, img1, img2 = detector.detect_from_files(img1_path, img2_path)
    
    locations = extractor.extract_clustered_locations(
        diff_map, 
        threshold=0.1,
        clustering_method='morphological',
        cluster_kernel_size=25
    )
    
    return locations

def extract_coordinates_from_json(json_path):
    """
    Extract just the coordinate arrays from a results JSON file.
    
    Args:
        json_path: Path to JSON file with detection results
        
    Returns:
        List of [x, y, width, height] coordinate arrays
    """
    locations = load_locations_from_json(json_path)
    
    if not locations or 'bounding_boxes' not in locations:
        print("No bounding boxes found in JSON")
        return []
    
    coordinates = []
    for bbox in locations['bounding_boxes']:
        coord_array = [bbox['x'], bbox['y'], bbox['width'], bbox['height']]
        coordinates.append(coord_array)
    
    print(f"Extracted {len(coordinates)} coordinate arrays:")
    for i, coord in enumerate(coordinates):
        print(f"  {i+1}: {coord}")
    
    return coordinates

def get_coordinate_summary(json_path):
    """
    Get a summary of coordinates from a results file.
    
    Args:
        json_path: Path to JSON file
        
    Returns:
        Dictionary with coordinate summary
    """
    locations = load_locations_from_json(json_path)
    
    if not locations or 'bounding_boxes' not in locations:
        return {'error': 'No bounding boxes found'}
    
    bboxes = locations['bounding_boxes']
    
    summary = {
        'total_changes': len(bboxes),
        'coordinates': [],
        'areas': [],
        'total_area': 0,
        'bounding_box_of_all_changes': None
    }
    
    if bboxes:
        # Extract coordinates and areas
        for bbox in bboxes:
            summary['coordinates'].append({
                'x': bbox['x'],
                'y': bbox['y'], 
                'width': bbox['width'],
                'height': bbox['height'],
                'area': bbox['area']
            })
            summary['areas'].append(bbox['area'])
        
        # Calculate total area
        summary['total_area'] = sum(summary['areas'])
        
        # Calculate overall bounding box containing all changes
        min_x = min(bbox['x'] for bbox in bboxes)
        min_y = min(bbox['y'] for bbox in bboxes)
        max_x = max(bbox['x'] + bbox['width'] for bbox in bboxes)
        max_y = max(bbox['y'] + bbox['height'] for bbox in bboxes)
        
        summary['bounding_box_of_all_changes'] = {
            'x': min_x,
            'y': min_y,
            'width': max_x - min_x,
            'height': max_y - min_y
        }
    
    return summary

def export_coordinates_csv(json_path, csv_path):
    """
    Export coordinates to CSV format.
    
    Args:
        json_path: Path to JSON results file
        csv_path: Output CSV file path
    """
    locations = load_locations_from_json(json_path)
    
    if not locations or 'bounding_boxes' not in locations:
        print("No bounding boxes to export")
        return
    
    import csv
    
    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['id', 'x', 'y', 'width', 'height', 'area', 'center_x', 'center_y']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for bbox in locations['bounding_boxes']:
            writer.writerow({
                'id': bbox['id'],
                'x': bbox['x'],
                'y': bbox['y'],
                'width': bbox['width'],
                'height': bbox['height'],
                'area': bbox['area'],
                'center_x': bbox['center_x'],
                'center_y': bbox['center_y']
            })
    
    print(f"Coordinates exported to {csv_path}")

if __name__ == "__main__":
    print("=== COORDINATE-ONLY EXTRACTION ===\n")
    
    print("Options:")
    print("1. Review existing JSON for coordinates only")
    print("2. Detect and review for coordinates only") 
    print("3. Extract coordinates from JSON (no review)")
    print("4. Get coordinate summary from JSON")
    print("5. Export JSON to CSV")
    
    choice = input("\nChoose option (1-5): ").strip() or '1'
    
    if choice == '1':
        # Review existing JSON
        json_path = input("Enter path to existing JSON results: ").strip()
        img1_path = input("Enter path to original image: ").strip()
        img2_path = input("Enter path to modified image: ").strip()
        
        coordinates = review_for_coordinates_only(img1_path, img2_path, json_path)
        
        if coordinates:
            print(f"\n=== READY TO USE COORDINATES ===")
            print("Use these coordinate values in your application:")
            for i, coord in enumerate(coordinates):
                print(f"change_{i+1} = [{coord['x']}, {coord['y']}, {coord['width']}, {coord['height']}]")
    
    elif choice == '2':
        # Detect and review
        img1_path = input("Enter path to original image: ").strip()
        img2_path = input("Enter path to modified image: ").strip()
        
        coordinates = review_for_coordinates_only(img1_path, img2_path)
        
    elif choice == '3':
        # Extract without review
        json_path = input("Enter path to JSON file: ").strip()
        coordinates = extract_coordinates_from_json(json_path)
        
    elif choice == '4':
        # Get summary
        json_path = input("Enter path to JSON file: ").strip()
        summary = get_coordinate_summary(json_path)
        
        print("\n=== COORDINATE SUMMARY ===")
        print(json.dumps(summary, indent=2))
        
    elif choice == '5':
        # Export to CSV
        json_path = input("Enter path to JSON file: ").strip()
        csv_path = input("Enter output CSV path: ").strip() or 'coordinates.csv'
        export_coordinates_csv(json_path, csv_path)
        
    print("\n=== DONE ===")