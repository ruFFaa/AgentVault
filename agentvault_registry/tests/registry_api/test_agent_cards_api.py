import pytest
import uuid
import datetime
from unittest.mock import patch, MagicMock, ANY, AsyncMock
from typing import Optional, List, Dict, Any, Tuple, AsyncGenerator # Added AsyncGenerator

from fastapi.testclient import TestClient # Import sync client
from fastapi import status
import pydantic # Import pydantic for ValidationError

# Imports are now relative to the src dir added to path by pytest.ini
from agentvault_registry import schemas, models, security # Import security for optional dep

# Use fixtures defined in conftest.py implicitly
API_BASE_URL = "/api/v1/agent-cards"

# --- Test POST /agent-cards/ ---
# ... (create tests remain the same) ...
def test_create_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # Use fixture
    override_get_current_developer: None,
    valid_agent_card_data_dict: dict,
    mocker
):
    """Test successful creation of an agent card."""
    # Mock the validation within CRUD to succeed
    mock_validated_card_model = MagicMock()
    mock_validated_card_model.model_dump.return_value = valid_agent_card_data_dict
    mock_validate_patch = mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        return_value=mock_validated_card_model
    )

    # Mock the CRUD function return value
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_developer.is_verified = False # Set explicit state
    mock_db_return = models.AgentCard(
        id=uuid.uuid4(), # Generate a new UUID for the return
        developer_id=mock_developer.id,
        card_data=valid_agent_card_data_dict,
        name=valid_agent_card_data_dict["name"],
        description=valid_agent_card_data_dict.get("description"),
        is_active=True,
        created_at=now,
        updated_at=now,
        developer=mock_developer # Attach the mock developer
    )
    mock_create = mocker.patch(
        "agentvault_registry.crud.agent_card.create_agent_card",
        new_callable=AsyncMock, return_value=mock_db_return
    )
    # Mock refresh if needed
    mock_db_session.refresh = AsyncMock()

    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)

    response = sync_test_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json'),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    # Validate the response against the schema
    validated_response = schemas.AgentCardRead.model_validate(response_data)
    assert validated_response.name == valid_agent_card_data_dict["name"]
    assert validated_response.developer_id == mock_developer.id
    assert validated_response.developer_is_verified == mock_developer.is_verified # is_verified should be False by default
    assert validated_response.card_data == valid_agent_card_data_dict

    # Assert mocks were called
    mock_create.assert_awaited_once()
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs['db'] is mock_db_session
    assert call_kwargs['developer_id'] == mock_developer.id
    assert call_kwargs['card_create'].card_data == valid_agent_card_data_dict


def test_create_agent_card_auth_fail(
    sync_test_client: TestClient,
    override_get_current_developer_forbidden: None,
    valid_agent_card_data_dict: dict
):
    """Test create endpoint with missing/invalid auth header."""
    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)
    response = sync_test_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json')
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_agent_card_validation_fail(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    valid_agent_card_data_dict: dict,
    mocker
):
    """Test create endpoint when CRUD validation raises ValueError."""
    error_message = "Invalid card data from CRUD"
    # Mock the CRUD function itself to raise the error
    mock_create = mocker.patch(
        "agentvault_registry.crud.agent_card.create_agent_card",
        new_callable=AsyncMock, side_effect=ValueError(error_message) # Use AsyncMock
    )

    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)

    response = sync_test_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json'),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Check the detail uses the message from the ValueError raised by CRUD
    assert error_message in response.json()["detail"]
    mock_create.assert_awaited_once() # Ensure create was called (and raised)


