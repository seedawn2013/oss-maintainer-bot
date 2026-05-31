import sys
import os

# Add src/ to the Python path so tests can import feature modules directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
