import tensorflow as tf
import sys
import traceback
import json

def _strip_keras3_compat_fields(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, child in value.items():
            if key in {"quantization_config", "optional"} and child is None:
                continue
            if key == "optional":
                continue
            cleaned[key] = _strip_keras3_compat_fields(child)
        return cleaned
    if isinstance(value, list):
        return [_strip_keras3_compat_fields(item) for item in value]
    return value

def load_with_compat(model_path):
    try:
        return tf.keras.models.load_model(model_path, compile=False)
    except Exception as load_error:
        try:
            import h5py
        except ImportError:
            raise load_error
        
        with h5py.File(model_path, "r") as handle:
            model_config_raw = handle.attrs.get("model_config")
            if not model_config_raw:
                raise load_error
            if isinstance(model_config_raw, bytes):
                model_config_raw = model_config_raw.decode("utf-8")
            model_config = json.loads(model_config_raw)
            model_config = _strip_keras3_compat_fields(model_config)

        model = tf.keras.models.model_from_json(
            json.dumps(model_config),
            custom_objects={
                "Sequential": tf.keras.Sequential,
                "DTypePolicy": tf.keras.mixed_precision.Policy,
            },
        )
        model.load_weights(model_path)
        return model

with open("model_inspection_log.txt", "w") as f:
    for path in ["model.h5", "model.h5.bak"]:
        f.write(f"--- Inspecting {path} ---\n")
        try:
            model = load_with_compat(path)
            f.write(f"Loaded successfully.\n")
            f.write(f"Input shape: {model.input_shape}\n")
            f.write(f"Output shape: {model.output_shape}\n")
            f.write("Model Config:\n")
            f.write(json.dumps(model.get_config(), indent=2))
            f.write("\n\n")
        except Exception as e:
            f.write(f"Error loading {path}:\n")
            f.write(traceback.format_exc() + "\n\n")