# --- Test GET /agent-cards/ (List) ---
def test_list_agent_cards_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successful listing of agent cards (no filters)."""
    mock_cards = [mock_agent_card_db_object] * 3
    total_items = 15
    mock_list = mocker.patch(
        "agentvault_registry.crud.agent_card.list_agent_cards",
        new_callable=AsyncMock, return_value=(mock_cards, total_items) # Use AsyncMock
    )

    response = sync_test_client.get(API_BASE_URL + "/")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardListResponse.model_validate(response_data)
    assert len(response_data["items"]) == 3
    assert response_data["items"][0]["name"] == mock_agent_card_db_object.name
    assert response_data["pagination"]["total_items"] == total_items
    assert response_data["pagination"]["limit"] == 100
    assert response_data["pagination"]["offset"] == 0

    mock_list.assert_awaited_once_with(
        db=mock_db_session, skip=0, limit=100, active_only=True, search=None, tags=None, developer_id=None
    )


@pytest.mark.parametrize(
    "skip, limit, active_only, search, tags", # Added tags parameter
    [
        (10, 50, True, None, None),
        (0, 25, False, None, ["weather"]), # Test with tags
        (0, 100, True, "test", None),
        (20, 10, False, "search term", ["tool", "internal"]), # Test with multiple tags
    ]
)
def test_list_agent_cards_with_params(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mocker,
    skip: int, limit: int, active_only: bool, search: Optional[str], tags: Optional[List[str]] # Added tags parameter
):
    """Test listing with various query parameters."""
    mock_list = mocker.patch(
        "agentvault_registry.crud.agent_card.list_agent_cards",
        new_callable=AsyncMock, return_value=([], 0) # Use AsyncMock
    )

    # Build query params, handling list for tags
    query_params = {"skip": skip, "limit": limit, "active_only": active_only}
    if search is not None:
        query_params["search"] = search
    if tags is not None:
        query_params['tags'] = tags

    response = sync_test_client.get(API_BASE_URL + "/", params=query_params) # Use query_params

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_awaited_once_with(
        db=mock_db_session, skip=skip, limit=limit, active_only=active_only, search=search, tags=tags, developer_id=None
    )

# --- Tag Filtering Tests ---
def test_list_agent_cards_filter_single_tag(sync_test_client: TestClient, mock_db_session: MagicMock, mocker):
    """Test filtering by a single tag."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards", new_callable=AsyncMock, return_value=([], 0))
    tag_to_filter = "weather"

    response = sync_test_client.get(API_BASE_URL + "/", params={"tags": tag_to_filter})

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_awaited_once_with(db=mock_db_session, skip=0, limit=100, active_only=True, search=None, tags=[tag_to_filter], developer_id=None)

def test_list_agent_cards_filter_multiple_tags(sync_test_client: TestClient, mock_db_session: MagicMock, mocker):
    """Test filtering by multiple tags."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards", new_callable=AsyncMock, return_value=([], 0))
    tags_to_filter = ["tool", "internal"]

    response = sync_test_client.get(API_BASE_URL + "/", params={"tags": tags_to_filter}) # Pass list

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_awaited_once_with(db=mock_db_session, skip=0, limit=100, active_only=True, search=None, tags=tags_to_filter, developer_id=None)

def test_list_agent_cards_filter_tag_no_match(sync_test_client: TestClient, mock_db_session: MagicMock, mocker):
    """Test filtering by a tag that returns no results."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards", new_callable=AsyncMock, return_value=([], 0))
    tag_to_filter = "nonexistent-tag"

    response = sync_test_client.get(API_BASE_URL + "/", params={"tags": tag_to_filter})

    assert response.status_code == status.HTTP_200_OK
    resp_data = response.json()
    assert resp_data["items"] == []
    assert resp_data["pagination"]["total_items"] == 0
    mock_list.assert_awaited_once_with(db=mock_db_session, skip=0, limit=100, active_only=True, search=None, tags=[tag_to_filter], developer_id=None)

