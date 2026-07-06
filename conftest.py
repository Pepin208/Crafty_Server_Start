import os
import pytest

# Set default env vars before any imports so global config loading passes
os.environ["CRAFTY_URL"] = "http://test"
os.environ["CRAFTY_TOKEN"] = "token"
os.environ["SERVER_ID"] = "123"
os.environ["CRAFTY_DIR"] = "/tmp"
os.environ["MC_PUBLIC_PORT"] = "25565"
os.makedirs("/tmp/venv", exist_ok=True)
with open("/tmp/main.py", "w") as f:
    f.write("")
