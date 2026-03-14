#!/usr/bin/env python3
"""
Helper script to diagnose and fix the corrupted model.h5 file
"""

import os
import sys
import shutil
from pathlib import Path

def check_model_file():
    """Check if model.h5 exists and its status"""
    model_path = Path("model.h5")
    
    print("=" * 60)
    print("Model File Diagnostic Tool")
    print("=" * 60)
    
    if not model_path.exists():
        print("✗ model.h5 NOT FOUND")
        return False
    
    file_size = model_path.stat().st_size
    print(f"✓ model.h5 found")
    print(f"  File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
    
    # Check if it's a valid HDF5 file
    try:
        import h5py
        with h5py.File("model.h5", "r") as f:
            print(f"✓ Valid HDF5 file detected")
            print(f"  Contents: {list(f.keys())}")
            return True
    except Exception as e:
        print(f"✗ Invalid or corrupted HDF5 file: {e}")
        return False

def backup_model():
    """Create a backup of the corrupted model"""
    if os.path.exists("model.h5"):
        backup_path = "model.h5.bak"
        shutil.copy2("model.h5", backup_path)
        print(f"✓ Backup created: {backup_path}")

def suggest_fixes():
    """Provide suggestions to fix the issue"""
    print("\n" + "=" * 60)
    print("Recommended Solutions:")
    print("=" * 60)
    
    print("\nOption 1: Retrain the model (Recommended)")
    print("-" * 60)
    print("Run the following command:")
    print("  python train_model.py")
    print("\nThis will:")
    print("  - Load training data from the 'archive' directory")
    print("  - Train a new CNN model")
    print("  - Save to model.h5")
    
    print("\nOption 2: Check Python and library compatibility")
    print("-" * 60)
    print("Verify your environment:")
    print("  pip list | grep -E 'tensorflow|h5py|keras'")
    print("\nUpgrade if needed:")
    print("  pip install --upgrade tensorflow h5py")
    
    print("\nOption 3: Convert to SavedModel format")
    print("-" * 60)
    print("This avoids .h5 format issues:")
    print("  - Retrain with: python train_model.py")
    print("  - Then modify train_model.py to use:")
    print("    model.save('model_saved') instead of model.save('model.h5')")
    print("  - Update app.py to load:")
    print("    model = tf.keras.models.load_model('model_saved')")

def main():
    """Main function"""
    # Check model status
    is_valid = check_model_file()
    
    # Backup if exists
    if os.path.exists("model.h5"):
        backup_model()
    
    # Suggest fixes
    suggest_fixes()
    
    print("\n" + "=" * 60)
    if is_valid:
        print("✓ Your model file is valid and should work!")
        print("Try running: python app.py")
    else:
        print("✗ Your model file is corrupted or invalid.")
        print("Please follow Option 1 above to retrain the model.")
    print("=" * 60)

if __name__ == "__main__":
    main()
