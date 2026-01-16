# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your game code
COPY . .

# Expose the port your game runs on (e.g., 5000)
EXPOSE 5000

# Command to run your game
CMD ["python", "app.py"]