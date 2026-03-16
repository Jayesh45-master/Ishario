-- Ishario main database schema (ishario_db)
-- Designed to be idempotent (safe to run multiple times).

CREATE TABLE IF NOT EXISTS profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  alt_email VARCHAR(255),
  contact VARCHAR(30),
  username VARCHAR(100),
  dob DATE,
  about TEXT,
  photo LONGBLOB,
  photo_mime VARCHAR(100),
  photo_filename VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  username VARCHAR(100) NULL,
  name VARCHAR(255) NULL,
  role VARCHAR(50) NULL,
  course_progress VARCHAR(50) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NULL,
  email VARCHAR(255) NULL,
  category VARCHAR(100) NULL,
  rating INT NULL,
  message TEXT NULL,
  status VARCHAR(50) NULL,
  reply TEXT NULL,
  date DATETIME NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  password VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gesture_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_email VARCHAR(255) NULL,
  gesture VARCHAR(255) NOT NULL,
  confidence FLOAT NULL,
  source VARCHAR(50) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_gesture_history_user_email (user_email)
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_email VARCHAR(255) NULL,
  role VARCHAR(20) NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_chat_messages_user_email (user_email)
);
