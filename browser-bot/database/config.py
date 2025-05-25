import os

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "DB_HOST": os.getenv("DB_HOST"),
    "DB_PORT": int(os.getenv("DB_PORT")),
    "DB_NAME": os.getenv("DB_NAME"),
    "DB_USER": os.getenv("DB_USER"),
    "DB_PASS": os.getenv("DB_PASS"),
}

def get_database_url():
    return (
        f"postgresql://{DB_CONFIG['DB_USER']}:{DB_CONFIG['DB_PASS']}"
        f"@{DB_CONFIG['DB_HOST']}:{DB_CONFIG['DB_PORT']}/{DB_CONFIG['DB_NAME']}"
    )