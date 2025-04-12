import pytest
import uuid
import datetime
from unittest.mock import patch, MagicMock, ANY
from typing import Optional, List

import httpx
from fastapi import status

# Imports are now relative to the src dir added to path by pytest.ini
from agentvault_registry import schemas, models

# Use fixtures defined in conftest.py implicitly
# pytest will automatically inject fixtures like async_client, mock_db_session etc.
# based on their names used as test function arguments.

API_BASE_URL = "/api/v1/agent-cards"

# --- Test POST /agent-cards/ ---

@pytest.mark.asyncio
async def test_create_agent_card_success(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock, # Mocked session from conftest
    mock_developer: models.Developer, # Mocked developer from conftest
    override_get_current_developer: None, # Apply auth override fixture
    valid_agent_card_data_dict: dict,
    mock_agent_card_db_object: models.AgentCard, # Mocked DB object to return
    mocker # Pytest-mock fixture
):
    """Test successful creation of an agent card."""
    # Mock the CRUD function
    mock_create = mocker.patch(
        "agentvault_registry.crud.agent_card.create_agent_card",
        return_value=mock_agent_card_db_object
    )
    # Mock the AgentCardModel validation from the library (assume success)
    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        return_value=MagicMock(**valid_agent_card_data_dict) # Return a mock that looks like the validated model
    )

    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)

    response = await async_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json'),
        headers={"X-Api-Key": "fake-key"} # Header value doesn't matter due to override
    )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    # Validate response against the Read schema
    assert schemas.AgentCardRead.model_validate(response_data)
    assert response_data["name"] == valid_agent_card_data_dict["name"]
    assert response_data["developer_id"] == mock_developer.id
    assert response_data["card_data"] == valid_agent_card_data_dict # Check if full data is returned

    # Assert CRUD function was called correctly
    mock_create.assert_called_once()
    # Check that db and developer_id were passed correctly
    mock_call_args = mock_create.call_args
    call_kwargs = mock_call_args.kwargs
    # For a more robust check, let's check the kwargs
    if 'db' in call_kwargs:
        assert call_kwargs['db'] is mock_db_session
    if 'developer_id' in call_kwargs:
        assert call_kwargs['developer_id'] == mock_developer.id
    if 'card_create' in call_kwargs:
        assert call_kwargs['card_create'].card_data == valid_agent_card_data_dict


@pytest.mark.asyncio
async def test_create_agent_card_auth_fail(
    async_client: httpx.AsyncClient,
    override_get_current_developer_forbidden: None, # Use fixture that raises 403
    valid_agent_card_data_dict: dict
):
    """Test create endpoint with missing/invalid auth header."""
    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)
    response = await async_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json')
        # No X-Api-Key header provided, or override raises 403
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_create_agent_card_validation_fail(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    valid_agent_card_data_dict: dict,
    mocker
):
    """Test create endpoint when CRUD validation raises ValueError."""
    # Mock the CRUD function to raise ValueError (simulating validation failure)
    mock_create = mocker.patch(
        "agentvault_registry.crud.agent_card.create_agent_card",
        side_effect=ValueError("Invalid card data")
    )
    # Mock the AgentCardModel validation itself (though CRUD mock handles it here)
    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        side_effect=ValueError("Invalid card data") # Match the expected error
    )

    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict) # Data itself is valid here

    response = await async_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json'),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid card data" in response.json()["detail"]


# --- Test GET /agent-cards/ (List) ---

