import os
import mysql.connector

# --- Database Configuration ---
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',        # change if needed
    'password': 'Jayesh@45',        # change if needed
    'database': 'signease'
}

# --- Folder containing sign images ---
SIGN_FOLDER = r"C:\Users\chaud\OneDrive\Desktop\Ishario (2)\Ishario\Ishario\static\signs"

# --- Connect to database ---
conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

# --- Fetch existing sign names ---
cursor.execute("SELECT sign_name FROM sign_images")
existing_signs = {row[0] for row in cursor.fetchall()}

# --- Iterate over files in folder ---
for filename in os.listdir(SIGN_FOLDER):
    file_path = os.path.join(SIGN_FOLDER, filename)
    
    # Skip if not an image or already present
    if not os.path.isfile(file_path):
        continue
    sign_name = os.path.splitext(filename)[0]  # remove file extension

    if sign_name in existing_signs:
        print(f"⚠️ Skipping existing sign: {sign_name}")
        continue

    # --- Read image in binary mode ---
    with open(file_path, 'rb') as file:
        image_data = file.read()

    # --- Insert new sign ---
    cursor.execute(
        "INSERT INTO sign_images (sign_name, image_data) VALUES (%s, %s)",
        (sign_name, image_data)
    )
    print(f"✅ Added new sign: {sign_name}")

# --- Commit changes and close ---
conn.commit()
cursor.close()
conn.close()

print("\n🎯 Done updating sign_images table!")
