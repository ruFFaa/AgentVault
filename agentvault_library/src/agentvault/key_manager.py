"""
Manages loading and retrieving API keys and OAuth 2.0 Client Credentials
securely from various sources.

Priority Order for Loading Keys/Credentials (highest to lowest):
1. Key File (.env or .json)
2. Environment Variables
3. OS Keyring (if enabled and key/creds explicitly requested via get_ methods)

Storage Conventions:

API Keys:
- Env Vars: AGENTVAULT_KEY_<SERVICE_ID_UPPER>
- File (.env): <service_id_lower>=...
- File (.json): {"service_id": "..."} or {"service_id": {"apiKey": "..."}}
- Keyring: service="agentvault:<norm_id>", username="<norm_id>"

OAuth 2.0 Client Credentials (Client ID & Secret):
- Env Vars:
    - AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_ID
    - AGENTVAULT_OAUTH_<SERVICE_ID_UPPER>_CLIENT_SECRET
- File (.env):
    - AGENTVAULT_OAUTH_<service_id_lower>_CLIENT_ID=...
    - AGENTVAULT_OAUTH_<service_id_lower>_CLIENT_SECRET=...
- File (.json):
    {
        "service_id": {
            "oauth": {
                "clientId": "...",
                "clientSecret": "..."
            }
            // Optionally alongside "apiKey": "..."
        }
    }
- Keyring:
    - Client ID: service="agentvault:oauth:<norm_id>", username="clientId"
    - Client Secret: service="agentvault:oauth:<norm_id>", username="clientSecret"
"""

