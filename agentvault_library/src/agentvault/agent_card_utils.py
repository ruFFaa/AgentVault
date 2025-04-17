"""
Utilities for loading, parsing, and validating A2A Agent Cards.
"""

import json
import httpx
import pathlib
from typing import Dict, Any, Optional

# Import Pydantic for validation errors
import pydantic
# --- ADDED: Import respx exceptions if available (for testing) ---
try:
    import respx
    from respx.mock import MockError as RespxMockError
except ImportError:
    respx = None # type: ignore
    RespxMockError = Exception # Fallback type
# --- END ADDED ---

# Import local models and exceptions
from .models.agent_card import AgentCard
from .exceptions import (
    AgentCardError,
    AgentCardValidationError,
    AgentCardFetchError,
)


def parse_agent_card_from_dict(data: Dict[str, Any]) -> AgentCard:
    """
    Parses and validates Agent Card data from a dictionary.

    Args:
        data: A dictionary containing the Agent Card data.

    Returns:
        A validated AgentCard Pydantic model instance.

    Raises:
        AgentCardValidationError: If the provided data fails Pydantic validation.
        AgentCardError: For any other unexpected errors during parsing.
    """
    try:
        # Use Pydantic V2's model_validate method
        agent_card = AgentCard.model_validate(data)
        return agent_card
    except pydantic.ValidationError as e:
        # Wrap Pydantic's error in our custom exception
        raise AgentCardValidationError(f"Agent Card validation failed: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during parsing
        raise AgentCardError(f"An unexpected error occurred parsing the Agent Card data: {e}") from e


def load_agent_card_from_file(file_path: pathlib.Path) -> AgentCard:
    """
    Loads, parses, and validates an Agent Card from a local JSON file.

    Args:
        file_path: A pathlib.Path object pointing to the JSON file.

    Returns:
        A validated AgentCard Pydantic model instance.

    Raises:
        AgentCardError: If the file does not exist, is not a file,
                        cannot be read, or is not valid JSON.
        AgentCardValidationError: If the JSON content fails Agent Card validation.
    """
    if not isinstance(file_path, pathlib.Path):
         # Ensure input is a Path object for consistency
         file_path = pathlib.Path(file_path)

    if not file_path.exists():
        raise AgentCardError(f"Agent Card file not found at: {file_path}")
    if not file_path.is_file():
        raise AgentCardError(f"Path exists but is not a file: {file_path}")

    try:
        # Read the file content
        raw_content = file_path.read_text(encoding='utf-8')
        # Parse the JSON content
        data = json.loads(raw_content)
    except IOError as e:
        raise AgentCardError(f"Failed to read Agent Card file '{file_path}': {e}") from e
    except json.JSONDecodeError as e:
        raise AgentCardError(f"Failed to decode JSON from Agent Card file '{file_path}': {e}") from e
    except Exception as e:
        # Catch other potential errors during file reading/parsing
        raise AgentCardError(f"An unexpected error occurred loading Agent Card file '{file_path}': {e}") from e

    # Validate the loaded data using the dictionary parser
    return parse_agent_card_from_dict(data)


async def fetch_agent_card_from_url(
    url: str,
    http_client: Optional[httpx.AsyncClient] = None
) -> AgentCard:
    """
    Fetches, parses, and validates an Agent Card from a URL.

    Args:
        url: The URL to fetch the Agent Card JSON from.
        http_client: An optional httpx.AsyncClient instance for making the request.
                     If None, a temporary client will be created.

    Returns:
        A validated AgentCard Pydantic model instance.

    Raises:
        AgentCardFetchError: If there's a network error, the server returns a non-2xx
                             status code, or the response is not valid JSON.
                             This wraps httpx.RequestError and httpx.HTTPStatusError.
        AgentCardValidationError: If the fetched JSON content fails Agent Card validation.
        AgentCardError: For other unexpected errors during fetch/parse.
    """
    client_to_use: httpx.AsyncClient

    async def _fetch(client: httpx.AsyncClient):
        try:
            response = await client.get(url) # Can raise httpx.RequestError

            # Check for non-successful status codes first
            response.raise_for_status() # Can raise httpx.HTTPStatusError

            # Try parsing the JSON response
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                # --- MODIFIED: Raise AgentCardFetchError here ---
                # This was the missing part causing the test failure
                raise AgentCardFetchError(f"Failed to decode JSON response from URL '{url}': {e}") from e
                # --- END MODIFIED ---

            # Validate the fetched data using the dictionary parser
            # Let AgentCardValidationError or AgentCardError propagate if raised
            return parse_agent_card_from_dict(data)

        # --- REVISED Exception Handling Order (Again) ---
        except httpx.HTTPStatusError as e:
            # Wrap HTTP status errors (4xx/5xx) specifically
            raise AgentCardFetchError(
                f"Failed to fetch Agent Card from URL '{url}'. Status: {e.response.status_code}. Response: {e.response.text}",
                status_code=e.response.status_code,
                response_body=e.response.text
            ) from e
        except httpx.RequestError as e:
            # Wrap network-related errors (DNS, connection, timeout, etc.)
            raise AgentCardFetchError(f"Network error fetching Agent Card from URL '{url}': {e}") from e
        # --- ADDED: Catch AgentCardFetchError specifically ---
        except AgentCardFetchError:
             # Re-raise fetch errors (like the JSON decode one) directly
             raise
        # --- END ADDED ---
        except AgentCardValidationError:
             # Re-raise validation errors directly if they came from parse_agent_card_from_dict
             raise
        except AgentCardError as e:
             # Re-raise other card-specific parsing errors
             raise AgentCardError(f"An error occurred processing the Agent Card data from '{url}': {e}") from e
        # --- ADDED: Catch respx errors specifically if respx is available ---
        except RespxMockError as e:
             # Let respx errors propagate during testing
             raise e
        # --- END ADDED ---
        except Exception as e:
            # Catch any other unexpected errors during fetch/parse and wrap
            raise AgentCardError(f"An unexpected error occurred fetching/processing Agent Card from '{url}': {e}") from e
        # --- END REVISED ---

    if http_client:
        return await _fetch(http_client)
    else:
        # Create a temporary client if none was provided
        async with httpx.AsyncClient() as temp_client:
            return await _fetch(temp_client)

#
