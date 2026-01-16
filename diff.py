import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import math
import os

class DifferenceMarker:
    def __init__(self, root):
        self.root = root
        self.root.title("Spot the Difference - Coordinate Marker")
        self.root.geometry("1200x800")
        
        # Variables
        self.image = None
        self.photo = None
        self.canvas_width = 800
        self.canvas_height = 600
        self.current_tool = "rectangle"
        self.drawing = False
        self.start_x = 0
        self.start_y = 0
        self.current_shape = None
        self.shapes = []
        self.shape_counter = 1
        self.image_file = ""
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel for controls
        control_frame = ttk.Frame(main_frame, width=300)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        control_frame.pack_propagate(False)
        
        # Image controls
        ttk.Label(control_frame, text="Image Controls", font=("Arial", 12, "bold")).pack(pady=(0, 10))
        ttk.Button(control_frame, text="Load Image", command=self.load_image).pack(fill=tk.X, pady=2)
        
        # Tool selection
        ttk.Label(control_frame, text="Shape Tools", font=("Arial", 12, "bold")).pack(pady=(20, 10))
        
        self.tool_var = tk.StringVar(value="rectangle")
        ttk.Radiobutton(control_frame, text="Rectangle", variable=self.tool_var, 
                       value="rectangle", command=self.change_tool).pack(anchor=tk.W)
        ttk.Radiobutton(control_frame, text="Circle", variable=self.tool_var, 
                       value="circle", command=self.change_tool).pack(anchor=tk.W)
        ttk.Radiobutton(control_frame, text="Ellipse", variable=self.tool_var, 
                       value="ellipse", command=self.change_tool).pack(anchor=tk.W)
        
        # Shape list
        ttk.Label(control_frame, text="Marked Differences", font=("Arial", 12, "bold")).pack(pady=(20, 10))
        
        # Listbox frame with scrollbar
        list_frame = ttk.Frame(control_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.shape_listbox = tk.Listbox(list_frame, height=10)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.shape_listbox.yview)
        self.shape_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.shape_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Shape controls
        ttk.Button(control_frame, text="Delete Selected", command=self.delete_shape).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="Clear All", command=self.clear_all).pack(fill=tk.X, pady=2)
        
        # File operations
        ttk.Label(control_frame, text="File Operations", font=("Arial", 12, "bold")).pack(pady=(20, 10))
        ttk.Button(control_frame, text="Save Coordinates", command=self.save_coordinates).pack(fill=tk.X, pady=2)
        ttk.Button(control_frame, text="Load Coordinates", command=self.load_coordinates).pack(fill=tk.X, pady=2)
        
        # Canvas frame
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Canvas with scrollbars
        self.canvas = tk.Canvas(canvas_frame, bg="white", width=self.canvas_width, height=self.canvas_height)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
        
        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Bind events
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw_motion)
        self.canvas.bind("<ButtonRelease-1>", self.end_draw)
        
    def change_tool(self):
        self.current_tool = self.tool_var.get()
        
    def load_image(self):
        file_path = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff")]
        )
        
        if file_path:
            try:
                self.image = Image.open(file_path)
                self.image_file = os.path.basename(file_path)
                
                # Resize image if too large while maintaining aspect ratio
                max_size = (1000, 800)
                self.image.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                self.photo = ImageTk.PhotoImage(self.image)
                
                # Update canvas size to image size
                self.canvas.configure(scrollregion=(0, 0, self.image.width, self.image.height))
                
                # Clear canvas and display image
                self.canvas.delete("all")
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
                
                # Clear existing shapes
                self.shapes = []
                self.update_shape_list()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {str(e)}")
    
    def start_draw(self, event):
        if not self.image:
            messagebox.showwarning("Warning", "Please load an image first!")
            return
            
        self.drawing = True
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        
        # Create temporary shape for visual feedback
        if self.current_tool == "rectangle":
            self.current_shape = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline="red", width=2, fill="", stipple="gray25"
            )
        elif self.current_tool in ["circle", "ellipse"]:
            self.current_shape = self.canvas.create_oval(
                self.start_x, self.start_y, self.start_x, self.start_y,
                outline="red", width=2, fill="", stipple="gray25"
            )
    
    def draw_motion(self, event):
        if not self.drawing or not self.current_shape:
            return
            
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        
        if self.current_tool == "rectangle":
            self.canvas.coords(self.current_shape, self.start_x, self.start_y, current_x, current_y)
        elif self.current_tool == "circle":
            # Calculate radius and create square (circle)
            radius = math.sqrt((current_x - self.start_x)**2 + (current_y - self.start_y)**2)
            self.canvas.coords(self.current_shape, 
                             self.start_x - radius, self.start_y - radius,
                             self.start_x + radius, self.start_y + radius)
        elif self.current_tool == "ellipse":
            self.canvas.coords(self.current_shape, self.start_x, self.start_y, current_x, current_y)
    
    def end_draw(self, event):
        if not self.drawing or not self.current_shape:
            return
            
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        
        # Calculate final coordinates based on tool
        shape_data = {
            "id": self.shape_counter,
            "shape": self.current_tool
        }
        
        if self.current_tool == "rectangle":
            shape_data["coordinates"] = {
                "x1": min(self.start_x, current_x),
                "y1": min(self.start_y, current_y),
                "x2": max(self.start_x, current_x),
                "y2": max(self.start_y, current_y)
            }
        elif self.current_tool == "circle":
            radius = math.sqrt((current_x - self.start_x)**2 + (current_y - self.start_y)**2)
            shape_data["coordinates"] = {
                "center_x": self.start_x,
                "center_y": self.start_y,
                "radius": radius
            }
        elif self.current_tool == "ellipse":
            center_x = (self.start_x + current_x) / 2
            center_y = (self.start_y + current_y) / 2
            radius_x = abs(current_x - self.start_x) / 2
            radius_y = abs(current_y - self.start_y) / 2
            shape_data["coordinates"] = {
                "center_x": center_x,
                "center_y": center_y,
                "radius_x": radius_x,
                "radius_y": radius_y,
                "rotation": 0
            }
        
        # Only add if shape has meaningful size
        if self.is_valid_shape(shape_data):
            self.shapes.append(shape_data)
            self.shape_counter += 1
            self.update_shape_list()
        else:
            # Remove the temporary shape if too small
            self.canvas.delete(self.current_shape)
        
        self.drawing = False
        self.current_shape = None
    
    def is_valid_shape(self, shape_data):
        coords = shape_data["coordinates"]
        if shape_data["shape"] == "rectangle":
            return abs(coords["x2"] - coords["x1"]) > 5 and abs(coords["y2"] - coords["y1"]) > 5
        elif shape_data["shape"] == "circle":
            return coords["radius"] > 5
        elif shape_data["shape"] == "ellipse":
            return coords["radius_x"] > 5 and coords["radius_y"] > 5
        return False
    
    def update_shape_list(self):
        self.shape_listbox.delete(0, tk.END)
        for shape in self.shapes:
            shape_str = f"#{shape['id']} - {shape['shape'].capitalize()}"
            self.shape_listbox.insert(tk.END, shape_str)
    
    def delete_shape(self):
        selection = self.shape_listbox.curselection()
        if selection:
            index = selection[0]
            deleted_shape = self.shapes.pop(index)
            
            # Find and remove the canvas item
            # This is a simplified approach - in a more complex app you'd track canvas items
            self.redraw_all_shapes()
            self.update_shape_list()
    
    def clear_all(self):
        self.shapes = []
        self.redraw_all_shapes()
        self.update_shape_list()
        self.shape_counter = 1
    
    def redraw_all_shapes(self):
        # Clear all shapes and redraw
        if self.image:
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            
            # Redraw all shapes
            for shape in self.shapes:
                self.draw_shape_on_canvas(shape)
    
    def draw_shape_on_canvas(self, shape_data):
        coords = shape_data["coordinates"]
        
        if shape_data["shape"] == "rectangle":
            self.canvas.create_rectangle(
                coords["x1"], coords["y1"], coords["x2"], coords["y2"],
                outline="red", width=2, fill="", stipple="gray25"
            )
        elif shape_data["shape"] == "circle":
            r = coords["radius"]
            self.canvas.create_oval(
                coords["center_x"] - r, coords["center_y"] - r,
                coords["center_x"] + r, coords["center_y"] + r,
                outline="red", width=2, fill="", stipple="gray25"
            )
        elif shape_data["shape"] == "ellipse":
            self.canvas.create_oval(
                coords["center_x"] - coords["radius_x"], coords["center_y"] - coords["radius_y"],
                coords["center_x"] + coords["radius_x"], coords["center_y"] + coords["radius_y"],
                outline="red", width=2, fill="", stipple="gray25"
            )
    
    def save_coordinates(self):
        if not self.shapes:
            messagebox.showwarning("Warning", "No shapes to save!")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="Save Coordinates",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        
        if file_path:
            try:
                data = {
                    "image_file": self.image_file,
                    "image_dimensions": {
                        "width": self.image.width if self.image else 0,
                        "height": self.image.height if self.image else 0
                    },
                    "differences": self.shapes
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                    
                messagebox.showinfo("Success", f"Coordinates saved to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save coordinates: {str(e)}")
    
    def load_coordinates(self):
        file_path = filedialog.askopenfilename(
            title="Load Coordinates",
            filetypes=[("JSON files", "*.json")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                self.shapes = data.get("differences", [])
                
                # Update shape counter
                if self.shapes:
                    self.shape_counter = max(shape["id"] for shape in self.shapes) + 1
                else:
                    self.shape_counter = 1
                
                self.redraw_all_shapes()
                self.update_shape_list()
                
                messagebox.showinfo("Success", f"Loaded {len(self.shapes)} shapes from {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load coordinates: {str(e)}")

def main():
    root = tk.Tk()
    app = DifferenceMarker(root)
    root.mainloop()

if __name__ == "__main__":
    main()