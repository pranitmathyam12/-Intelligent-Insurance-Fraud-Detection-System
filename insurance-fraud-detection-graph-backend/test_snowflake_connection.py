import os
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv('.env')

print("Environment variables loaded:")
print(f"SNOWFLAKE_ACCOUNT: '{os.getenv('SNOWFLAKE_ACCOUNT')}'")
print(f"SNOWFLAKE_USER: '{os.getenv('SNOWFLAKE_USER')}'")
print(f"SNOWFLAKE_PASSWORD: {'SET' if os.getenv('SNOWFLAKE_PASSWORD') else 'MISSING'}")
print(f"SNOWFLAKE_WAREHOUSE: '{os.getenv('SNOWFLAKE_WAREHOUSE')}'")
print(f"SNOWFLAKE_DATABASE: '{os.getenv('SNOWFLAKE_DATABASE')}'")
print(f"SNOWFLAKE_SCHEMA: '{os.getenv('SNOWFLAKE_SCHEMA')}'")
print()

try:
    from app.db.snowflake_utils import get_snowflake_connection
    print("Testing Snowflake connection...")
    conn = get_snowflake_connection()
    if conn:
        print("✅ SUCCESS! Connected to Snowflake")
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_VERSION()")
        version = cursor.fetchone()
        print(f"Snowflake version: {version[0]}")
        cursor.close()
        conn.close()
    else:
        print("❌ FAILED - Connection returned None")
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