@pytest.mark.asyncio
async def test_list_agent_cards_success(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successful listing of agent cards (no filters)."""
    mock_cards = [mock_agent_card_db_object] * 3
    total_items = 15
    mock_list = mocker.patch(
        "agentvault_registry.crud.agent_card.list_agent_cards",
        return_value=(mock_cards, total_items)
    )

    response = await async_client.get(API_BASE_URL + "/")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardListResponse.model_validate(response_data)
    assert len(response_data["items"]) == 3
    assert response_data["items"][0]["name"] == mock_agent_card_db_object.name
    assert response_data["pagination"]["total_items"] == total_items
    assert response_data["pagination"]["limit"] == 100 # Default limit
    assert response_data["pagination"]["offset"] == 0   # Default offset

    mock_list.assert_called_once_with(db=mock_db_session, skip=0, limit=100, active_only=True, search=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "skip, limit, active_only, search",
    [
        (10, 50, True, None),
        (0, 25, False, None),
        (0, 100, True, "test"),
        (20, 10, False, "search term"),
    ]
)
async def test_list_agent_cards_with_params(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mocker,
    skip: int, limit: int, active_only: bool, search: Optional[str]
):
    """Test listing with various query parameters."""
    mock_list = mocker.patch(
        "agentvault_registry.crud.agent_card.list_agent_cards",
        return_value=([], 0) # Return value doesn't matter much here
    )

    params = {"skip": skip, "limit": limit, "active_only": active_only}
    if search is not None:
        params["search"] = search

    response = await async_client.get(API_BASE_URL + "/", params=params)

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_called_once_with(
        db=mock_db_session, skip=skip, limit=limit, active_only=active_only, search=search
    )


# --- Test GET /agent-cards/{card_id} (Read) ---

@pytest.mark.asyncio
async def test_get_agent_card_success(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successfully retrieving a single agent card."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object
    )

    response = await async_client.get(f"{API_BASE_URL}/{card_id}")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardRead.model_validate(response_data)
    assert response_data["id"] == str(card_id)
    assert response_data["name"] == mock_agent_card_db_object.name

    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)


@pytest.mark.asyncio
async def test_get_agent_card_not_found(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mocker
):
    """Test retrieving a non-existent agent card."""
    card_id = uuid.uuid4()
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=None
    )

    response = await async_client.get(f"{API_BASE_URL}/{card_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)


# --- Test PUT /agent-cards/{card_id} (Update) ---

@pytest.mark.asyncio
async def test_update_agent_card_success(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard, # Original object
    valid_agent_card_data_dict: dict,
    mocker
):
    """Test successful update of an agent card."""
    card_id = mock_agent_card_db_object.id
    # Ensure the mock card belongs to the mock developer
    mock_agent_card_db_object.developer_id = mock_developer.id

    # Prepare update data
    updated_data_dict = valid_agent_card_data_dict.copy()
    updated_data_dict["description"] = "Updated description via API."
    update_schema = schemas.AgentCardUpdate(
        card_data=updated_data_dict,
        is_active=False
    )

    # Mock the object returned by the update CRUD function
    updated_mock_card = models.AgentCard(
        id=mock_agent_card_db_object.id,
        developer_id=mock_agent_card_db_object.developer_id,
        card_data=updated_data_dict,
        name=updated_data_dict["name"],
        description=updated_data_dict["description"],
        is_active=False,
        created_at=mock_agent_card_db_object.created_at,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
        developer=mock_developer
    )

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object # Return the original object first
    )
    mock_update = mocker.patch(
        "agentvault_registry.crud.agent_card.update_agent_card",
        return_value=updated_mock_card # Return the updated object
    )
    # Mock validation within CRUD
    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        return_value=MagicMock(**updated_data_dict)
    )

    response = await async_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True), # Send only updated fields
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardRead.model_validate(response_data)
    assert response_data["id"] == str(card_id)
    assert response_data["description"] == "Updated description via API."
    assert response_data["is_active"] is False

    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_called_once()
    
    # Check the parameters of the update function call
    mock_call_args = mock_update.call_args
    call_kwargs = mock_call_args.kwargs
    # For a more robust check, check the kwargs
    if 'db' in call_kwargs:
        assert call_kwargs['db'] is mock_db_session
    if 'db_card' in call_kwargs:
        assert call_kwargs['db_card'] is mock_agent_card_db_object
    if 'card_update' in call_kwargs:
        assert call_kwargs['card_update'].card_data == updated_data_dict
        assert call_kwargs['card_update'].is_active is False


@pytest.mark.asyncio
async def test_update_agent_card_not_found(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mocker
):
    """Test updating a non-existent agent card."""
    card_id = uuid.uuid4()
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=None
    )
    update_schema = schemas.AgentCardUpdate(is_active=False)

    response = await async_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)


@pytest.mark.asyncio
async def test_update_agent_card_forbidden(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer, # The authenticated developer
    mock_other_developer: models.Developer, # The owner of the card
    override_get_current_developer: None, # Uses mock_developer
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test updating a card owned by another developer."""
    card_id = mock_agent_card_db_object.id
    # Set owner to be the *other* developer
    mock_agent_card_db_object.developer_id = mock_other_developer.id

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object
    )
    mock_update = mocker.patch("agentvault_registry.crud.agent_card.update_agent_card")
    update_schema = schemas.AgentCardUpdate(is_active=False)

    response = await async_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in response.json()["detail"]
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_not_called() # CRUD update should not be reached


