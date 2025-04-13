import pytest
import uuid
import datetime
# --- MODIFIED: Import AsyncMock ---
from unittest.mock import patch, MagicMock, ANY, AsyncMock
# --- END MODIFIED ---
from typing import Optional, List

from fastapi.testclient import TestClient # Import sync client
from fastapi import status

# Imports are now relative to the src dir added to path by pytest.ini
from agentvault_registry import schemas, models

# Use fixtures defined in conftest.py implicitly
API_BASE_URL = "/api/v1/agent-cards"

# --- Test POST /agent-cards/ ---

def test_create_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_developer: models.Developer,
    override_get_current_developer: None,
    valid_agent_card_data_dict: dict,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successful creation of an agent card."""
    mock_create = mocker.patch(
        "agentvault_registry.crud.agent_card.create_agent_card",
        # Mock needs to be awaitable if CRUD is async
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock here
    )
    # mock_create.assert_awaited = AsyncMock() # No longer needed with new_callable

    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        return_value=MagicMock(**valid_agent_card_data_dict)
    )

    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)

    response = sync_test_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json'),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert schemas.AgentCardRead.model_validate(response_data)
    assert response_data["name"] == valid_agent_card_data_dict["name"]
    assert response_data["developer_id"] == mock_developer.id
    assert response_data["card_data"] == valid_agent_card_data_dict

    # Use assert_awaited_once with AsyncMock
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
    mock_create = mocker.patch(
        "agentvault_registry.crud.agent_card.create_agent_card",
        new_callable=AsyncMock, side_effect=ValueError("Invalid card data") # Use AsyncMock
    )
    # mock_create.assert_awaited = AsyncMock() # No longer needed

    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        side_effect=ValueError("Invalid card data")
    )

    create_schema = schemas.AgentCardCreate(card_data=valid_agent_card_data_dict)

    response = sync_test_client.post(
        API_BASE_URL + "/",
        json=create_schema.model_dump(mode='json'),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid card data" in response.json()["detail"]


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
    # mock_list.assert_awaited = AsyncMock() # No longer needed

    response = sync_test_client.get(API_BASE_URL + "/")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardListResponse.model_validate(response_data)
    assert len(response_data["items"]) == 3
    assert response_data["items"][0]["name"] == mock_agent_card_db_object.name
    assert response_data["pagination"]["total_items"] == total_items
    assert response_data["pagination"]["limit"] == 100
    assert response_data["pagination"]["offset"] == 0

    mock_list.assert_awaited_once_with(db=mock_db_session, skip=0, limit=100, active_only=True, search=None)


@pytest.mark.parametrize(
    "skip, limit, active_only, search",
    [
        (10, 50, True, None),
        (0, 25, False, None),
        (0, 100, True, "test"),
        (20, 10, False, "search term"),
    ]
)
def test_list_agent_cards_with_params(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mocker,
    skip: int, limit: int, active_only: bool, search: Optional[str]
):
    """Test listing with various query parameters."""
    mock_list = mocker.patch(
        "agentvault_registry.crud.agent_card.list_agent_cards",
        new_callable=AsyncMock, return_value=([], 0) # Use AsyncMock
    )
    # mock_list.assert_awaited = AsyncMock() # No longer needed

    params = {"skip": skip, "limit": limit, "active_only": active_only}
    if search is not None:
        params["search"] = search

    response = sync_test_client.get(API_BASE_URL + "/", params=params)

    assert response.status_code == status.HTTP_200_OK
    mock_list.assert_awaited_once_with(
        db=mock_db_session, skip=skip, limit=limit, active_only=active_only, search=search
    )


# --- Test GET /agent-cards/{card_id} (Read) ---

def test_get_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successfully retrieving a single agent card."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed

    response = sync_test_client.get(f"{API_BASE_URL}/{card_id}")

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardRead.model_validate(response_data)
    assert response_data["id"] == str(card_id)
    assert response_data["name"] == mock_agent_card_db_object.name

    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)


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
    # mock_get.assert_awaited = AsyncMock() # No longer needed

    response = sync_test_client.get(f"{API_BASE_URL}/{card_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)


# --- Test PUT /agent-cards/{card_id} (Update) ---

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
    mock_agent_card_db_object.developer_id = mock_developer.id

    updated_data_dict = valid_agent_card_data_dict.copy()
    updated_data_dict["description"] = "Updated description via API."
    update_schema = schemas.AgentCardUpdate(card_data=updated_data_dict, is_active=False)

    updated_mock_card = models.AgentCard(
        id=mock_agent_card_db_object.id, developer_id=mock_agent_card_db_object.developer_id,
        card_data=updated_data_dict, name=updated_data_dict["name"],
        description=updated_data_dict["description"], is_active=False,
        created_at=mock_agent_card_db_object.created_at,
        updated_at=datetime.datetime.now(datetime.timezone.utc), developer=mock_developer
    )

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed
    mock_update = mocker.patch(
        "agentvault_registry.crud.agent_card.update_agent_card",
        new_callable=AsyncMock, return_value=updated_mock_card # Use AsyncMock
    )
    # mock_update.assert_awaited = AsyncMock() # No longer needed
    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        return_value=MagicMock(**updated_data_dict)
    )

    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert schemas.AgentCardRead.model_validate(response_data)
    assert response_data["id"] == str(card_id)
    assert response_data["description"] == "Updated description via API."
    assert response_data["is_active"] is False

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
    # mock_get.assert_awaited = AsyncMock() # No longer needed
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
    mock_developer: models.Developer,
    mock_other_developer: models.Developer,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test updating a card owned by another developer."""
    card_id = mock_agent_card_db_object.id
    mock_agent_card_db_object.developer_id = mock_other_developer.id

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed
    mock_update = mocker.patch("agentvault_registry.crud.agent_card.update_agent_card")
    update_schema = schemas.AgentCardUpdate(is_active=False)

    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authorized" in response.json()["detail"]
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_not_called()


