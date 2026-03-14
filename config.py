import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'c1b0563091f8c5624a412a50246d10821068e93b396d6c37d78a7fead2821084')
    
    # MySQL Database Configuration
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'Jayesh@45')
    MYSQL_DB = os.getenv('MYSQL_DB', 'signease')
    
    # Email Configuration (SMTP)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'jayesh.d.chaudhary@slrtce.in')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'dkyi xcun djwe eicd')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'jayesh.d.chaudhary@slrtce.in')
    
    # OTP Configuration
    OTP_EXPIRY_MINUTES = 10
    OTP_LENGTH = 6