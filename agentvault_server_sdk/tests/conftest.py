import os
import sys

# Add the src directory to the Python path for tests in this component
# This ensures that imports like 'from agentvault_server_sdk import ...' work correctly
# when running tests from the root or within the component directory.
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)
    print(f"\n[conftest.py] Added to sys.path: {src_path}\n") # Add print for verification

# You can add shared fixtures specific to server-sdk tests here later if needed.
