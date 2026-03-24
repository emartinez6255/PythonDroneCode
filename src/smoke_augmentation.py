# Imports
import cv2
import numpy as np
import os

# Imports end

# Function to add smoke to our images 
def add_smoke(image, density = 0.5):
    # Create a random noise layer 
    noise = np.random.randint(0, 255, (image.shape[0], image.shape[1]), dtype = np.uint8)

    # Apply heavy blur to the noise to simulate thick fog/smoke
    blur_kernel = 51 # Tweak this value for "thicker" smoke
    smoke_layer = cv2.GaussianBlur(noise, (blur_kernel, blur_kernel), 0)

    # Merge the smoke layer with the original image 
    smoke_layer = cv2.cvtColor(smoke_layer, cv2.COLOR_GRAY2BGR)
    augmented_image = cv2.addWeighted(image, 1 - density, smoke_layer, density, 0)

    return augmented_image 

# Directories 
RAW_DIR = "data/raw"
PROC_DIR = "data/processed"

if not os.path.exists(PROC_DIR):
    os.makedirs(PROC_DIR)

# Process images
for filename in os.listdir(RAW_DIR):
    if filename.endswith((".png", "jpg", "jpeg")):
        img_path = os.path.join(RAW_DIR, filename)
        image = cv2.imread(img_path)

        # Generate 3 variations of smoke density for each image 

        for i in [0.3, 0.5, 0.7]:
            smoky_img = add_smoke(image, density = i)
            save_path = os.path.join(PROC_DIR, f"smoke_{i}_{filename}")
            cv2.imwrite(save_path, smoky_img)

print(f"Dataset augmentation complete. Check the {PROC_DIR} folder.")



