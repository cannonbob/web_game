"""
Manual change reviewer - interactively approve or reject detected changes.

This tool shows you each detected change and lets you decide if it's a real change or false positive.
"""

import cv2
import numpy as np
import json
from detector import MultiScaleImageDiff
from extractor import ClusteredChangeExtractor

class ManualChangeReviewer:
    """Interactive tool for manually reviewing detected changes."""
    
    def __init__(self):
        self.approved_changes = []
        self.rejected_changes = []
        self.current_index = 0
        
    def review_changes(self, img1, img2, locations, window_size=(800, 600)):
        """
        Interactively review each detected change.
        
        Args:
            img1, img2: Original images
            locations: Dictionary with detected bounding boxes
            window_size: Size of review window
        
        Returns:
            Dictionary with approved changes only
        """
        if 'bounding_boxes' not in locations or len(locations['bounding_boxes']) == 0:
            print("No changes to review!")
            return {'bounding_boxes': [], 'summary': {'total_regions': 0}}
        
        bboxes = locations['bounding_boxes']
        total_changes = len(bboxes)
        
        print(f"\n=== MANUAL CHANGE REVIEW ===")
        print(f"Found {total_changes} changes to review")
        print(f"Controls:")
        print(f"  'a' or SPACE = Approve this change")
        print(f"  'r' or 'd' = Reject this change") 
        print(f"  'n' = Next (skip for now)")
        print(f"  'p' = Previous")
        print(f"  'q' = Quit and save results")
        print(f"  's' = Show statistics")
        print(f"  'h' = Show help")
        print(f"\nStarting review...\n")
        self.current_index = 0
        
        while self.current_index < total_changes:
            bbox = bboxes[self.current_index]
            
            # Create review image
            review_img = self._create_review_image(img1, img2, bbox, self.current_index, total_changes)
            
            # Show the image
            cv2.imshow('Change Review - Press h for help', review_img)
            
            # Wait for user input
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('a') or key == ord(' '):  # Approve
                self._approve_change(bbox)
                self.current_index += 1
                
            elif key == ord('r') or key == ord('d'):  # Reject
                self._reject_change(bbox)
                self.current_index += 1
                
            elif key == ord('n'):  # Next (skip)
                self.current_index += 1
                
            elif key == ord('p'):  # Previous
                self.current_index = max(0, self.current_index - 1)
                
            elif key == ord('s'):  # Statistics
                self._show_statistics(total_changes)
                
            elif key == ord('h'):  # Help
                self._show_help()
                
            elif key == ord('q') or key == 27:  # Quit (q or ESC)
                break
        
        cv2.destroyAllWindows()
        
        # Create final results
        approved_locations = {
            'bounding_boxes': self.approved_changes,
            'rejected_boxes': self.rejected_changes,
            'summary': self._calculate_final_summary()
        }
        
        print(f"\n=== REVIEW COMPLETE ===")
        print(f"Approved: {len(self.approved_changes)} changes")
        print(f"Rejected: {len(self.rejected_changes)} changes")
        print(f"Skipped: {total_changes - len(self.approved_changes) - len(self.rejected_changes)} changes")
        
        return approved_locations
    
    def _create_review_image(self, img1, img2, bbox, current_idx, total_changes):
        """Create a review image showing the change in context."""
        
        # Extract region with padding
        padding = 50
        x1 = max(0, bbox['x'] - padding)
        y1 = max(0, bbox['y'] - padding)
        x2 = min(img1.shape[1], bbox['x'] + bbox['width'] + padding)
        y2 = min(img1.shape[0], bbox['y'] + bbox['height'] + padding)
        
        # Extract regions from both images
        region1 = img1[y1:y2, x1:x2].copy()
        region2 = img2[y1:y2, x1:x2].copy()
        
        # Adjust bbox coordinates for cropped region
        adj_bbox = {
            'x': bbox['x'] - x1,
            'y': bbox['y'] - y1,
            'width': bbox['width'],
            'height': bbox['height']
        }
        
        # Draw bounding box on both regions
        cv2.rectangle(region1, 
                     (adj_bbox['x'], adj_bbox['y']), 
                     (adj_bbox['x'] + adj_bbox['width'], adj_bbox['y'] + adj_bbox['height']), 
                     (0, 255, 0), 3)
        
        cv2.rectangle(region2, 
                     (adj_bbox['x'], adj_bbox['y']), 
                     (adj_bbox['x'] + adj_bbox['width'], adj_bbox['y'] + adj_bbox['height']), 
                     (0, 255, 0), 3)
        
        # Resize regions for display
        max_height = 400
        if region1.shape[0] > max_height:
            scale = max_height / region1.shape[0]
            new_width = int(region1.shape[1] * scale)
            region1 = cv2.resize(region1, (new_width, max_height))
            region2 = cv2.resize(region2, (new_width, max_height))
        
        # Create side-by-side comparison
        comparison = np.hstack([region1, region2])
        
        # Add text labels
        label_height = 60
        text_area = np.zeros((label_height, comparison.shape[1], 3), dtype=np.uint8)
        
        # Add labels
        cv2.putText(text_area, "ORIGINAL", (10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(text_area, "MODIFIED", (region1.shape[1] + 10, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Add progress and change info
        progress = f"Change {current_idx + 1}/{total_changes}"
        change_info = f"Size: {bbox['width']}x{bbox['height']}, Area: {bbox['area']} pixels"
        status = f"Approved: {len(self.approved_changes)}, Rejected: {len(self.rejected_changes)}"
        
        cv2.putText(text_area, progress, (10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(text_area, change_info, (200, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        cv2.putText(text_area, status, (region1.shape[1] + 10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Create instruction area
        instruction_height = 80
        instruction_area = np.zeros((instruction_height, comparison.shape[1], 3), dtype=np.uint8)
        instructions = [
            "Controls: [A]pprove  [R]eject  [N]ext  [P]revious  [Q]uit  [S]tats  [H]elp",
            "Look at the green box - is this a real change you want to keep?"
        ]
        
        for i, instruction in enumerate(instructions):
            cv2.putText(instruction_area, instruction, (10, 25 + i * 25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Combine all parts
        final_image = np.vstack([text_area, comparison, instruction_area])
        
        return final_image
    
    def _approve_change(self, bbox):
        """Approve a change."""
        if bbox not in self.approved_changes:
            self.approved_changes.append(bbox)
            print(f"✓ Approved change {bbox['id']} at ({bbox['x']}, {bbox['y']})")
    
    def _reject_change(self, bbox):
        """Reject a change."""
        if bbox not in self.rejected_changes:
            self.rejected_changes.append(bbox)
            print(f"✗ Rejected change {bbox['id']} at ({bbox['x']}, {bbox['y']})")
    
    def _show_statistics(self, total_changes):
        """Show current review statistics."""
        reviewed = len(self.approved_changes) + len(self.rejected_changes)
        remaining = total_changes - reviewed
        
        print(f"\n=== CURRENT STATISTICS ===")
        print(f"Total changes: {total_changes}")
        print(f"Reviewed: {reviewed}")
        print(f"Approved: {len(self.approved_changes)}")
        print(f"Rejected: {len(self.rejected_changes)}")
        print(f"Remaining: {remaining}")
        
        if self.approved_changes:
            approved_areas = [bbox['area'] for bbox in self.approved_changes]
            print(f"Approved changes area range: {min(approved_areas)} - {max(approved_areas)} pixels")
        
        print("Press any key to continue...")
    
    def _show_help(self):
        """Show help information."""
        print(f"\n=== HELP ===")
        print(f"You are reviewing detected image changes to filter out false positives.")
        print(f"Look at the green box in both images:")
        print(f"- If you see a real, meaningful change → Press 'A' to APPROVE")
        print(f"- If it's just noise, compression artifacts, or not important → Press 'R' to REJECT")
        print(f"- If you're unsure → Press 'N' to skip for now")
        print(f"")
        print(f"Navigation:")
        print(f"  A/SPACE = Approve and move to next")
        print(f"  R/D = Reject and move to next")
        print(f"  N = Skip to next without deciding")
        print(f"  P = Go back to previous")
        print(f"  S = Show statistics")
        print(f"  Q/ESC = Quit and save current results")
        print(f"")
        print(f"Tips:")
        print(f"- Small changes (< 100 pixels) are often false positives")
        print(f"- Look for actual content differences, not just lighting/compression")
        print(f"- You can always run this again with different settings")
        print(f"")
        print("Press any key to continue...")
    
    def _calculate_final_summary(self):
        """Calculate summary statistics for approved changes."""
        if not self.approved_changes:
            return {
                'total_regions': 0,
                'total_changed_pixels': 0,
                'largest_change_area': 0,
                'average_change_area': 0
            }
        
        areas = [bbox['area'] for bbox in self.approved_changes]
        return {
            'total_regions': len(self.approved_changes),
            'total_changed_pixels': sum(areas),
            'largest_change_area': max(areas),
            'average_change_area': sum(areas) / len(areas),
            'rejected_count': len(self.rejected_changes)
        }

def auto_filter_by_size(locations, min_area=100, max_area=50000):
    """
    Automatically filter out changes that are too small or too large.
    
    Args:
        locations: Dictionary with bounding boxes
        min_area: Minimum area to keep (pixels)
        max_area: Maximum area to keep (pixels)
    
    Returns:
        Filtered locations dictionary
    """
    if 'bounding_boxes' not in locations:
        return locations
    
    original_count = len(locations['bounding_boxes'])
    
    filtered_boxes = []
    for bbox in locations['bounding_boxes']:
        if min_area <= bbox['area'] <= max_area:
            filtered_boxes.append(bbox)
    
    print(f"Auto-filter by size: {original_count} → {len(filtered_boxes)} changes")
    print(f"Removed {original_count - len(filtered_boxes)} changes outside range {min_area}-{max_area} pixels")
    
    # Update locations
    locations['bounding_boxes'] = filtered_boxes
    extractor = ClusteredChangeExtractor()
    locations['summary'] = extractor._calculate_summary(filtered_boxes)
    
    return locations

def complete_review_workflow(img1_path, img2_path, auto_filter=True):
    """
    Complete workflow: detect, cluster, auto-filter, then manual review.
    
    Args:
        img1_path, img2_path: Image file paths
        auto_filter: Whether to apply automatic size filtering first
    
    Returns:
        Final approved locations
    """
    print("=== COMPLETE REVIEW WORKFLOW ===\n")
    
    # Step 1: Detect changes
    print("1. Detecting changes...")
    detector = MultiScaleImageDiff()
    extractor = ClusteredChangeExtractor(min_area=20)  # Lower threshold for initial detection
    
    diff_map, img1, img2 = detector.detect_from_files(img1_path, img2_path)
    
    # Step 2: Extract and cluster
    print("2. Extracting and clustering changes...")
    locations = extractor.extract_clustered_locations(
        diff_map, 
        threshold=0.08,  # Lower threshold to catch more changes
        clustering_method='morphological',
        cluster_kernel_size=20
    )
    
    initial_count = len(locations['bounding_boxes'])
    print(f"   Found {initial_count} potential changes")
    
    if initial_count == 0:
        print("No changes detected!")
        return {'bounding_boxes': [], 'summary': {'total_regions': 0}}
    
    # Step 3: Auto-filter (optional)
    if auto_filter:
        print("3. Auto-filtering by size...")
        locations = auto_filter_by_size(locations, min_area=50, max_area=20000)
        
        if len(locations['bounding_boxes']) == 0:
            print("All changes filtered out by auto-filter!")
            return locations
    
    # Step 4: Manual review
    print("4. Starting manual review...")
    reviewer = ManualChangeReviewer()
    approved_locations = reviewer.review_changes(img1, img2, locations)
    
    # Step 5: Save results
    print("5. Saving results...")
    
    # Save approved changes
    extractor.export_to_json(approved_locations, 'approved_changes.json')
    
    # Create visualization with only approved changes
    if approved_locations['bounding_boxes']:
        extractor.visualize_locations(img1, approved_locations, 'approved_changes.jpg')
        print("   Saved: approved_changes.json and approved_changes.jpg")
    else:
        print("   No changes approved - no files saved")
    
    return approved_locations

if __name__ == "__main__":
    # Example usage
    img1_path = 'anne.png'  # Replace with your paths
    img2_path = 'anne_bling.png'
    
    try:
        approved_changes = complete_review_workflow(img1_path, img2_path, auto_filter=True)
        
        print(f"\n=== FINAL RESULTS ===")
        if approved_changes['bounding_boxes']:
            print(f"Final approved changes: {len(approved_changes['bounding_boxes'])}")
            for bbox in approved_changes['bounding_boxes']:
                print(f"  Change at ({bbox['x']}, {bbox['y']}) size {bbox['width']}×{bbox['height']}")
        else:
            print("No changes were approved.")
            
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your image paths are correct!")