def test_list_agent_cards_filter_tags_and_search(sync_test_client: TestClient, mock_db_session: MagicMock, mocker):
    """Test filtering by both tags and search term."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards", new_callable=AsyncMock, return_value=([], 0))
    tags_to_filter = ["nlp"]
    search_term = "summary"

    response = sync_test_client.get(API_BASE_URL + "/", params={"tags": tags_to_filter, "search": search_term})

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_awaited_once_with(db=mock_db_session, skip=0, limit=100, active_only=True, search=search_term, tags=tags_to_filter, developer_id=None)

# --- Tests for owned_only filter ---
def test_list_agent_cards_owned_only_success(
    sync_test_client: TestClient, mock_db_session: MagicMock, mock_developer: models.Developer,
    # --- MODIFIED: Use the correct optional override fixture ---
    override_get_current_developer_optional: None,
    # --- END MODIFIED ---
    mocker
):
    """Test filtering by owned_only=true with valid authentication."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards", new_callable=AsyncMock, return_value=([], 0))

    # --- ADDED: Configure mock DB execute result for the auth check ---
    # This simulates get_developer_by_plain_api_key finding the developer
    async def mock_dev_scalar_gen():
        yield mock_developer
    mock_db_session.execute.return_value.scalars.return_value = mock_dev_scalar_gen()
    # --- END ADDED ---

    response = sync_test_client.get(API_BASE_URL + "/", params={"owned_only": True}, headers={"X-Api-Key": "fake-key"})

    assert response.status_code == status.HTTP_200_OK # Expect 200 now
    mock_list.assert_awaited_once_with(
        db=mock_db_session, skip=0, limit=100, active_only=True, search=None, tags=None, developer_id=mock_developer.id # Check developer_id is passed
    )

