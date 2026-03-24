import tensorflow as tf
import sys

def inspect_model(path):
    print(f"--- Inspecting {path} ---")
    try:
        model = tf.keras.models.load_model(path, compile=False)
        model.summary()
        print("Input shape:", model.input_shape)
        print("Output shape:", model.output_shape)
    except Exception as e:
        print(f"Error loading {path}: {e}")

if __name__ == "__main__":
    inspect_model("c:/Users/chaud/Downloads/Ishario/Ishario/model.h5")
    inspect_model("c:/Users/chaud/Downloads/Ishario/Ishario/model.h5.bak")
