import pytest
import pytest_asyncio
import uuid
import json
import pathlib
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock, ANY

import httpx # For mocking registry lookup within run
import respx # For mocking registry lookup within run
from click.testing import CliRunner

# Import CLI entrypoint and command
from agentvault_cli.main import cli
# Import library components for mocking
try:
    from agentvault import agent_card_utils, key_manager, client as av_client, models as av_models, exceptions as av_exceptions
    _AGENTVAULT_AVAILABLE = True
except ImportError:
    _AGENTVAULT_AVAILABLE = False

# Skip tests if library not available
pytestmark = pytest.mark.skipif(not _AGENTVAULT_AVAILABLE, reason="agentvault library not found")

# --- Fixtures ---

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_agent_card() -> av_models.AgentCard:
    """Provides a mock AgentCard object."""
    return av_models.AgentCard(
        schemaVersion="1.0",
        humanReadableId="test-org/mock-run-agent",
        agentVersion="1.0",
        name="Mock Run Agent",
        description="Agent for run command tests",
        url="http://mock-agent.test/a2a",
        provider=av_models.AgentProvider(name="Mock Provider"),
        capabilities=av_models.AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[av_models.AgentAuthentication(scheme="apiKey", service_identifier="mock-service-id")]
    )

@pytest.fixture
def mock_agent_card_no_auth() -> av_models.AgentCard:
    """Provides a mock AgentCard object with 'none' auth."""
    return av_models.AgentCard(
        schemaVersion="1.0",
        humanReadableId="test-org/no-auth-agent",
        agentVersion="1.0",
        name="No Auth Agent",
        description="Agent requiring no auth",
        url="http://no-auth-agent.test/a2a",
        provider=av_models.AgentProvider(name="Mock Provider"),
        capabilities=av_models.AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[av_models.AgentAuthentication(scheme="none")]
    )

# --- Test Agent Loading within 'run' ---

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.agent_card_utils.fetch_agent_card_from_url')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient') # Mock client to prevent execution
async def test_run_load_agent_from_url(mock_av_client, mock_fetch, runner: CliRunner, mock_agent_card: av_models.AgentCard):
    """Test loading agent card from URL."""
    mock_fetch.return_value = mock_agent_card
    agent_url = "http://valid-agent-url.test/card.json"

    result = await runner.invoke_async(cli, ['run', '--agent', agent_url, '--input', 'test'])

    assert result.exit_code == 0 # Should proceed past loading
    assert f"Successfully loaded agent: {mock_agent_card.name}" in result.output
    mock_fetch.assert_awaited_once_with(agent_url)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.agent_card_utils.load_agent_card_from_file')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_load_agent_from_file(mock_av_client, mock_load, runner: CliRunner, mock_agent_card: av_models.AgentCard, tmp_path: pathlib.Path):
    """Test loading agent card from file."""
    mock_load.return_value = mock_agent_card
    agent_file = tmp_path / "card.json"
    agent_file.touch() # Create the dummy file

    result = await runner.invoke_async(cli, ['run', '--agent', str(agent_file), '--input', 'test'])

    assert result.exit_code == 0
    assert f"Successfully loaded agent: {mock_agent_card.name}" in result.output
    mock_load.assert_called_once_with(agent_file)

