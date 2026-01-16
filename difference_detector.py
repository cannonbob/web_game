import cv2
import numpy as np
import json
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class DifferenceDetector:
    def __init__(self, sensitivity=40, min_cluster_size=50, cluster_distance=50):
        self.sensitivity = sensitivity
        self.min_cluster_size = min_cluster_size
        self.cluster_distance = cluster_distance
    
    def detect_differences(self, image1_path, image2_path, method='hybrid'):
        """
        Detect differences between two images
        Returns list of difference regions with coordinates and radius
        """
        # Load images
        img1 = cv2.imread(str(image1_path))
        img2 = cv2.imread(str(image2_path))
        
        if img1 is None or img2 is None:
            raise ValueError("Could not load one or both images")
        
        # Ensure same dimensions
        if img1.shape != img2.shape:
            print(f"Resizing images to match: {img1.shape}")
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
        
        print(f"Processing images: {img1.shape[1]}x{img1.shape[0]} pixels")
        
        # Choose detection method
        if method == 'fast':
            difference_points = self._fast_detection(img1, img2)
        elif method == 'accurate':
            difference_points = self._accurate_detection(img1, img2)
        else:  # hybrid (default)
            difference_points = self._hybrid_detection(img1, img2)
        
        print(f"Found {len(difference_points)} difference points")
        
        # Cluster nearby points into regions
        regions = self._cluster_differences(difference_points)
        
        print(f"Clustered into {len(regions)} regions")
        return regions, img1, img2
    
    def _fast_detection(self, img1, img2):
        """Fast detection using larger grid scanning"""
        points = []
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        # Adaptive grid size based on image size
        grid_size = max(20, min(img1.shape[0], img1.shape[1]) // 50)
        threshold = self.sensitivity * 1.5
        
        print(f"Using grid size: {grid_size}px")
        
        h, w = gray1.shape
        for y in range(0, h - grid_size, grid_size // 2):
            for x in range(0, w - grid_size, grid_size // 2):
                region1 = gray1[y:y+grid_size, x:x+grid_size]
                region2 = gray2[y:y+grid_size, x:x+grid_size]
                
                diff = np.abs(region1.astype(int) - region2.astype(int))
                avg_diff = np.mean(diff)
                
                if avg_diff > threshold:
                    # Find the most different point in this region
                    max_pos = np.unravel_index(np.argmax(diff), diff.shape)
                    points.append({
                        'x': x + max_pos[1],
                        'y': y + max_pos[0],
                        'intensity': avg_diff
                    })
        
        return points
    
    def _accurate_detection(self, img1, img2):
        """Accurate detection using computer vision techniques"""
        points = []
        
        # Convert to LAB color space for better perceptual difference
        lab1 = cv2.cvtColor(img1, cv2.COLOR_BGR2LAB)
        lab2 = cv2.cvtColor(img2, cv2.COLOR_BGR2LAB)
        
        # Calculate difference
        diff = cv2.absdiff(lab1, lab2)
        
        # Convert to grayscale for processing
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_LAB2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray_diff, (5, 5), 0)
        
        # Threshold to find significant differences
        _, thresh = cv2.threshold(blurred, self.sensitivity, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        print(f"Found {len(contours)} contours")
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 5:  # Minimum area
                # Get center of contour
                M = cv2.moments(contour)
                if M['m00'] != 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    
                    # Calculate intensity at this point
                    if 0 <= cy < gray_diff.shape[0] and 0 <= cx < gray_diff.shape[1]:
                        intensity = float(gray_diff[cy, cx])
                        
                        points.append({
                            'x': cx,
                            'y': cy,
                            'intensity': intensity,
                            'area': area
                        })
        
        return points
    
    def _hybrid_detection(self, img1, img2):
        """Combine multiple detection methods"""
        print("Running hybrid detection...")
        
        # Get points from both methods
        fast_points = self._fast_detection(img1, img2)
        print(f"Fast detection: {len(fast_points)} points")
        
        accurate_points = self._accurate_detection(img1, img2)
        print(f"Accurate detection: {len(accurate_points)} points")
        
        # Combine and deduplicate
        all_points = fast_points + accurate_points
        return self._remove_duplicate_points(all_points, 20)
    
    def _remove_duplicate_points(self, points, threshold):
        """Remove duplicate points within threshold distance"""
        if not points:
            return []
        
        filtered = []
        for point in points:
            is_duplicate = False
            for existing in filtered:
                distance = np.sqrt((point['x'] - existing['x'])**2 + (point['y'] - existing['y'])**2)
                if distance < threshold:
                    # Keep the stronger point
                    if point['intensity'] > existing['intensity']:
                        existing.update(point)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered.append(point)
        
        print(f"After deduplication: {len(filtered)} points")
        return filtered
    
    def _cluster_differences(self, points):
        """Group nearby difference points into clickable regions"""
        if not points:
            return []
        
        regions = []
        used = set()
        
        for i, point in enumerate(points):
            if i in used:
                continue
            
            # Start new cluster
            cluster = [point]
            used.add(i)
            
            # Find nearby points
            for j, other_point in enumerate(points):
                if j in used:
                    continue
                
                distance = np.sqrt((point['x'] - other_point['x'])**2 + 
                                 (point['y'] - other_point['y'])**2)
                
                if distance <= self.cluster_distance:
                    cluster.append(other_point)
                    used.add(j)
            
            # Calculate cluster center and radius
            center_x = sum(p['x'] for p in cluster) / len(cluster)
            center_y = sum(p['y'] for p in cluster) / len(cluster)
            
            # Calculate radius (max distance from center + buffer)
            max_dist = max(np.sqrt((p['x'] - center_x)**2 + (p['y'] - center_y)**2) 
                          for p in cluster)
            radius = max(25, max_dist + 15)  # Minimum 25px radius
            
            total_intensity = sum(p['intensity'] for p in cluster)
            avg_intensity = total_intensity / len(cluster)
            
            # Only keep meaningful regions
            if len(cluster) >= 2 or avg_intensity > self.sensitivity * 1.5:
                regions.append({
                    'centerX': round(center_x, 1),
                    'centerY': round(center_y, 1),
                    'radius': round(radius, 1),
                    'point_count': len(cluster),
                    'avg_intensity': round(avg_intensity, 1)
                })
        
        # Sort by intensity (strongest differences first)
        regions.sort(key=lambda r: r['avg_intensity'], reverse=True)
        return regions

def show_results(original_path, modified_path, differences, img1, img2):
    """Show a comprehensive view of the detection results"""
    
    # Convert BGR to RGB for matplotlib
    img1_rgb = cv2.cvtColor(img1, cv2.COLOR_BGR2RGB)
    img2_rgb = cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)
    
    # Create figure with multiple subplots
    fig = plt.figure(figsize=(20, 12))
    
    # Original image
    ax1 = plt.subplot(2, 3, 1)
    ax1.imshow(img1_rgb)
    ax1.set_title('Original Image', fontsize=14, fontweight='bold')
    ax1.axis('off')
    
    # Modified image with differences marked
    ax2 = plt.subplot(2, 3, 2)
    ax2.imshow(img2_rgb)
    ax2.set_title(f'Modified Image\n({len(differences)} differences found)', fontsize=14, fontweight='bold')
    ax2.axis('off')
    
    # Draw circles around differences
    for i, diff in enumerate(differences):
        circle = patches.Circle(
            (diff['centerX'], diff['centerY']), 
            diff['radius'],
            linewidth=3, 
            edgecolor='red', 
            facecolor='none',
            alpha=0.8
        )
        ax2.add_patch(circle)
        
        # Add number label
        ax2.text(diff['centerX'], diff['centerY'], str(i+1), 
                ha='center', va='center', color='red', fontweight='bold', fontsize=12,
                bbox=dict(boxstyle="circle,pad=0.1", facecolor='white', alpha=0.8))
    
    # Side-by-side comparison
    ax3 = plt.subplot(2, 3, (3, 6))
    combined = np.hstack([img1_rgb, img2_rgb])
    ax3.imshow(combined)
    ax3.set_title('Side-by-Side Comparison', fontsize=14, fontweight='bold')
    ax3.axis('off')
    
    # Add vertical line to separate images
    ax3.axvline(x=img1_rgb.shape[1], color='white', linewidth=3)
    
    # Difference heatmap
    ax4 = plt.subplot(2, 3, 4)
    diff_img = cv2.absdiff(img1, img2)
    diff_gray = cv2.cvtColor(diff_img, cv2.COLOR_BGR2GRAY)
    heatmap = ax4.imshow(diff_gray, cmap='hot')
    ax4.set_title('Difference Heatmap', fontsize=14, fontweight='bold')
    ax4.axis('off')
    plt.colorbar(heatmap, ax=ax4, shrink=0.6)
    
    # Statistics
    ax5 = plt.subplot(2, 3, 5)
    ax5.axis('off')
    
    stats_text = f"""
DETECTION RESULTS

Total Differences: {len(differences)}

Difficulty Analysis:
• Very Easy (radius > 40px): {sum(1 for d in differences if d['radius'] > 40)}
• Easy (radius 30-40px): {sum(1 for d in differences if 30 <= d['radius'] <= 40)}
• Medium (radius 20-30px): {sum(1 for d in differences if 20 <= d['radius'] < 30)}
• Hard (radius < 20px): {sum(1 for d in differences if d['radius'] < 20)}

Average radius: {np.mean([d['radius'] for d in differences]):.1f}px
Average intensity: {np.mean([d['avg_intensity'] for d in differences]):.1f}

Top 5 Strongest Differences:
"""
    
    for i, diff in enumerate(differences[:5]):
        stats_text += f"{i+1}. Center: ({diff['centerX']:.0f}, {diff['centerY']:.0f}), "
        stats_text += f"Radius: {diff['radius']:.0f}px, Intensity: {diff['avg_intensity']:.1f}\n"
    
    ax5.text(0.05, 0.95, stats_text, transform=ax5.transAxes, fontsize=11,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle="round,pad=0.5", facecolor='lightgray', alpha=0.8))
    
    plt.tight_layout()
    plt.show()

def export_results(differences, original_path, modified_path, output_file):
    """Export results to JSON file for use in game"""
    output_data = {
        'game_name': Path(original_path).stem,
        'original_image': str(original_path),
        'modified_image': str(modified_path),
        'image_info': {
            'created_at': str(Path(original_path).stat().st_mtime),
            'total_differences': len(differences)
        },
        'differences': differences,
        'game_config': {
            'difficulty': 'auto',
            'time_limit': None,
            'hints_allowed': 3
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"Results exported to: {output_file}")
    print(f"File size: {Path(output_file).stat().st_size} bytes")

def main():
    parser = argparse.ArgumentParser(description='Detect differences between two images')
    parser.add_argument('original', help='Path to original image')
    parser.add_argument('modified', help='Path to modified image') 
    parser.add_argument('--output', '-o', help='Output JSON file path')
    parser.add_argument('--method', choices=['fast', 'accurate', 'hybrid'], 
                       default='hybrid', help='Detection method (default: hybrid)')
    parser.add_argument('--sensitivity', '-s', type=int, default=40, 
                       help='Detection sensitivity 10-100 (default: 40)')
    parser.add_argument('--cluster-distance', '-c', type=int, default=50,
                       help='Maximum distance to cluster points (default: 50)')
    parser.add_argument('--no-preview', action='store_true',
                       help='Skip showing the preview window')
    parser.add_argument('--list-only', action='store_true',
                       help='Only print the coordinates, no visualization')
    
    args = parser.parse_args()
    
    # Validate input files
    if not Path(args.original).exists():
        print(f"Error: Original image '{args.original}' not found")
        return
    
    if not Path(args.modified).exists():
        print(f"Error: Modified image '{args.modified}' not found")
        return
    
    # Initialize detector
    detector = DifferenceDetector(
        sensitivity=args.sensitivity,
        cluster_distance=args.cluster_distance
    )
    
    print(f"Analyzing differences between:")
    print(f"  Original: {args.original}")
    print(f"  Modified: {args.modified}")
    print(f"  Method: {args.method}")
    print(f"  Sensitivity: {args.sensitivity}")
    print("-" * 50)
    
    try:
        # Detect differences
        differences, img1, img2 = detector.detect_differences(args.original, args.modified, args.method)
        
        if not differences:
            print("❌ No differences found!")
            print("Try:")
            print("  • Lowering sensitivity (--sensitivity 20)")
            print("  • Using 'accurate' method (--method accurate)")
            print("  • Checking if images are actually different")
            return
        
        print(f"✅ Found {len(differences)} difference regions!")
        
        # List results
        if args.list_only:
            print("\nDifference coordinates:")
            for i, diff in enumerate(differences):
                print(f"{i+1:2d}. Center: ({diff['centerX']:6.1f}, {diff['centerY']:6.1f}) "
                      f"Radius: {diff['radius']:4.1f}px  "
                      f"Intensity: {diff['avg_intensity']:5.1f}")
        else:
            # Show visual results
            if not args.no_preview:
                show_results(args.original, args.modified, differences, img1, img2)
        
        # Export to JSON if requested
        if args.output:
            export_results(differences, args.original, args.modified, args.output)
        else:
            # Auto-generate output filename
            output_file = f"{Path(args.original).stem}_differences.json"
            export_results(differences, args.original, args.modified, output_file)
        
        print(f"\n🎮 Game ready!")
        print(f"   • {len(differences)} differences to find")
        print(f"   • Average difficulty: {np.mean([d['radius'] for d in differences]):.1f}px radius")
        print(f"   • Estimated play time: {len(differences) * 30}s - {len(differences) * 60}s")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return

if __name__ == '__main__':
    main()