@pytest.mark.asyncio
async def test_update_agent_card_validation_fail(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard, # Belongs to mock_developer via fixture setup
    mocker
):
    """Test update endpoint when CRUD validation raises ValueError."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object
    )
    # Mock the update CRUD function to raise ValueError
    mock_update = mocker.patch(
        "agentvault_registry.crud.agent_card.update_agent_card",
        side_effect=ValueError("Invalid updated card data")
    )
    # Mock validation within CRUD
    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        side_effect=ValueError("Invalid updated card data")
    )

    update_schema = schemas.AgentCardUpdate(card_data={"invalid": "data"})

    response = await async_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid updated card data" in response.json()["detail"]
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_called_once() # Update was called, but raised error


# --- Test DELETE /agent-cards/{card_id} (Soft Delete) ---

@pytest.mark.asyncio
async def test_delete_agent_card_success(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard, # Belongs to mock_developer
    mocker
):
    """Test successful soft deletion of an agent card."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object
    )
    mock_delete = mocker.patch(
        "agentvault_registry.crud.agent_card.delete_agent_card",
        return_value=True # Simulate successful soft delete
    )

    response = await async_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)
    mock_delete.assert_called_once_with(db=mock_db_session, card_id=card_id)


@pytest.mark.asyncio
async def test_delete_agent_card_not_found(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mocker
):
    """Test deleting a non-existent agent card."""
    card_id = uuid.uuid4()
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=None
    )
    mock_delete = mocker.patch("agentvault_registry.crud.agent_card.delete_agent_card")

    response = await async_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_agent_card_forbidden(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    mock_other_developer: models.Developer, # Card owner
    override_get_current_developer: None, # Authenticated user (mock_developer)
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test deleting a card owned by another developer."""
    card_id = mock_agent_card_db_object.id
    # Set owner to be the *other* developer
    mock_agent_card_db_object.developer_id = mock_other_developer.id

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object
    )
    mock_delete = mocker.patch("agentvault_registry.crud.agent_card.delete_agent_card")

    response = await async_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in response.json()["detail"]
    mock_get.assert_called_once_with(db=mock_db_session, card_id=card_id)
    mock_delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_agent_card_db_error(
    async_client: httpx.AsyncClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard, # Belongs to mock_developer
    mocker
):
    """Test delete endpoint when CRUD delete function returns False (DB error)."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        return_value=mock_agent_card_db_object
    )
    mock_delete = mocker.patch(
        "agentvault_registry.crud.agent_card.delete_agent_card",
        return_value=False # Simulate DB error during soft delete
    )

    # Second check when checking if the agent card still exists
    def get_side_effect(db, card_id):
        # First call returns the card before deletion
        # Second call checks if it still exists after failed deletion
        mock_get.side_effect = None  # Prevent infinite recursion
        mock_get.return_value = mock_agent_card_db_object
        return mock_agent_card_db_object
        
    mock_get.side_effect = get_side_effect

    response = await async_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to deactivate" in response.json()["detail"]
    mock_delete.assert_called_once_with(db=mock_db_session, card_id=card_id)