@pytest.mark.asyncio
@respx.mock
@patch('agentvault_cli.commands.run.agent_card_utils.parse_agent_card_from_dict')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_load_agent_from_id(mock_av_client, mock_parse, runner: CliRunner, mock_agent_card: av_models.AgentCard):
    """Test loading agent card from ID via registry."""
    agent_id = mock_agent_card.human_readable_id
    registry_url = "http://test-registry.dev"
    # Mock the direct lookup endpoint
    lookup_url = f"{registry_url}/api/v1/agent-cards/id/{agent_id}"
    # Assume detail endpoint returns structure containing card_data
    mock_api_response = {
        "id": str(uuid.uuid4()),
        "developer_id": 1,
        "name": mock_agent_card.name,
        "description": mock_agent_card.description,
        "is_active": True,
        "created_at": datetime.datetime.now().isoformat(),
        "updated_at": datetime.datetime.now().isoformat(),
        "card_data": mock_agent_card.model_dump(mode='json') # Embed the card data
    }
    respx.get(lookup_url).mock(return_value=httpx.Response(200, json=mock_api_response))
    mock_parse.return_value = mock_agent_card

    result = await runner.invoke_async(cli, ['run', '--agent', agent_id, '--input', 'test', '--registry', registry_url])

    assert result.exit_code == 0
    assert f"Successfully loaded agent: {mock_agent_card.name}" in result.output
    mock_parse.assert_called_once_with(mock_api_response["card_data"])

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.agent_card_utils.fetch_agent_card_from_url', side_effect=av_exceptions.AgentCardFetchError("Network error"))
async def test_run_load_agent_fetch_error(mock_fetch, runner: CliRunner):
    """Test agent loading failure (fetch error)."""
    result = await runner.invoke_async(cli, ['run', '--agent', 'http://bad-url', '--input', 'test'])
    assert result.exit_code == 1
    assert "ERROR: Failed to load agent card: Network error" in result.output

# --- Test Input/Context Loading ---

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card') # Mock loading
@patch('agentvault_cli.commands.run.key_manager.KeyManager') # Mock key manager
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient') # Mock client
async def test_run_load_input_from_file(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, tmp_path: pathlib.Path, mock_agent_card_no_auth):
    """Test reading input from file using @filepath."""
    mock_load_card.return_value = mock_agent_card_no_auth # Use no-auth card for simplicity
    input_file = tmp_path / "input.txt"
    input_content = "Line 1\nLine 2 from file."
    input_file.write_text(input_content)

    # Mock KeyManager methods used after input loading
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = None # No key needed
    mock_key_mgr.return_value = mock_mgr_instance

    # Mock client methods to prevent full run
    mock_client_instance = MagicMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-123")
    mock_client_instance.receive_messages = AsyncMock(return_value=asyncio.sleep(0)) # Empty async generator
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    mock_av_client.return_value.__aenter__.return_value = mock_client_instance # Mock async context manager

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy-ref', '--input', f'@{input_file}'])

    assert result.exit_code == 0 # Should complete successfully
    assert f"Read input from file: {input_file}" in result.output
    # Check that initiate_task was called with the correct content
    mock_client_instance.initiate_task.assert_awaited_once()
    call_args, _ = mock_client_instance.initiate_task.call_args
    initial_message = call_args[1]['initial_message'] # Get keyword arg
    assert isinstance(initial_message, av_models.Message)
    assert len(initial_message.parts) == 1
    assert isinstance(initial_message.parts[0], av_models.TextPart)
    assert initial_message.parts[0].content == input_content

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_load_context_file(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, tmp_path: pathlib.Path, mock_agent_card_no_auth):
    """Test reading context from file."""
    mock_load_card.return_value = mock_agent_card_no_auth
    context_file = tmp_path / "context.json"
    context_content = {"user_id": "abc", "settings": {"theme": "dark"}}
    context_file.write_text(json.dumps(context_content))

    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = None
    mock_key_mgr.return_value = mock_mgr_instance

    mock_client_instance = MagicMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-ctx")
    mock_client_instance.receive_messages = AsyncMock(return_value=asyncio.sleep(0))
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test', '--context-file', str(context_file)])

    assert result.exit_code == 0
    assert f"Loading MCP context from: {context_file}" in result.output
    # Check initiate_task was called with correct context
    mock_client_instance.initiate_task.assert_awaited_once()
    call_args, _ = mock_client_instance.initiate_task.call_args
    assert call_args[1]['mcp_context'] == context_content

@pytest.mark.asyncio
async def test_run_load_context_file_not_found(runner: CliRunner):
    """Test error when context file doesn't exist."""
    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test', '--context-file', 'nonexistent.json'])
    # Should exit before trying to load agent card if context file specified but not found
    assert result.exit_code != 0 # Click handles Path(exists=True) error
    assert "Invalid value for '--context-file': Path 'nonexistent.json' does not exist." in result.output