import os
import json
import logging
import pathlib
from typing import Dict, Optional, Union, Any, Tuple

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
    Handles loading and accessing API keys and OAuth 2.0 credentials from
    environment variables, files (.env or .json), and optionally the OS keyring.
    """
    env_prefix: str = "AGENTVAULT_KEY_" # Default prefix for API Keys
    oauth_env_prefix: str = "AGENTVAULT_OAUTH_"
    oauth_client_id_suffix: str = "_CLIENT_ID"
    oauth_client_secret_suffix: str = "_CLIENT_SECRET"


    def __init__(
        self,
        key_file_path: Optional[Union[str, pathlib.Path]] = None,
        use_env_vars: bool = True,
        use_keyring: bool = False,
        env_prefix: Optional[str] = None,
        oauth_env_prefix: Optional[str] = None
    ):
        """
        Initializes the KeyManager.
        """
        self.key_file_path: Optional[pathlib.Path] = None
        if key_file_path:
            self.key_file_path = pathlib.Path(key_file_path).resolve()

        self.use_env_vars = use_env_vars
        self.env_prefix = env_prefix if env_prefix is not None else KeyManager.env_prefix
        self.oauth_env_prefix = oauth_env_prefix if oauth_env_prefix is not None else KeyManager.oauth_env_prefix

        # Storage for API Keys
        self._keys: Dict[str, str] = {}
        self._key_sources: Dict[str, str] = {}

        # Storage for OAuth Credentials
        self._oauth_creds: Dict[str, Dict[str, str]] = {} # Stores {"clientId": "...", "clientSecret": "..."}
        self._oauth_sources: Dict[str, str] = {} # Stores source like 'file', 'env', 'keyring'

        # Keyring availability check
        self.use_keyring = False # Default to False
        if use_keyring:
            if not _keyring_imported:
                logger.warning(
                    "Keyring usage requested, but 'keyring' package is not installed. Keyring disabled. "
                    "Install with 'pip install agentvault[os_keyring]' or 'poetry install --extras os_keyring'."
                )
            else:
                try:
                    keyring.get_keyring() # type: ignore
                    self.use_keyring = True
                    logger.debug("Keyring backend check successful during init. Keyring enabled.")
                except Exception as kr_init_err:
                    logger.warning(f"Keyring library imported but backend failed to initialize: {kr_init_err}. Keyring support disabled.")
                    self.use_keyring = False

        self._load_keys()

    def _load_keys(self) -> None:
        """Loads keys and credential structures from configured sources."""
        self._keys = {}
        self._key_sources = {}
        self._oauth_creds = {}
        self._oauth_sources = {}

        if self.key_file_path: self._load_from_file()
        if self.use_env_vars: self._load_from_env()

    def _load_from_file(self) -> None:
        """
        Loads API keys and OAuth credentials from the specified key file (.env or .json).
        """
        if not self.key_file_path: return
        logger.debug(f"Attempting to load keys/creds from file: {self.key_file_path}")
        if not self.key_file_path.exists(): logger.warning(f"Key file specified but not found: {self.key_file_path}"); return
        if not self.key_file_path.is_file(): logger.warning(f"Key file path specified but is not a file: {self.key_file_path}"); return

        file_suffix = self.key_file_path.suffix.lower()
        api_loaded_count = 0; api_overwritten_count = 0
        oauth_loaded_count = 0; oauth_overwritten_count = 0 # Count services where OAuth was loaded

        try:
            if file_suffix == ".env":
                logger.debug("Processing key file as .env format.")
                env_values = dotenv_values(self.key_file_path, stream=None, verbose=False)
                for key, value in env_values.items():
                    if not value: # Skip empty values for both types
                        logger.warning(f"Skipping empty value for key '{key}' in .env file '{self.key_file_path}'.")
                        continue

                    # .env OAuth Handling
                    if key.startswith(self.oauth_env_prefix):
                        remaining = key[len(self.oauth_env_prefix):]
                        cred_type = None
                        service_id_part = None

                        if remaining.endswith(self.oauth_client_id_suffix):
                            cred_type = "clientId"
                            service_id_part = remaining[:-len(self.oauth_client_id_suffix)]
                        elif remaining.endswith(self.oauth_client_secret_suffix):
                            cred_type = "clientSecret"
                            service_id_part = remaining[:-len(self.oauth_client_secret_suffix)]

                        if not cred_type or not service_id_part:
                            logger.warning(f"Skipping malformed OAuth key '{key}' in .env file.")
                            continue

                        normalized_id = service_id_part.lower()

                        # Check priority: Overwrite if already loaded from file (last one wins in .env)
                        if normalized_id in self._oauth_sources:
                            logger.debug(f"OAuth source for '{normalized_id}' already set to '{self._oauth_sources[normalized_id]}'. Overwriting with value from .env key '{key}'.")
                        else:
                            oauth_loaded_count += 1 # Count as newly loaded service

                        if normalized_id not in self._oauth_creds:
                            self._oauth_creds[normalized_id] = {}
                        self._oauth_creds[normalized_id][cred_type] = value
                        self._oauth_sources[normalized_id] = 'file' # Set source
                        logger.info(f"Loaded OAuth '{cred_type}' for service '{normalized_id}' from .env file.")
                    # API Key Logic
                    else:
                        normalized_id = key.lower()
                        if normalized_id in self._keys: api_overwritten_count += 1; logger.debug(f"Overwriting API key for '{normalized_id}' from source '{self._key_sources.get(normalized_id)}' with value from file.")
                        self._keys[normalized_id] = value; self._key_sources[normalized_id] = 'file'; logger.info(f"Loaded API key for service '{normalized_id}' from .env file."); api_loaded_count += 1

            elif file_suffix == ".json":
                logger.debug("Processing key file as .json format.")
                raw_content = self.key_file_path.read_text(encoding='utf-8'); data = json.loads(raw_content)
                if not isinstance(data, dict): logger.error(f"Invalid format in JSON key file '{self.key_file_path}': Root element must be an object (dictionary)."); return

                for key, value in data.items():
                    normalized_id = key.lower()
                    api_key_loaded = False
                    oauth_loaded_this_service = False

                    # Try loading API Key first
                    api_key_value = None
                    if isinstance(value, str):
                        api_key_value = value
                    elif isinstance(value, dict) and isinstance(value.get("apiKey"), str):
                        api_key_value = value["apiKey"]

                    if api_key_value:
                        if api_key_value: # Check not empty
                            if normalized_id in self._keys: api_overwritten_count += 1; logger.debug(f"Overwriting API key for '{normalized_id}' from source '{self._key_sources.get(normalized_id)}' with value from JSON file.")
                            self._keys[normalized_id] = api_key_value; self._key_sources[normalized_id] = 'file'; logger.info(f"Loaded API key for service '{normalized_id}' from JSON file."); api_loaded_count += 1
                            api_key_loaded = True
                        else: logger.warning(f"Skipping empty string value for key '{key}' (or nested apiKey) in JSON file '{self.key_file_path}'.")

                    # .json OAuth Handling
                    if isinstance(value, dict) and "oauth" in value:
                        oauth_dict = value["oauth"]
                        if isinstance(oauth_dict, dict):
                            client_id = oauth_dict.get("clientId")
                            client_secret = oauth_dict.get("clientSecret")

                            has_valid_id = isinstance(client_id, str) and client_id
                            has_valid_secret = isinstance(client_secret, str) and client_secret

                            if has_valid_id or has_valid_secret:
                                # Check priority: Overwrite if already loaded from file
                                if normalized_id in self._oauth_sources:
                                    oauth_overwritten_count += 1
                                    logger.debug(f"Overwriting OAuth creds for '{normalized_id}' from source '{self._oauth_sources[normalized_id]}' with value from JSON file.")
                                else:
                                    oauth_loaded_count += 1

                                self._oauth_creds[normalized_id] = {} # Ensure it's initialized/reset
                                if has_valid_id:
                                    self._oauth_creds[normalized_id]["clientId"] = client_id
                                    logger.info(f"Loaded OAuth 'clientId' for service '{normalized_id}' from JSON file.")
                                else:
                                    logger.warning(f"Missing or invalid 'clientId' in 'oauth' block for service '{normalized_id}' in JSON file.")

                                if has_valid_secret:
                                    self._oauth_creds[normalized_id]["clientSecret"] = client_secret
                                    logger.info(f"Loaded OAuth 'clientSecret' for service '{normalized_id}' from JSON file.")
                                else:
                                     logger.warning(f"Missing or invalid 'clientSecret' in 'oauth' block for service '{normalized_id}' in JSON file.")

                                self._oauth_sources[normalized_id] = 'file' # Set source
                                oauth_loaded_this_service = True
                            else:
                                logger.warning(f"Found 'oauth' block for service '{normalized_id}' in JSON file, but missing valid 'clientId' and 'clientSecret'. Skipping.")
                        else:
                            logger.warning(f"Found 'oauth' key for service '{normalized_id}' in JSON file, but its value is not a dictionary. Skipping.")

                    # Log warning if neither API key nor valid OAuth creds were loaded for this top-level key
                    if not api_key_loaded and not oauth_loaded_this_service and not isinstance(value, str):
                         logger.warning(f"Skipping entry for key '{key}' in JSON file: Value is not a string, nor a dict containing 'apiKey' or a valid 'oauth' block. Value type: {type(value)}")

            else: logger.warning(f"Unsupported key file extension '{file_suffix}' for file: {self.key_file_path}. Only '.env' and '.json' are supported."); return
            logger.debug(f"Finished loading from file. API Keys Loaded: {api_loaded_count}, Overwritten: {api_overwritten_count}. OAuth Services Loaded/Updated: {oauth_loaded_count}.")
        except IOError as e: logger.error(f"Error reading key file '{self.key_file_path}': {e}", exc_info=True)
        except json.JSONDecodeError as e: logger.error(f"Error decoding JSON from key file '{self.key_file_path}': {e}", exc_info=True)
        except Exception as e: logger.error(f"An unexpected error occurred loading key file '{self.key_file_path}': {e}", exc_info=True)

    def _load_from_env(self) -> None:
        """
        Loads API keys and OAuth credentials from environment variables.
        Respects priority (File > Env).
        """
        # API Key Loading
        logger.debug(f"Attempting to load API keys from environment variables with prefix '{self.env_prefix}'...")
        api_prefix_len = len(self.env_prefix)
        api_loaded_count = 0; api_skipped_count = 0; api_empty_val_count = 0; api_empty_id_count = 0

        # OAuth Loading Prep
        oauth_prefix_len = len(self.oauth_env_prefix)
        oauth_loaded_count = 0; oauth_skipped_count = 0; oauth_empty_val_count = 0; oauth_malformed_count = 0
        logger.debug(f"Attempting to load OAuth creds from environment variables with prefix '{self.oauth_env_prefix}'...")

        for env_var, value in os.environ.items():
            # Check for API Key Prefix
            if env_var.startswith(self.env_prefix):
                service_id_part = env_var[api_prefix_len:]
                if not service_id_part: api_empty_id_count += 1; continue
                normalized_id = service_id_part.lower()
                # PRIORITY CHECK: Only load if not loaded from file
                if normalized_id not in self._key_sources:
                    if value: self._keys[normalized_id] = value; self._key_sources[normalized_id] = 'env'; api_loaded_count += 1
                    else: api_empty_val_count += 1
                else: api_skipped_count += 1 # Already loaded from file
            # Check for OAuth Prefix
            elif env_var.startswith(self.oauth_env_prefix):
                remaining = env_var[oauth_prefix_len:]
                cred_type = None
                service_id_part = None

                if remaining.endswith(self.oauth_client_id_suffix):
                    cred_type = "clientId"
                    service_id_part = remaining[:-len(self.oauth_client_id_suffix)]
                elif remaining.endswith(self.oauth_client_secret_suffix):
                    cred_type = "clientSecret"
                    service_id_part = remaining[:-len(self.oauth_client_secret_suffix)]

                if not cred_type or not service_id_part:
                    oauth_malformed_count += 1
                    continue

                normalized_id = service_id_part.lower()

                # --- CORRECTED Priority Check ---
                # Allow loading from env if source is not set OR if source is already 'env'
                # (to allow loading both ID and Secret from env)
                # Skip only if source is 'file' (or 'keyring' later)
                current_source = self._oauth_sources.get(normalized_id)
                if current_source == 'file': # Or add 'keyring' check later
                    oauth_skipped_count += 1
                    logger.debug(f"OAuth creds for service '{normalized_id}' already loaded from '{current_source}'. Skipping environment variable '{env_var}'.")
                    continue
                # --- END CORRECTED ---

                # Proceed if source is not set or is 'env'
                if value:
                    if normalized_id not in self._oauth_creds:
                        self._oauth_creds[normalized_id] = {}
                    # Store the credential part
                    self._oauth_creds[normalized_id][cred_type] = value
                    # Set source only once per service_id from env
                    if normalized_id not in self._oauth_sources:
                         self._oauth_sources[normalized_id] = 'env'
                    oauth_loaded_count += 1
                else:
                    oauth_empty_val_count += 1


        logger.debug(f"Finished loading API Keys from env. Loaded: {api_loaded_count}, Skipped (File): {api_skipped_count}, EmptyVal: {api_empty_val_count}, EmptyID: {api_empty_id_count}.")
        logger.debug(f"Finished loading OAuth Creds from env. Loaded parts: {oauth_loaded_count}, Skipped (File): {oauth_skipped_count}, EmptyVal: {oauth_empty_val_count}, Malformed: {oauth_malformed_count}.")

    def _load_from_keyring(self, service_id: str) -> Optional[str]:
        """Attempts to load a specific API key from the OS keyring."""
        if not self.use_keyring: return None
        if not _keyring_imported or keyring is None: return None

        normalized_id = service_id.lower()
        keyring_service_name = f"agentvault:{normalized_id}" # Convention for API keys
        try:
            logger.debug(f"Attempting to load API key for service '{normalized_id}' from keyring (service name: '{keyring_service_name}').")
            key_value = keyring.get_password(keyring_service_name, normalized_id)
            if key_value is not None: logger.info(f"Loaded API key for service '{normalized_id}' from OS keyring."); return key_value
            else: logger.debug(f"API key for service '{normalized_id}' not found in OS keyring."); return None
        except Exception as e:
            logger.error(f"Failed to get API key for service '{normalized_id}' from keyring: {e}", exc_info=True)
            return None

    def _load_oauth_from_keyring(self, service_id: str) -> Optional[Dict[str, str]]:
        """
        Attempts to load OAuth client_id and client_secret from the OS keyring.
        Returns the creds dict only if BOTH are found.
        """
        if not self.use_keyring: return None
        if not _keyring_imported or keyring is None: return None

        normalized_id = service_id.lower()
        keyring_service_name = f"agentvault:oauth:{normalized_id}" # Convention for OAuth
        logger.debug(f"Attempting to load OAuth creds for service '{normalized_id}' from keyring (service name: '{keyring_service_name}').")
        client_id = None
        client_secret = None
        try:
            client_id = keyring.get_password(keyring_service_name, "clientId")
            client_secret = keyring.get_password(keyring_service_name, "clientSecret")

            if client_id and client_secret:
                 logger.info(f"Loaded OAuth credentials for service '{normalized_id}' from OS keyring.")
                 return {"clientId": client_id, "clientSecret": client_secret}
            elif client_id or client_secret:
                 logger.warning(f"Found partial OAuth credentials for service '{normalized_id}' in OS keyring (missing ID or Secret). Ignoring.")
                 return None
            else:
                 logger.debug(f"OAuth credentials for service '{normalized_id}' not found in OS keyring.")
                 return None
        except Exception as e:
            logger.error(f"Failed to get OAuth credentials for service '{normalized_id}' from keyring: {e}", exc_info=True)
            return None

    def get_key(self, service_id: str) -> Optional[str]:
        """Retrieves an API key for the given service ID."""
        normalized_id = service_id.lower()
        # 1. Check cache (File > Env)
        if normalized_id in self._keys:
            source = self._key_sources.get(normalized_id, 'cache')
            logger.debug(f"Returning cached API key for '{normalized_id}' (loaded from {source}).")
            return self._keys[normalized_id]
        # 2. Try loading from keyring if enabled and not found in cache
        if self.use_keyring:
            logger.debug(f"API key for '{normalized_id}' not in cache, attempting keyring load.")
            key_value = self._load_from_keyring(normalized_id)
            if key_value is not None:
                self._keys[normalized_id] = key_value
                self._key_sources[normalized_id] = 'keyring'
                return key_value
        # 3. Not found anywhere
        logger.debug(f"API key for service '{normalized_id}' not found in any configured source.")
        return None

    def get_key_source(self, service_id: str) -> Optional[str]:
        """Returns the source from which the API key for the given service ID was loaded."""
        normalized_id = service_id.lower()
        return self._key_sources.get(normalized_id)

    def set_key_in_keyring(self, service_id: str, key_value: str) -> None:
        """Stores or updates an API key in the OS keyring."""
        if not self.use_keyring: raise KeyManagementError("Keyring support is not enabled or non-functional.")
        if not _keyring_imported or keyring is None: raise KeyManagementError("Keyring library not available.")
        if not isinstance(key_value, str) or not key_value: raise ValueError("key_value must be a non-empty string.")

        normalized_id = service_id.lower()
        keyring_service_name = f"agentvault:{normalized_id}" # Convention for API keys
        try:
            logger.info(f"Setting API key for service '{normalized_id}' in OS keyring under service name '{keyring_service_name}'.")
            keyring.set_password(keyring_service_name, normalized_id, key_value)
        except Exception as e:
            logger.error(f"Failed to set API key for service '{normalized_id}' in keyring: {e}", exc_info=True)
            raise KeyManagementError(f"Failed to set API key in keyring for service '{normalized_id}': {e}") from e

    def get_oauth_client_id(self, service_id: str) -> Optional[str]:
        """Retrieves the OAuth Client ID for the given service ID."""
        normalized_id = service_id.lower()
        # 1. Check cache (File > Env)
        if normalized_id in self._oauth_creds and "clientId" in self._oauth_creds[normalized_id]:
            source = self._oauth_sources.get(normalized_id, 'cache')
            logger.debug(f"Returning cached OAuth Client ID for '{normalized_id}' (loaded from {source}).")
            return self._oauth_creds[normalized_id]["clientId"]
        # 2. Try loading from keyring if enabled and not found in cache
        if self.use_keyring:
            # Check cache *before* loading to avoid redundant keyring calls if already loaded
            if normalized_id not in self._oauth_sources: # Only load if source isn't set yet
                logger.debug(f"OAuth creds for '{normalized_id}' not in cache, attempting keyring load.")
                creds = self._load_oauth_from_keyring(normalized_id)
                if creds:
                    # Cache the loaded credentials
                    self._oauth_creds[normalized_id] = creds
                    self._oauth_sources[normalized_id] = 'keyring'
                    return creds.get("clientId") # Return ID if found
            elif normalized_id in self._oauth_creds: # Already loaded (e.g., from file/env)
                 return self._oauth_creds[normalized_id].get("clientId")
        # 3. Not found
        logger.debug(f"OAuth Client ID for service '{normalized_id}' not found.")
        return None

    def get_oauth_client_secret(self, service_id: str) -> Optional[str]:
        """Retrieves the OAuth Client Secret for the given service ID."""
        normalized_id = service_id.lower()
        # 1. Check cache (File > Env)
        if normalized_id in self._oauth_creds and "clientSecret" in self._oauth_creds[normalized_id]:
            source = self._oauth_sources.get(normalized_id, 'cache')
            logger.debug(f"Returning cached OAuth Client Secret for '{normalized_id}' (loaded from {source}).")
            return self._oauth_creds[normalized_id]["clientSecret"]
        # 2. Try loading from keyring if enabled and not found in cache
        if self.use_keyring:
            # Check cache *before* loading
            if normalized_id not in self._oauth_sources: # Only load if source isn't set yet
                 logger.debug(f"OAuth creds for '{normalized_id}' not in cache, attempting keyring load.")
                 creds = self._load_oauth_from_keyring(normalized_id)
                 if creds:
                     self._oauth_creds[normalized_id] = creds
                     self._oauth_sources[normalized_id] = 'keyring'
                     return creds.get("clientSecret") # Return Secret if found
            elif normalized_id in self._oauth_creds: # Already loaded (e.g., from file/env)
                  return self._oauth_creds[normalized_id].get("clientSecret")

        # 3. Not found
        logger.debug(f"OAuth Client Secret for service '{normalized_id}' not found.")
        return None

    def get_oauth_config_status(self, service_id: str) -> str:
        """Checks if OAuth credentials (ID and Secret) are configured for a service."""
        normalized_id = service_id.lower()
        # Attempt to load them first (checks cache, then keyring if enabled)
        client_id = self.get_oauth_client_id(normalized_id)
        client_secret = self.get_oauth_client_secret(normalized_id)

        if client_id and client_secret:
            source = self._oauth_sources.get(normalized_id, "Unknown")
            return f"Configured (Source: {source.upper()})"
        elif client_id or client_secret:
            source = self._oauth_sources.get(normalized_id, "Unknown")
            return f"Partially Configured (Source: {source.upper()})"
        else:
            return "Not Configured"

    def set_oauth_creds_in_keyring(self, service_id: str, client_id: str, client_secret: str) -> None:
        """
        Stores or updates OAuth Client ID and Secret in the OS keyring.
        """
        if not self.use_keyring: raise KeyManagementError("Keyring support is not enabled or non-functional.")
        if not _keyring_imported or keyring is None: raise KeyManagementError("Keyring library not available.")
        if not isinstance(client_id, str) or not client_id: raise ValueError("client_id must be a non-empty string.")
        if not isinstance(client_secret, str) or not client_secret: raise ValueError("client_secret must be a non-empty string.")

        normalized_id = service_id.lower()
        keyring_service_name = f"agentvault:oauth:{normalized_id}" # Convention for OAuth
        logger.info(f"Setting OAuth creds for service '{normalized_id}' in OS keyring under service name '{keyring_service_name}'.")
        try:
            keyring.set_password(keyring_service_name, "clientId", client_id)
            keyring.set_password(keyring_service_name, "clientSecret", client_secret)
            # Clear cache for this service to force reload on next get
            if normalized_id in self._oauth_creds:
                del self._oauth_creds[normalized_id]
            if normalized_id in self._oauth_sources:
                del self._oauth_sources[normalized_id]
            logger.info(f"Successfully set OAuth credentials for '{normalized_id}' in keyring.")
        except Exception as e:
            logger.error(f"Failed to set OAuth creds for service '{normalized_id}' in keyring: {e}", exc_info=True)
            raise KeyManagementError(f"Failed to set OAuth creds in keyring for service '{normalized_id}': {e}") from e

#
