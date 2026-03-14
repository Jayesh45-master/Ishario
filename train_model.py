import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
import os
import sys
import time

# Correct dataset path
dataset = os.path.join("archive", "asl_alphabet_train", "asl_alphabet_train")

print(f"Loading training data from: {dataset}")

if not os.path.exists(dataset):
    print(f"ERROR: Dataset not found at {dataset}")
    sys.exit(1)

print("Creating data generators...")
start_time = time.time()

datagen = ImageDataGenerator(rescale=1./255, validation_split=0.2)

train = datagen.flow_from_directory(
    dataset,
    target_size=(64, 64),
    batch_size=64,  # Increased batch size for faster training
    class_mode="categorical",
    subset="training"
)

val = datagen.flow_from_directory(
    dataset,
    target_size=(64, 64),
    batch_size=64,
    class_mode="categorical",
    subset="validation"
)

print(f"Number of classes: {train.num_classes}")
print(f"Data loading time: {time.time() - start_time:.2f}s")

print("\nBuilding model...")
model = tf.keras.models.Sequential([
    tf.keras.layers.Conv2D(32, (3, 3), activation="relu", input_shape=(64, 64, 3)),
    tf.keras.layers.MaxPooling2D(pool_size=(2, 2)),
    tf.keras.layers.Conv2D(64, (3, 3), activation="relu"),
    tf.keras.layers.MaxPooling2D(pool_size=(2, 2)),
    tf.keras.layers.Conv2D(128, (3, 3), activation="relu"),
    tf.keras.layers.MaxPooling2D(pool_size=(2, 2)),
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(256, activation="relu"),
    tf.keras.layers.Dropout(0.5),
    tf.keras.layers.Dense(train.num_classes, activation="softmax")
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

print(f"Training on {len(train)} training samples and {len(val)} validation samples...")
print("Starting training (this may take 10-30 minutes)...\n")

# Train with 3 epochs for faster initial model
training_start = time.time()
history = model.fit(
    train,
    epochs=3,  # Reduced from 10 to 3 for faster training
    validation_data=val,
    verbose=1
)

training_time = time.time() - training_start
print(f"\nTraining completed in {training_time/60:.2f} minutes")
print(f"Final accuracy: {history.history['accuracy'][-1]:.4f}")
print(f"Final validation accuracy: {history.history['val_accuracy'][-1]:.4f}")

print("\nSaving model as model.h5...")
model.save("model.h5")

file_size = os.path.getsize("model.h5") / 1024 / 1024
print(f"✓ Model saved successfully!")
print(f"  File size: {file_size:.2f} MB")
print(f"\nYou can now run the Flask app: python app.py")

