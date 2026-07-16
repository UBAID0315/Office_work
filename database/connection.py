from mysql.connector import connect, Error
from dotenv import load_dotenv
import os

load_dotenv()

def create_connection():
    """Create a database connection to a MySQL database."""
    try:
        connection = connect(
            host="localhost",
            user="root",
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        return connection
    except Error as e:
        print(f"Error: '{e}'")
        return None