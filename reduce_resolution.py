from PIL import Image
import sys
import os
import math

# Resolution reduction steps (total pixel counts for each step)
# Step 4 is the most pixelated (128 total pixels)
PIXEL_COUNTS = [1024, 2048, 3072, 4096]  #[128, 256, 512, 1024] 
image_path = "C:/Users/Kai/Documents/Projekte/VS Code/web game v1/static/images/lists/pixel/vans.jpg"

def reduce_resolution(image_path):
    """
    Reduces image resolution in multiple steps with pixelated effect.
    Saves 4 versions with decreasing resolution based on total pixel counts.
    """
    try:
        # Open the original image
        img = Image.open(image_path)
        original_width, original_height = img.size
        aspect_ratio = original_width / original_height

        # Get the directory and filename
        directory = os.path.dirname(image_path)
        filename = os.path.basename(image_path)
        name, ext = os.path.splitext(filename)

        print(f"Original image: {filename} ({original_width}x{original_height})")
        print(f"Total pixels: {original_width * original_height}")
        print(f"Processing {len(PIXEL_COUNTS)} resolution steps...\n")

        # Create reduced resolution versions
        for i, pixel_count in enumerate(PIXEL_COUNTS, 1):
            # Calculate dimensions maintaining aspect ratio with target pixel count
            # width = aspect_ratio * height
            # width * height = pixel_count
            # So: height = sqrt(pixel_count / aspect_ratio)
            new_height = int(math.sqrt(pixel_count / aspect_ratio))
            new_width = int(aspect_ratio * new_height)

            # Downscale to reduced resolution, then upscale back to original size
            # This creates the pixelated effect while maintaining original dimensions
            reduced_img = img.resize((new_width, new_height), Image.NEAREST)
            pixelated_img = reduced_img.resize((original_width, original_height), Image.NEAREST)

            # Save with naming convention: [original]_1, [original]_2, etc.
            output_filename = f"{name}_{i}{ext}"
            output_path = os.path.join(directory, output_filename)
            pixelated_img.save(output_path)

            actual_pixels = new_width * new_height
            print(f"Step {i}: {output_filename} - {new_width}x{new_height} ({actual_pixels} pixels) -> {original_width}x{original_height}")

        print(f"\nAll {len(PIXEL_COUNTS)} images saved successfully!")

    except FileNotFoundError:
        print(f"Error: File '{image_path}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    reduce_resolution(image_path)
