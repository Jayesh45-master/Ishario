-- Signease database schema (signease)
-- Designed to be idempotent (safe to run multiple times).

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  first_name VARCHAR(100) NULL,
  last_name VARCHAR(100) NULL,
  username VARCHAR(100) NOT NULL UNIQUE,
  email VARCHAR(255) NOT NULL UNIQUE,
  contact VARCHAR(30) NULL,
  password_hash VARCHAR(255) NOT NULL,
  otp VARCHAR(20) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sign_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sign_name VARCHAR(255) NOT NULL UNIQUE,
  image_data LONGBLOB NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

