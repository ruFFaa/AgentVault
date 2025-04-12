"""
Utilities for loading, parsing, and validating A2A Agent Cards.
"""

import json
import httpx
import pydantic
from pathlib import Path
from typing import Dict, Any, Optional

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
        AgentCardValidationError: If the data fails Pydantic validation.
        AgentCardError: For any other unexpected errors during parsing.
    """
    try:
        # Use Pydantic's model_validate for v2 syntax
        agent_card = AgentCard.model_validate(data)
        return agent_card
    except pydantic.ValidationError as e:
        # Wrap Pydantic's validation error in our custom exception
        raise AgentCardValidationError(f"Agent Card validation failed: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during parsing
        raise AgentCardError(f"An unexpected error occurred parsing the Agent Card data: {e}") from e


def load_agent_card_from_file(file_path: Path) -> AgentCard:
    """
    Loads, parses, and validates an Agent Card from a local JSON file.

    Args:
        file_path: A pathlib.Path object pointing to the JSON file.

    Returns:
        A validated AgentCard Pydantic model instance.

    Raises:
        AgentCardError: If the file does not exist, is not a file,
                        cannot be read, or is not valid JSON.
        AgentCardValidationError: If the loaded JSON data fails validation
                                  against the AgentCard model.
    """
    if not isinstance(file_path, Path):
        # Ensure input is a Path object for consistency
        try:
            file_path = Path(file_path)
        except TypeError as e:
             raise AgentCardError(f"Invalid file path type provided: {type(file_path)}. Must be Path or str.") from e

    if not file_path.exists():
        raise AgentCardError(f"Agent Card file not found at: {file_path}")
    if not file_path.is_file():
        raise AgentCardError(f"Path exists but is not a file: {file_path}")

    try:
        with file_path.open('r', encoding='utf-8') as f:
            raw_data = f.read()
            data = json.loads(raw_data)
    except IOError as e:
        raise AgentCardError(f"Could not read Agent Card file: {file_path}. Error: {e}") from e
    except json.JSONDecodeError as e:
        raise AgentCardError(f"Invalid JSON in Agent Card file: {file_path}. Error: {e}") from e
    except Exception as e:
        raise AgentCardError(f"An unexpected error occurred loading the Agent Card file: {e}") from e

    # Reuse the dictionary parsing function for validation
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
        AgentCardFetchError: If there's a network error, an unsuccessful HTTP status code,
                             or the response is not valid JSON.
        AgentCardValidationError: If the fetched JSON data fails validation
                                  against the AgentCard model.
    """
    client_to_use = http_client or httpx.AsyncClient()
    should_close_client = not http_client # Only close if we created it

    try:
        response = await client_to_use.get(url)

        # Check for HTTP errors (4xx or 5xx)
        response.raise_for_status()

        # Attempt to parse the JSON response
        data = response.json()

    except httpx.RequestError as e:
        # Handles connection errors, timeouts, etc.
        raise AgentCardFetchError(f"Network error fetching Agent Card from {url}: {e}") from e
    except httpx.HTTPStatusError as e:
        # Handles 4xx/5xx responses after raise_for_status()
        raise AgentCardFetchError(
            f"Failed to fetch Agent Card from {url}. "
            f"Status code: {e.response.status_code}. Response: {e.response.text}"
        ) from e
    except json.JSONDecodeError as e:
        # Handle cases where the response is not valid JSON
        raise AgentCardFetchError(
            f"Invalid JSON received from Agent Card URL: {url}. Error: {e}. Response text: {response.text}"
        ) from e
    except Exception as e:
         raise AgentCardFetchError(f"An unexpected error occurred fetching the Agent Card: {e}") from e
    finally:
        # Ensure the temporary client is closed if we created it
        if should_close_client:
            await client_to_use.aclose()

    # Reuse the dictionary parsing function for validation
    # This will raise AgentCardValidationError if validation fails
    try:
        return parse_agent_card_from_dict(data)
    except AgentCardValidationError as e:
         # Re-raise validation errors specifically from parsing the fetched data
         raise AgentCardValidationError(f"Validation failed for Agent Card fetched from {url}: {e}") from e
    except AgentCardError as e:
         # Catch other parsing errors from parse_agent_card_from_dict
         raise AgentCardFetchError(f"Error parsing Agent Card fetched from {url}: {e}") from e


#