def test_list_agent_cards_owned_only_no_auth(
    sync_test_client: TestClient, mock_db_session: MagicMock,
    # --- MODIFIED: Use the correct optional override fixture ---
    override_get_current_developer_optional_none: None,
     # --- END MODIFIED ---
    mocker
):
    """Test filtering by owned_only=true without authentication."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards") # No need for AsyncMock here

    response = sync_test_client.get(API_BASE_URL + "/", params={"owned_only": True}) # No X-Api-Key header

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Authentication required" in response.json()["detail"]
    mock_list.assert_not_called() # CRUD should not be called

def test_list_agent_cards_owned_only_false_with_auth(
    sync_test_client: TestClient, mock_db_session: MagicMock, mock_developer: models.Developer,
    # --- MODIFIED: Use the correct optional override fixture ---
    override_get_current_developer_optional: None,
    # --- END MODIFIED ---
    mocker
):
    """Test owned_only=false with authentication (should ignore auth)."""
    mock_list = mocker.patch("agentvault_registry.crud.agent_card.list_agent_cards", new_callable=AsyncMock, return_value=([], 0))

    # --- ADDED: Configure mock DB execute result for the auth check (even though not used for filtering) ---
    async def mock_dev_scalar_gen():
        yield mock_developer
    mock_db_session.execute.return_value.scalars.return_value = mock_dev_scalar_gen()
    # --- END ADDED ---

    response = sync_test_client.get(API_BASE_URL + "/", params={"owned_only": False}, headers={"X-Api-Key": "fake-key"})

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_awaited_once_with(
        db=mock_db_session, skip=0, limit=100, active_only=True, search=None, tags=None, developer_id=None # developer_id should be None
    )


# --- Test GET /agent-cards/{card_id} (Read) ---
# ... (get, update, delete tests remain the same) ...
def test_get_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_agent_card_db_object: models.AgentCard, # Use the fixture
    mock_developer: models.Developer, # Use the fixture
    mocker
):
    """Test successfully retrieving a single agent card."""
    card_id = mock_agent_card_db_object.id
    mock_developer.is_verified = False # Set a specific state for this test
    mock_agent_card_db_object.developer = mock_developer

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )

    response = sync_test_client.get(f"{API_BASE_URL}/{card_id}")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    validated_response = schemas.AgentCardRead.model_validate(response_data)
    assert validated_response.id == card_id
    assert validated_response.name == mock_agent_card_db_object.name
    assert validated_response.developer_id == mock_developer.id
    assert validated_response.developer_is_verified is False

    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)


def test_get_agent_card_includes_developer_verified(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mocker
):
    """Test GET /agent-cards/{card_id} includes developer_is_verified."""
    test_dev = models.Developer(id=5, name="Verified Dev", api_key_hash="abc", is_verified=True) # Set verified True
    test_card_id = uuid.uuid4()
    test_card_data = {"name": "Verified Agent Card", "description": "Desc", "schemaVersion": "1.0", "humanReadableId": "vd/vac", "agentVersion": "1", "url": "http://localhost", "provider": {"name": "vd"}, "capabilities": {"a2aVersion": "1"}, "authSchemes": [{"scheme": "none"}]}
    mock_card_db = models.AgentCard(
        id=test_card_id,
        developer_id=test_dev.id,
        card_data=test_card_data,
        name=test_card_data["name"],
        description=test_card_data["description"],
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
        developer=test_dev # Assign the related developer object
    )

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_card_db
    )

    response = sync_test_client.get(f"{API_BASE_URL}/{test_card_id}")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    validated_response = schemas.AgentCardRead.model_validate(response_data)

    assert validated_response.id == test_card_id
    assert validated_response.developer_id == test_dev.id
    assert "developer_is_verified" in response_data # Check key exists
    assert validated_response.developer_is_verified is True # Check the value

    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=test_card_id)


def test_get_agent_card_not_found(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mocker
):
    """Test retrieving a non-existent agent card."""
    card_id = uuid.uuid4()
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=None # Use AsyncMock
    )

    response = sync_test_client.get(f"{API_BASE_URL}/{card_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)


# --- Test PUT /agent-cards/{card_id} (Update) ---

@patch("agentvault_registry.crud.agent_card._agentvault_lib_available", True)
def test_update_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    valid_agent_card_data_dict: dict,
    mocker
):
    """Test successful update of an agent card."""
    card_id = mock_agent_card_db_object.id
    mock_agent_card_db_object.developer_id = mock_developer.id # Ensure ownership matches
    mock_developer.is_verified = True # Set initial state for developer
    mock_agent_card_db_object.developer = mock_developer # Attach developer

    updated_data_dict = valid_agent_card_data_dict.copy()
    updated_data_dict["description"] = "Updated description via API."
    update_schema = schemas.AgentCardUpdate(card_data=updated_data_dict, is_active=False)

    # Create a mock for the *updated* card state returned by CRUD
    updated_mock_card = models.AgentCard(
        id=mock_agent_card_db_object.id, developer_id=mock_agent_card_db_object.developer_id,
        card_data=updated_data_dict, name=updated_data_dict["name"],
        description=updated_data_dict["description"], is_active=False, # Reflect update
        created_at=mock_agent_card_db_object.created_at,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
        developer=mock_developer # Attach developer to returned object too
    )

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object
    )
    mock_update = mocker.patch(
        "agentvault_registry.crud.agent_card.update_agent_card",
        new_callable=AsyncMock, return_value=updated_mock_card
    )
    # Mock refresh if needed
    mock_db_session.refresh = AsyncMock()

    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    validated_response = schemas.AgentCardRead.model_validate(response_data)
    assert validated_response.id == card_id
    assert validated_response.description == "Updated description via API."
    assert validated_response.is_active is False
    assert validated_response.developer_id == mock_developer.id
    assert validated_response.developer_is_verified is True

    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_awaited_once()
    call_kwargs = mock_update.call_args.kwargs
    assert call_kwargs['db'] is mock_db_session
    assert call_kwargs['db_card'] is mock_agent_card_db_object
    assert call_kwargs['card_update'].card_data == updated_data_dict
    assert call_kwargs['card_update'].is_active is False


def test_update_agent_card_not_found(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mocker
):
    """Test updating a non-existent agent card."""
    card_id = uuid.uuid4()
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=None # Use AsyncMock
    )
    update_schema = schemas.AgentCardUpdate(is_active=False)

    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)


def test_update_agent_card_forbidden(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # The authenticated developer
    mock_other_developer: models.Developer, # The owner of the card
    override_get_current_developer: None, # Overrides to return mock_developer
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test updating a card owned by another developer."""
    card_id = mock_agent_card_db_object.id
    # Set the card's owner to be the *other* developer
    mock_agent_card_db_object.developer_id = mock_other_developer.id
    mock_agent_card_db_object.developer = mock_other_developer # Attach correct owner

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    mock_update = mocker.patch("agentvault_registry.crud.agent_card.update_agent_card")
    update_schema = schemas.AgentCardUpdate(is_active=False)

    # The override ensures the request is authenticated as mock_developer
    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in response.json()["detail"]
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_not_called()