# --- Test Key Loading ---

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_key_loading_success(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card):
    """Test successful key loading via KeyManager."""
    mock_load_card.return_value = mock_agent_card # Agent requires apiKey
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = "secret-key-from-manager"
    mock_mgr_instance.get_key_source.return_value = "keyring" # Example source
    mock_key_mgr.return_value = mock_mgr_instance

    mock_client_instance = MagicMock() # Mock client methods
    mock_client_instance.initiate_task = AsyncMock(return_value="task-key")
    mock_client_instance.receive_messages = AsyncMock(return_value=asyncio.sleep(0))
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test'])

    assert result.exit_code == 0
    mock_key_mgr.assert_called_once_with(use_keyring=True)
    # Check service_id derived from card was used
    mock_mgr_instance.get_key.assert_called_once_with('mock-service-id')
    assert "Found API key for service 'mock-service-id' (Source: KEYRING)" in result.output
    # Check initiate_task was called with the manager instance
    mock_client_instance.initiate_task.assert_awaited_once()
    call_args, _ = mock_client_instance.initiate_task.call_args
    assert call_args[1]['key_manager'] is mock_mgr_instance

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_key_loading_override_service(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card):
    """Test overriding service ID for key lookup."""
    mock_load_card.return_value = mock_agent_card
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = "key-for-override"
    mock_mgr_instance.get_key_source.return_value = "env"
    mock_key_mgr.return_value = mock_mgr_instance
    # Mock client methods
    mock_client_instance = MagicMock(); mock_client_instance.initiate_task = AsyncMock(return_value="task-override"); mock_client_instance.receive_messages = AsyncMock(return_value=asyncio.sleep(0)); mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED)); mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    override_id = "custom-service"
    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test', '--key-service', override_id])

    assert result.exit_code == 0
    assert f"Using overridden service ID for key lookup: '{override_id}'" in result.output
    mock_mgr_instance.get_key.assert_called_once_with(override_id)
    assert f"Found API key for service '{override_id}' (Source: ENV)" in result.output

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager') # Still need to patch KeyManager class
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_key_loading_override_key(mock_av_client, mock_key_mgr_cls, mock_load_card, runner: CliRunner, mock_agent_card):
    """Test overriding key directly via --auth-key."""
    mock_load_card.return_value = mock_agent_card
    override_key = "direct-key-abc"
    # Mock client methods
    mock_client_instance = MagicMock(); mock_client_instance.initiate_task = AsyncMock(return_value="task-directkey"); mock_client_instance.receive_messages = AsyncMock(return_value=asyncio.sleep(0)); mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED)); mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test', '--auth-key', override_key])

    assert result.exit_code == 0
    assert "WARNING: Using API key provided directly via --auth-key (INSECURE)." in result.output
    mock_key_mgr_cls.assert_called_once_with(use_keyring=True) # Manager is still instantiated
    # Check that get_key was NOT called on the manager instance
    mock_key_mgr_instance = mock_key_mgr_cls.return_value
    mock_key_mgr_instance.get_key.assert_not_called()
    # Check initiate_task was called (we don't easily check the key used internally by client here, assume client handles it)
    mock_client_instance.initiate_task.assert_awaited_once()

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_key_loading_not_found(mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card):
    """Test error when required key is not found."""
    mock_load_card.return_value = mock_agent_card # Requires key
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = None # Key not found
    mock_key_mgr.return_value = mock_mgr_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test'])

    assert result.exit_code == 1
    assert "ERROR: API key required for service 'mock-service-id' but not found." in result.output
    mock_mgr_instance.get_key.assert_called_once_with('mock-service-id')

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_key_loading_none_scheme(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card_no_auth):
    """Test successful run when agent uses 'none' auth."""
    mock_load_card.return_value = mock_agent_card_no_auth # Does not require key
    mock_mgr_instance = MagicMock()
    mock_key_mgr.return_value = mock_mgr_instance
    # Mock client methods
    mock_client_instance = MagicMock(); mock_client_instance.initiate_task = AsyncMock(return_value="task-noauth"); mock_client_instance.receive_messages = AsyncMock(return_value=asyncio.sleep(0)); mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED)); mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test'])

    assert result.exit_code == 0
    assert "Agent supports 'none' authentication scheme. No API key needed." in result.output
    mock_mgr_instance.get_key.assert_not_called() # get_key should not be called
    mock_client_instance.initiate_task.assert_awaited_once() # Task should still initiate


