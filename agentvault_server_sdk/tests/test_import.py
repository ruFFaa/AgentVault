import pytest

def test_sdk_import():
    """
    Basic test to ensure the agentvault_server_sdk package can be imported.
    """
    try:
        import agentvault_server_sdk
    except ImportError as e:
        pytest.fail(f"Failed to import agentvault_server_sdk: {e}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred during import: {e}")

    # Optional: Add a basic assertion if the __init__ exposes something
    # assert hasattr(agentvault_server_sdk, 'some_expected_attribute')