@patch("agentvault_registry.crud.agent_card._agentvault_lib_available", True)
def test_update_agent_card_validation_fail(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # Need owner for ownership check
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test update endpoint when CRUD validation raises ValueError."""
    card_id = mock_agent_card_db_object.id
    mock_agent_card_db_object.developer_id = mock_developer.id # Ensure ownership matches
    mock_agent_card_db_object.developer = mock_developer # Attach developer

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # Mock the CRUD update function to raise the error
    error_message = "Invalid updated card data from CRUD"
    mock_update = mocker.patch(
        "agentvault_registry.crud.agent_card.update_agent_card",
        new_callable=AsyncMock, side_effect=ValueError(error_message) # Use AsyncMock
    )

    update_schema = schemas.AgentCardUpdate(card_data={"invalid": "data"})

    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Check the detail uses the message from the ValueError raised by CRUD
    assert error_message in response.json()["detail"]
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_awaited_once() # Ensure update was called (and raised the error)


# --- Test DELETE /agent-cards/{card_id} (Soft Delete) ---
def test_delete_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # Need owner for ownership check
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successful soft deletion of an agent card."""
    card_id = mock_agent_card_db_object.id
    mock_agent_card_db_object.developer_id = mock_developer.id # Ensure ownership matches
    mock_agent_card_db_object.developer = mock_developer # Attach developer

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    mock_delete = mocker.patch(
        "agentvault_registry.crud.agent_card.delete_agent_card",
        new_callable=AsyncMock, return_value=True # Use AsyncMock
    )

    response = sync_test_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_delete.assert_awaited_once_with(db=mock_db_session, card_id=card_id)


def test_delete_agent_card_not_found(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mocker
):
    """Test deleting a non-existent agent card."""
    card_id = uuid.uuid4()
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=None # Use AsyncMock
    )
    mock_delete = mocker.patch("agentvault_registry.crud.agent_card.delete_agent_card")

    response = sync_test_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_delete.assert_not_called()


def test_delete_agent_card_forbidden(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # Authenticated user
    mock_other_developer: models.Developer, # Card owner
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test deleting a card owned by another developer."""
    card_id = mock_agent_card_db_object.id
    # Set the card's owner to be the *other* developer
    mock_agent_card_db_object.developer_id = mock_other_developer.id
    mock_agent_card_db_object.developer = mock_other_developer # Attach owner

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    mock_delete = mocker.patch("agentvault_registry.crud.agent_card.delete_agent_card")

    # The override ensures the request is authenticated as mock_developer
    response = sync_test_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in response.json()["detail"]
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_delete.assert_not_called()


def test_delete_agent_card_db_error(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # Need owner for ownership check
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test delete endpoint when CRUD delete function returns False (DB error)."""
    card_id = mock_agent_card_db_object.id
    mock_agent_card_db_object.developer_id = mock_developer.id # Ensure ownership matches
    mock_agent_card_db_object.developer = mock_developer # Attach developer

    # Mock get_agent_card to return the object twice (once for ownership, once for final check)
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, side_effect=[mock_agent_card_db_object, mock_agent_card_db_object] # Use AsyncMock
    )

    # Mock delete_agent_card to return False (simulating DB error)
    mock_delete = mocker.patch(
        "agentvault_registry.crud.agent_card.delete_agent_card",
        new_callable=AsyncMock, return_value=False # Use AsyncMock
    )

    response = sync_test_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to deactivate" in response.json()["detail"]
    # get_agent_card is called twice: once initially, once inside the error handling
    assert mock_get.await_count == 2
    mock_delete.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
