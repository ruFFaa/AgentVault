"""
Manages loading and retrieving API keys securely from various sources.

Priority Order for Loading Keys (highest to lowest):
1. Key File (.env or .json)
2. Environment Variables
3. OS Keyring (if enabled and key explicitly requested via get_key)
"""

import os
import json
import logging
import pathlib
from typing import Dict, Optional, Union, Any

# Import dotenv for .env file support
from dotenv import dotenv_values

# Import custom exceptions
from .exceptions import KeyManagementError

# Set up logging
logger = logging.getLogger(__name__)

# Optional keyring import handling - Check if library is installed at module level
try:
    import keyring
    _keyring_imported = True
except ImportError:
    keyring = None # type: ignore
    _keyring_imported = False


class KeyManager:
    """
    Handles loading and accessing API keys from environment variables,
    files (.env or .json), and optionally the OS keyring.
    """
    env_prefix: str = "AGENTVAULT_KEY_" # Default prefix

    def __init__(
        self,
        key_file_path: Optional[Union[str, pathlib.Path]] = None,
        use_env_vars: bool = True,
        use_keyring: bool = False,
        env_prefix: Optional[str] = None
    ):
        """
        Initializes the KeyManager.
        """
        self.key_file_path: Optional[pathlib.Path] = None
        if key_file_path:
            self.key_file_path = pathlib.Path(key_file_path).resolve()

        self.use_env_vars = use_env_vars
        self.env_prefix = env_prefix if env_prefix is not None else KeyManager.env_prefix
        self._keys: Dict[str, str] = {}
        self._key_sources: Dict[str, str] = {}

        # --- REVISED: Simplified Keyring Check ---
        self.use_keyring = False # Default to False
        if use_keyring:
            if not _keyring_imported:
                logger.warning(
                    "Keyring usage requested, but 'keyring' package is not installed. Keyring disabled. "
                    "Install with 'pip install agentvault[os_keyring]' or 'poetry install --extras os_keyring'."
                )
            else:
                try:
                    # Perform functional check here. Relies on tests mocking keyring module.
                    keyring.get_keyring() # type: ignore
                    self.use_keyring = True # Enable only if functional check passes
                    logger.debug("Keyring backend check successful during init. Keyring enabled.")
                except Exception as kr_init_err:
                    logger.warning(f"Keyring library imported but backend failed to initialize: {kr_init_err}. Keyring support disabled.")
                    self.use_keyring = False # Ensure it's disabled if check fails
        # --- END REVISED ---

        self._load_keys()

    # --- REMOVED _check_and_get_keyring_module helper ---

    def _load_keys(self) -> None:
        """Loads keys from configured sources in priority order."""
        if self.key_file_path: self._load_from_file()
        if self.use_env_vars: self._load_from_env()

    def _load_from_file(self) -> None:
        """Loads keys from the specified key file (.env or .json)."""
        # (Implementation as before)
        if not self.key_file_path: return
        logger.debug(f"Attempting to load keys from file: {self.key_file_path}")
        if not self.key_file_path.exists(): logger.warning(f"Key file specified but not found: {self.key_file_path}"); return
        if not self.key_file_path.is_file(): logger.warning(f"Key file path specified but is not a file: {self.key_file_path}"); return
        file_suffix = self.key_file_path.suffix.lower(); loaded_count = 0; overwritten_count = 0
        try:
            if file_suffix == ".env":
                logger.debug("Processing key file as .env format.")
                env_values = dotenv_values(self.key_file_path, stream=None, verbose=False)
                for key, value in env_values.items():
                    if value:
                        normalized_id = key.lower()
                        if normalized_id in self._keys: overwritten_count += 1; logger.debug(f"Overwriting key for '{normalized_id}' from source '{self._key_sources.get(normalized_id)}' with value from file.")
                        self._keys[normalized_id] = value; self._key_sources[normalized_id] = 'file'; logger.info(f"Loaded key for service '{normalized_id}' from file."); loaded_count += 1
                    else: logger.warning(f"Skipping empty value for key '{key}' in file '{self.key_file_path}'.")
            elif file_suffix == ".json":
                logger.debug("Processing key file as .json format.")
                raw_content = self.key_file_path.read_text(encoding='utf-8'); data = json.loads(raw_content)
                if not isinstance(data, dict): logger.error(f"Invalid format in JSON key file '{self.key_file_path}': Root element must be an object (dictionary)."); return
                for key, value in data.items():
                    normalized_id = key.lower()
                    if isinstance(value, str):
                        if value:
                            if normalized_id in self._keys: overwritten_count += 1; logger.debug(f"Overwriting key for '{normalized_id}' from source '{self._key_sources.get(normalized_id)}' with value from file.")
                            self._keys[normalized_id] = value; self._key_sources[normalized_id] = 'file'; logger.info(f"Loaded key for service '{normalized_id}' from file."); loaded_count += 1
                        else: logger.warning(f"Skipping empty string value for key '{key}' in JSON file '{self.key_file_path}'.")
                    else: logger.warning(f"Skipping non-string value for key '{key}' in JSON file '{self.key_file_path}'. Value type: {type(value)}")
            else: logger.warning(f"Unsupported key file extension '{file_suffix}' for file: {self.key_file_path}. Only '.env' and '.json' are supported."); return
            logger.debug(f"Finished loading from file. Loaded {loaded_count} keys. Overwrote {overwritten_count} existing keys.")
        except IOError as e: logger.error(f"Error reading key file '{self.key_file_path}': {e}", exc_info=True)
        except json.JSONDecodeError as e: logger.error(f"Error decoding JSON from key file '{self.key_file_path}': {e}", exc_info=True)
        except Exception as e: logger.error(f"An unexpected error occurred loading key file '{self.key_file_path}': {e}", exc_info=True)

    def _load_from_env(self) -> None:
        """Loads keys from environment variables based on the prefix."""
        # (Implementation as before)
        logger.debug(f"Attempting to load keys from environment variables with prefix '{self.env_prefix}'...")
        prefix_len = len(self.env_prefix); loaded_count = 0; skipped_count = 0; empty_val_count = 0; empty_id_count = 0
        for env_var, value in os.environ.items():
            if env_var.startswith(self.env_prefix):
                service_id_part = env_var[prefix_len:]
                if not service_id_part: logger.warning(f"Skipping environment variable '{env_var}' with empty service ID part."); empty_id_count += 1; continue
                normalized_id = service_id_part.lower()
                if normalized_id not in self._keys:
                    if value: self._keys[normalized_id] = value; self._key_sources[normalized_id] = 'env'; logger.info(f"Loaded key for service '{normalized_id}' from environment variable."); loaded_count += 1
                    else: logger.warning(f"Environment variable '{env_var}' found but has an empty value. Skipping."); empty_val_count += 1
                else: logger.debug(f"Key for service '{normalized_id}' already loaded from '{self._key_sources.get(normalized_id, 'unknown')}'. Skipping environment variable '{env_var}'."); skipped_count += 1
        logger.debug(f"Finished loading from environment variables. Loaded: {loaded_count}, Skipped (already loaded): {skipped_count}, Skipped (empty value): {empty_val_count}, Skipped (empty ID): {empty_id_count}.")

    def _load_from_keyring(self, service_id: str) -> Optional[str]:
        """Attempts to load a specific key from the OS keyring."""
        # --- MODIFIED: Directly check self.use_keyring and use module-level keyring ---
        if not self.use_keyring:
            logger.debug("Keyring usage is disabled or non-functional, skipping keyring load.")
            return None
        if not _keyring_imported or keyring is None: # Should not happen if self.use_keyring is True, but safety check
             logger.error("Keyring requested and enabled, but keyring module is not available unexpectedly.")
             return None
        # --- END MODIFIED ---

        normalized_id = service_id.lower()
        keyring_service_name = f"agentvault:{normalized_id}"
        try:
            logger.debug(f"Attempting to load key for service '{normalized_id}' from keyring (service name: '{keyring_service_name}').")
            key_value = keyring.get_password(keyring_service_name, normalized_id)
            if key_value is not None: logger.info(f"Loaded key for service '{normalized_id}' from OS keyring."); return key_value
            else: logger.debug(f"Key for service '{normalized_id}' not found in OS keyring."); return None
        except Exception as e:
            logger.error(f"Failed to get key for service '{normalized_id}' from keyring: {e}", exc_info=True)
            return None

    def get_key(self, service_id: str) -> Optional[str]:
        """Retrieves a key for the given service ID."""
        normalized_id = service_id.lower()
        # 1. Check cache (File > Env)
        if normalized_id in self._keys:
            source = self._key_sources.get(normalized_id, 'cache')
            logger.debug(f"Returning cached key for '{normalized_id}' (loaded from {source}).")
            return self._keys[normalized_id]
        # 2. Try loading from keyring if enabled and not found in cache
        # The self.use_keyring flag is now reliably set in __init__
        if self.use_keyring: # Check the instance flag set during __init__
            logger.debug(f"Key for '{normalized_id}' not in cache, attempting keyring load.")
            key_value = self._load_from_keyring(normalized_id)
            if key_value is not None:
                self._keys[normalized_id] = key_value
                self._key_sources[normalized_id] = 'keyring'
                return key_value
        # 3. Not found anywhere
        logger.debug(f"Key for service '{normalized_id}' not found in any configured source (or keyring disabled/failed).")
        return None

    def get_key_source(self, service_id: str) -> Optional[str]:
        """Returns the source from which the key for the given service ID was loaded."""
        normalized_id = service_id.lower()
        return self._key_sources.get(normalized_id)

    def set_key_in_keyring(self, service_id: str, key_value: str) -> None:
        """Stores or updates a key in the OS keyring."""
        # --- MODIFIED: Directly check self.use_keyring and use module-level keyring ---
        if not self.use_keyring:
            raise KeyManagementError("Keyring support is not enabled or non-functional for this KeyManager instance.")
        if not _keyring_imported or keyring is None: # Should not happen if self.use_keyring is True
             raise KeyManagementError("Keyring requested and enabled, but keyring module is not available unexpectedly.")
        # --- END MODIFIED ---

        if not isinstance(key_value, str) or not key_value:
             raise ValueError("key_value must be a non-empty string.")
        normalized_id = service_id.lower()
        keyring_service_name = f"agentvault:{normalized_id}"
        try:
            logger.info(f"Setting key for service '{normalized_id}' in OS keyring under service name '{keyring_service_name}'.")
            keyring.set_password(keyring_service_name, normalized_id, key_value)
        except Exception as e:
            logger.error(f"Failed to set key for service '{normalized_id}' in keyring: {e}", exc_info=True)
            raise KeyManagementError(f"Failed to set key in keyring for service '{normalized_id}': {e}") from e

#