def test_update_agent_card_validation_fail(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test update endpoint when CRUD validation raises ValueError."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed
    mock_update = mocker.patch(
        "agentvault_registry.crud.agent_card.update_agent_card",
        new_callable=AsyncMock, side_effect=ValueError("Invalid updated card data") # Use AsyncMock
    )
    # mock_update.assert_awaited = AsyncMock() # No longer needed
    mocker.patch(
        "agentvault_registry.crud.agent_card.AgentCardModel.model_validate",
        side_effect=ValueError("Invalid updated card data")
    )

    update_schema = schemas.AgentCardUpdate(card_data={"invalid": "data"})

    response = sync_test_client.put(
        f"{API_BASE_URL}/{card_id}",
        json=update_schema.model_dump(mode='json', exclude_unset=True),
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid updated card data" in response.json()["detail"]
    mock_get.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
    mock_update.assert_awaited_once()


# --- Test DELETE /agent-cards/{card_id} (Soft Delete) ---

def test_delete_agent_card_success(
    sync_test_client: TestClient,
    mock_db_session: MagicMock,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test successful soft deletion of an agent card."""
    card_id = mock_agent_card_db_object.id
    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed
    mock_delete = mocker.patch(
        "agentvault_registry.crud.agent_card.delete_agent_card",
        new_callable=AsyncMock, return_value=True # Use AsyncMock
    )
    # mock_delete.assert_awaited = AsyncMock() # No longer needed

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
    # mock_get.assert_awaited = AsyncMock() # No longer needed
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
    mock_other_developer: models.Developer,
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test deleting a card owned by another developer."""
    card_id = mock_agent_card_db_object.id
    mock_agent_card_db_object.developer_id = mock_other_developer.id

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed
    mock_delete = mocker.patch("agentvault_registry.crud.agent_card.delete_agent_card")

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
    override_get_current_developer: None,
    mock_agent_card_db_object: models.AgentCard,
    mocker
):
    """Test delete endpoint when CRUD delete function returns False (DB error)."""
    card_id = mock_agent_card_db_object.id

    mock_get = mocker.patch(
        "agentvault_registry.crud.agent_card.get_agent_card",
        new_callable=AsyncMock, return_value=mock_agent_card_db_object # Use AsyncMock
    )
    # mock_get.assert_awaited = AsyncMock() # No longer needed

    mock_delete = mocker.patch(
        "agentvault_registry.crud.agent_card.delete_agent_card",
        new_callable=AsyncMock, return_value=False # Use AsyncMock
    )
    # mock_delete.assert_awaited = AsyncMock() # No longer needed

    response = sync_test_client.delete(
        f"{API_BASE_URL}/{card_id}",
        headers={"X-Api-Key": "fake-key"}
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Failed to deactivate" in response.json()["detail"]
    assert mock_get.call_count == 2
    mock_delete.assert_awaited_once_with(db=mock_db_session, card_id=card_id)