# --- Test A2A Interaction ---

# Helper to create an async generator for mock events
async def mock_event_stream(*events):
    for event in events:
        yield event
        await asyncio.sleep(0.01) # Simulate small delay

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_a2a_interaction_success(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card_no_auth):
    """Test the full A2A interaction flow on success."""
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None; mock_key_mgr.return_value = mock_mgr_instance
    task_id = "task-run-success"

    # Mock events
    event1 = av_models.TaskStatusUpdateEvent(taskId=task_id, state=av_models.TaskState.RUNNING, timestamp=datetime.datetime.now())
    event2 = av_models.TaskMessageEvent(taskId=task_id, message=av_models.Message(role="assistant", parts=[av_models.TextPart(content="Working on it...")]), timestamp=datetime.datetime.now())
    event3 = av_models.TaskStatusUpdateEvent(taskId=task_id, state=av_models.TaskState.COMPLETED, timestamp=datetime.datetime.now(), message="All done!")

    # Mock client methods
    mock_client_instance = MagicMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)
    # Use helper to create async generator
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_event_stream(event1, event2, event3))
    # Mock final status check
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'Do the thing'])

    assert result.exit_code == 0
    assert f"Task initiated successfully. Task ID: {task_id}" in result.output
    assert "Task Status: RUNNING" in result.output
    assert "Working on it..." in result.output # Check message content
    assert "Task Status: COMPLETED - All done!" in result.output
    assert "Task completed." in result.output
    mock_client_instance.initiate_task.assert_awaited_once()
    mock_client_instance.receive_messages.assert_awaited_once()
    mock_client_instance.get_task_status.assert_awaited_once()


@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_a2a_initiate_error(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card_no_auth):
    """Test handling of A2AError during task initiation."""
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None; mock_key_mgr.return_value = mock_mgr_instance

    # Mock client methods
    mock_client_instance = MagicMock()
    mock_client_instance.initiate_task = AsyncMock(side_effect=av_exceptions.A2AConnectionError("Cannot connect"))
    mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test'])

    assert result.exit_code == 1
    assert "ERROR: A2A communication error: Cannot connect" in result.output
    mock_client_instance.initiate_task.assert_awaited_once()


@pytest.mark.asyncio
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient')
async def test_run_a2a_receive_error(mock_av_client, mock_key_mgr, mock_load_card, runner: CliRunner, mock_agent_card_no_auth):
    """Test handling of A2AError during event receiving."""
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None; mock_key_mgr.return_value = mock_mgr_instance
    task_id = "task-recv-err"

    # Mock client methods
    mock_client_instance = MagicMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)
    # Mock receive_messages to raise an error
    mock_client_instance.receive_messages = AsyncMock(side_effect=av_exceptions.A2AMessageError("Invalid event received"))
    # Mock final status check (might still be called in finally block)
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.FAILED)) # Assume it failed
    mock_av_client.return_value.__aenter__.return_value = mock_client_instance

    result = await runner.invoke_async(cli, ['run', '--agent', 'dummy', '--input', 'test'])

    assert result.exit_code == 1 # Should exit with error code
    assert f"Task initiated successfully. Task ID: {task_id}" in result.output
    assert "ERROR: A2A communication error: Invalid event received" in result.output
    # Final status check might still happen depending on exact error point
    # assert "Final Task State: FAILED" in result.output # Check final state reported

# Note: Testing Ctrl+C handling is complex in automated tests.
# It typically requires sending signals to the process, which CliRunner doesn't directly support.
# Manual testing or more advanced test setups (like using subprocess) might be needed.
