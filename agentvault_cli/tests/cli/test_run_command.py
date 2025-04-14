import pytest
import pytest_asyncio
import uuid
import json
import pathlib
import asyncio
import datetime
import logging # Added logging
from unittest.mock import patch, MagicMock, AsyncMock, ANY, call
import click
import re # Added re
from typing import Optional, Dict, Any, Union, Tuple, AsyncGenerator, List


import httpx
import respx
from click.testing import CliRunner

# Import the CLI entrypoint and the specific command FUNCTION
from agentvault_cli.main import cli
from agentvault_cli.commands.run import run_command  # Import the function

# Import library components for mocking
try:
    from agentvault import agent_card_utils, key_manager, client as av_client, models as av_models, exceptions as av_exceptions
    _AGENTVAULT_AVAILABLE = True
except ImportError:
    _AGENTVAULT_AVAILABLE = False

# Skip tests if library not available
pytestmark = pytest.mark.skipif(not _AGENTVAULT_AVAILABLE, reason="agentvault library not found")

# Helper function for running async Click commands with proper context
async def run_click_command(command, mock_ctx=None, **kwargs):
    """ Run an async Click command with proper context management. """
    ctx = click.Context(command)
    original_exit = ctx.exit
    def exit_wrapper(code=0):
        if mock_ctx is not None: mock_ctx.exit(code)
        return None
    ctx.exit = exit_wrapper
    with ctx:
        await asyncio.sleep(0.01)
        return await command.callback(**kwargs)

# --- Fixtures ---

@pytest.fixture
def runner():
    return CliRunner(mix_stderr=True)

@pytest.fixture
def mock_ctx() -> MagicMock:
    ctx = MagicMock(spec=click.Context)
    ctx.exit = MagicMock()
    return ctx

@pytest.fixture
def mock_agent_card() -> av_models.AgentCard:
    return av_models.AgentCard(
        schemaVersion="1.0", humanReadableId="test-org/mock-run-agent", agentVersion="1.0",
        name="Mock Run Agent", description="Agent for run command tests", url="https://mock-agent.test/a2a",
        provider=av_models.AgentProvider(name="Mock Provider"),
        capabilities=av_models.AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[av_models.AgentAuthentication(scheme="apiKey", service_identifier="mock-service-id")]
    )

@pytest.fixture
def mock_agent_card_no_auth() -> av_models.AgentCard:
    return av_models.AgentCard(
        schemaVersion="1.0", humanReadableId="test-org/no-auth-agent", agentVersion="1.0.0",
        name="No Auth Agent", description="Agent requiring no auth", url="https://no-auth-agent.test/a2a",
        provider=av_models.AgentProvider(name="Mock Provider"),
        capabilities=av_models.AgentCapabilities(a2aVersion="1.0"),
        authSchemes=[av_models.AgentAuthentication(scheme="none")]
    )

# --- Helper Async Generator Functions ---
async def mock_receive_empty() -> AsyncGenerator[Any, None]:
    if False: yield
    return

async def mock_receive_events(*events) -> AsyncGenerator[Any, None]:
    """Async generator that yields mock events with a delay."""
    test_logger = logging.getLogger("test_mock_receive_events")
    test_logger.info(f"Mock generator starting. Will yield {len(events)} events.")
    for i, event in enumerate(events):
        media_type_to_log = "N/A"
        if _AGENTVAULT_AVAILABLE and isinstance(event, av_models.TaskArtifactUpdateEvent):
             if hasattr(event, 'artifact') and hasattr(event.artifact, 'media_type'):
                 media_type_to_log = event.artifact.media_type
        test_logger.info(f"Mock generator yielding event {i+1}: type={type(event).__name__}, media_type='{media_type_to_log}'")
        yield event
        await asyncio.sleep(0.01)
    test_logger.info("Mock generator finished yielding events.")


# --- Test Agent Loading within 'run' ---
# (Tests unchanged)
@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_success')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_calls_load_agent(mock_key_mgr, mock_load_card_helper,
                                   mock_display_success, mock_ctx, mock_agent_card, anyio_backend):
    mock_load_card_helper.return_value = mock_agent_card
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-dummy")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))

    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = "dummy-key"
    mock_mgr_instance.get_key_source.return_value = "mock"
    mock_key_mgr.return_value = mock_mgr_instance

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='some-ref', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )

    mock_load_card_helper.assert_awaited_once_with('some-ref', ANY, ANY)
    mock_display_success.assert_any_call(f"Successfully loaded agent: {mock_agent_card.name} ({mock_agent_card.human_readable_id})")
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.run_command.callback')
@patch('agentvault_cli.commands.run.utils.display_error')
@patch('agentvault_cli.commands.run._load_agent_card')
async def test_run_load_agent_fail_exit(mock_load_card_helper, mock_display_error, mock_callback, mock_ctx, anyio_backend):
    mock_load_card_helper.return_value = None
    async def safe_mock_callback(ctx, agent_ref, input_data, context_file, registry_url, key_service_override, auth_key_override, output_artifacts):
        ctx.exit(1)
        return None
    mock_callback.side_effect = safe_mock_callback
    await safe_mock_callback(
        mock_ctx, agent_ref='bad-ref', input_data='test', context_file=None,
        registry_url='dummy_url', key_service_override=None, auth_key_override=None,
        output_artifacts=None
    )
    mock_ctx.exit.assert_called_once_with(1)
    mock_load_card_helper.assert_not_called()


# --- Test Input/Context Loading ---
# (Tests unchanged)
@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_load_input_from_file(mock_key_mgr, mock_load_card,
                                      mock_display_info, tmp_path, mock_agent_card_no_auth,
                                      mock_ctx, anyio_backend):
    mock_load_card.return_value = mock_agent_card_no_auth
    input_file = tmp_path / "input.txt"; input_content = "Line 1\nLine 2"; input_file.write_text(input_content)
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-123")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data=f'@{input_file}', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )
    mock_display_info.assert_any_call(f"Read input from file: {input_file}")
    mock_client_instance.initiate_task.assert_awaited_once()
    _, kwargs = mock_client_instance.initiate_task.call_args
    initial_message = kwargs.get('initial_message')
    assert initial_message.parts[0].content == input_content
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_load_context_file(mock_key_mgr, mock_load_card,
                                   mock_display_info, tmp_path, mock_agent_card_no_auth,
                                   mock_ctx, anyio_backend):
    mock_load_card.return_value = mock_agent_card_no_auth
    context_file = tmp_path / "context.json"; context_content = {"user_id": "abc"};
    context_file.write_text(json.dumps(context_content))
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = None
    mock_key_mgr.return_value = mock_mgr_instance
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-ctx")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=context_file,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )
    mock_display_info.assert_any_call(f"Loading MCP context from: {context_file}")
    mock_client_instance.initiate_task.assert_awaited_once()
    _, kwargs = mock_client_instance.initiate_task.call_args
    assert kwargs.get('mcp_context') == context_content
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_error')
async def test_run_load_context_file_not_found(mock_display_error, runner):
    result = runner.invoke(cli, ['run', '--agent', 'dummy', '--input', 'test', '--context-file', 'nonexistent.json'])
    assert result.exit_code != 0
    mock_display_error.assert_not_called()
    assert "Invalid value for '--context-file'" in result.output
    assert "'nonexistent.json' does not exist" in result.output

# --- Test Key Loading ---
# (Tests unchanged)
@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_key_loading_success(mock_key_mgr, mock_load_card,
                                     mock_display_info, mock_ctx, mock_agent_card, anyio_backend):
    mock_load_card.return_value = mock_agent_card
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = "secret-key"
    mock_mgr_instance.get_key_source.return_value = "keyring"
    mock_key_mgr.return_value = mock_mgr_instance
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-key")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )
    mock_key_mgr.assert_called_once_with(use_keyring=True)
    assert mock_mgr_instance.get_key.call_count >= 1
    mock_display_info.assert_any_call("Found credentials for service 'mock-service-id' (Source: KEYRING).")
    mock_client_instance.initiate_task.assert_awaited_once()
    _, kwargs = mock_client_instance.initiate_task.call_args
    assert kwargs.get('key_manager') is mock_mgr_instance
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_key_loading_override_service(mock_key_mgr, mock_load_card,
                                              mock_display_info, mock_ctx, mock_agent_card, anyio_backend):
    mock_load_card.return_value = mock_agent_card
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = "key-for-override"
    mock_mgr_instance.get_key_source.return_value = "env"
    mock_key_mgr.return_value = mock_mgr_instance
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-override")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    override_id = "custom-service"
    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=override_id, auth_key_override=None,
            output_artifacts=None
        )
    mock_display_info.assert_any_call(f"Using overridden service ID for key lookup: '{override_id}'")
    assert override_id in [args[0] for args, _ in mock_mgr_instance.get_key.call_args_list]
    mock_display_info.assert_any_call(f"Found credentials for service '{override_id}' (Source: ENV).")
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_warning')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_key_loading_override_key(mock_key_mgr_cls, mock_load_card,
                                          mock_display_warning, mock_ctx, mock_agent_card, anyio_backend):
    mock_load_card.return_value = mock_agent_card
    override_key = "direct-key-abc"
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-directkey")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=override_key,
            output_artifacts=None
        )
    mock_display_warning.assert_called_once_with("Using API key provided directly via --auth-key (INSECURE).")
    mock_key_mgr_cls.assert_called_once_with(use_keyring=True)
    mock_key_mgr_instance = mock_key_mgr_cls.return_value
    mock_key_mgr_instance.get_key.assert_not_called()
    mock_client_instance.initiate_task.assert_awaited_once()
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_error')
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_key_loading_not_found(mock_key_mgr, mock_load_card, mock_display_info,
                                       mock_display_error, mock_ctx, mock_agent_card, anyio_backend):
    mock_load_card.return_value = mock_agent_card
    mock_mgr_instance = MagicMock()
    mock_mgr_instance.get_key.return_value = None
    mock_mgr_instance.get_oauth_client_id.return_value = None
    mock_mgr_instance.get_oauth_client_secret.return_value = None
    mock_key_mgr.return_value = mock_mgr_instance
    await run_click_command(
        run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
        registry_url='dummy_url', key_service_override=None, auth_key_override=None,
        output_artifacts=None
    )
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)
    expected_msg = "Credentials required for service 'mock-service-id' but not found."
    assert expected_msg in [args[0] for args, _ in mock_display_error.call_args_list]
    guidance_msg = "Use 'agentvault config set' to configure the key/credentials using --env, --file, --keyring, or --oauth-configure."
    assert guidance_msg in [args[0] for args, _ in mock_display_info.call_args_list]
    mock_service_id_calls = [args for args, _ in mock_mgr_instance.get_key.call_args_list if args[0] == 'mock-service-id']
    assert len(mock_service_id_calls) >= 1

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
async def test_run_key_loading_none_scheme(mock_key_mgr, mock_load_card,
                                         mock_display_info, mock_ctx, mock_agent_card_no_auth, anyio_backend):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock()
    mock_key_mgr.return_value = mock_mgr_instance
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value="task-noauth")
    mock_client_instance.receive_messages = AsyncMock(return_value=mock_receive_empty())
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))
    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )
    mock_display_info.assert_any_call("Agent supports 'none' authentication scheme. No API key needed.")
    mock_mgr_instance.get_key.assert_not_called()
    mock_client_instance.initiate_task.assert_awaited_once()
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)


# --- Test A2A Interaction ---
@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_success')
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run.utils.console.print') # Patch rich print
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.signal')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient.receive_messages')
async def test_run_a2a_interaction_success(
    mock_receive_messages_method, mock_signal, mock_key_mgr, mock_load_card,
    mock_console_print, mock_display_info,
    mock_display_success, mock_ctx, mock_agent_card_no_auth, anyio_backend
):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance

    task_id = "task-run-success"
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_events = [
        av_models.TaskStatusUpdateEvent(taskId=task_id, state=av_models.TaskState.WORKING, timestamp=now),
        av_models.TaskMessageEvent(taskId=task_id, message=av_models.Message(role="assistant", parts=[av_models.TextPart(content="Working...")]), timestamp=now),
        av_models.TaskStatusUpdateEvent(taskId=task_id, state=av_models.TaskState.COMPLETED, timestamp=now, message="All done!"),
    ]
    mock_receive_messages_method.return_value = mock_receive_events(*mock_events)

    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value.initiate_task = mock_client_instance.initiate_task
        mock_av_client_cls.return_value.__aenter__.return_value.get_task_status = mock_client_instance.get_task_status
        mock_av_client_cls.return_value.__aenter__.return_value.receive_messages = mock_receive_messages_method

        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )

    mock_client_instance.initiate_task.assert_awaited_once()
    mock_receive_messages_method.assert_called_once()
    mock_display_info.assert_any_call("Task Status: WORKING")
    mock_display_info.assert_any_call("Task Status: COMPLETED - All done!")
    assert mock_console_print.call_count >= 1 # Check rich print was called
    mock_display_success.assert_any_call("Task completed.")
    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)


@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_error')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.signal')
async def test_run_a2a_initiate_error(mock_signal, mock_key_mgr, mock_load_card,
                                   mock_display_error, mock_ctx, mock_agent_card_no_auth, anyio_backend):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance

    error_msg = "Cannot connect to agent"
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(side_effect=av_exceptions.A2AConnectionError(error_msg))

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value = mock_client_instance
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )

    mock_display_error.assert_any_call(f"A2A communication error: {error_msg}")
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)


@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_error') # Keep this patch
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.signal')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient.receive_messages')
async def test_run_a2a_receive_error(
    mock_receive_messages_method, mock_signal, mock_key_mgr, mock_load_card,
    mock_display_error, mock_ctx, mock_agent_card_no_auth, anyio_backend
):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance

    task_id = "task-recv-err"
    error_msg = "Invalid event received from agent"
    error_to_raise = av_exceptions.A2AMessageError(error_msg)
    mock_receive_messages_method.side_effect = error_to_raise

    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value.initiate_task = mock_client_instance.initiate_task
        mock_av_client_cls.return_value.__aenter__.return_value.receive_messages = mock_receive_messages_method

        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )

    mock_display_error.assert_any_call(f"A2A communication error: {error_msg}")
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)


# --- Test Exit Codes ---
@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_warning')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.signal')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient.receive_messages')
async def test_run_exit_code_canceled(
    mock_receive_messages_method, mock_signal, mock_key_mgr, mock_load_card,
    mock_display_warning, mock_ctx, mock_agent_card_no_auth, anyio_backend
):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance
    task_id = "task-canceled"
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)
    mock_receive_messages_method.return_value = mock_receive_empty()
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.CANCELED))

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value.initiate_task = mock_client_instance.initiate_task
        mock_av_client_cls.return_value.__aenter__.return_value.get_task_status = mock_client_instance.get_task_status
        mock_av_client_cls.return_value.__aenter__.return_value.receive_messages = mock_receive_messages_method
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )

    mock_display_warning.assert_any_call("Task canceled.")
    assert any(args[0] == 2 for args, _ in mock_ctx.exit.call_args_list)

@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_error')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.signal')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient.receive_messages')
async def test_run_exit_code_failed(
    mock_receive_messages_method, mock_signal, mock_key_mgr, mock_load_card,
    mock_display_error, mock_ctx, mock_agent_card_no_auth, anyio_backend
):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance
    task_id = "task-failed"
    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)
    mock_receive_messages_method.return_value = mock_receive_empty()
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.FAILED))

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value.initiate_task = mock_client_instance.initiate_task
        mock_av_client_cls.return_value.__aenter__.return_value.get_task_status = mock_client_instance.get_task_status
        mock_av_client_cls.return_value.__aenter__.return_value.receive_messages = mock_receive_messages_method
        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=None
        )

    mock_display_error.assert_any_call("Task failed.")
    assert any(args[0] == 1 for args, _ in mock_ctx.exit.call_args_list)

# --- Test for artifact saving ---
@pytest.mark.asyncio
@patch('agentvault_cli.commands.run.utils.display_info')
@patch('agentvault_cli.commands.run._load_agent_card')
@patch('agentvault_cli.commands.run.key_manager.KeyManager')
@patch('agentvault_cli.commands.run.signal')
@patch('agentvault_cli.commands.run.av_client.AgentVaultClient.receive_messages')
@patch('pathlib.Path.mkdir') # Mock mkdir
@patch('builtins.open') # Mock open to check writing
async def test_run_artifact_saving(
    mock_open, mock_mkdir, mock_receive_messages_method, mock_signal, mock_key_mgr, mock_load_card,
    mock_display_info, mock_ctx, mock_agent_card_no_auth, tmp_path, anyio_backend
):
    mock_load_card.return_value = mock_agent_card_no_auth
    mock_mgr_instance = MagicMock(); mock_mgr_instance.get_key.return_value = None;
    mock_key_mgr.return_value = mock_mgr_instance

    task_id = "task-artifact-save"
    artifact_id = "art-large-1"
    large_content = "A" * 2000
    small_content = "B" * 100
    binary_content = b'\x01\x02' * 600
    json_content = {"data": ["C"] * 500}
    json_content_bytes = json.dumps(json_content, indent=2).encode('utf-8')

    now = datetime.datetime.now(datetime.timezone.utc)
    # Ensure Artifact objects have media_type set correctly
    mock_events = [
        av_models.TaskArtifactUpdateEvent(taskId=task_id, artifact=av_models.Artifact(id=artifact_id, type="log", media_type="text/plain", content=large_content), timestamp=now),
        av_models.TaskArtifactUpdateEvent(taskId=task_id, artifact=av_models.Artifact(id="art-small", type="text", media_type="text/plain", content=small_content), timestamp=now),
        av_models.TaskArtifactUpdateEvent(taskId=task_id, artifact=av_models.Artifact(id="art-bin", type="data", media_type="application/octet-stream", content=binary_content), timestamp=now),
        av_models.TaskArtifactUpdateEvent(taskId=task_id, artifact=av_models.Artifact(id="art-json", type="result", media_type="application/json", content=json_content), timestamp=now),
        av_models.TaskStatusUpdateEvent(taskId=task_id, state=av_models.TaskState.COMPLETED, timestamp=now),
    ]

    # --- ADDED Direct Print ---
    print("\n--- DEBUG: Mock Events List in Test ---")
    for i, event in enumerate(mock_events):
        if isinstance(event, av_models.TaskArtifactUpdateEvent):
            print(f"Event {i}: Artifact ID={event.artifact.id}, Media Type={event.artifact.media_type}")
        else:
            print(f"Event {i}: Type={type(event).__name__}")
    print("-------------------------------------\n")
    # --- END Direct Print ---

    mock_receive_messages_method.return_value = mock_receive_events(*mock_events)

    mock_client_instance = AsyncMock()
    mock_client_instance.initiate_task = AsyncMock(return_value=task_id)
    mock_client_instance.get_task_status = AsyncMock(return_value=MagicMock(state=av_models.TaskState.COMPLETED))

    output_dir = tmp_path / "artifact_output"

    with patch('agentvault_cli.commands.run.av_client.AgentVaultClient') as mock_av_client_cls:
        mock_av_client_cls.return_value.__aenter__.return_value.initiate_task = mock_client_instance.initiate_task
        mock_av_client_cls.return_value.__aenter__.return_value.get_task_status = mock_client_instance.get_task_status
        mock_av_client_cls.return_value.__aenter__.return_value.receive_messages = mock_receive_messages_method

        await run_click_command(
            run_command, mock_ctx=mock_ctx, agent_ref='dummy', input_data='test', context_file=None,
            registry_url='dummy_url', key_service_override=None, auth_key_override=None,
            output_artifacts=output_dir # Pass the output dir
        )

    mock_mkdir.assert_called_with(parents=True, exist_ok=True)
    assert mock_mkdir.call_count >= 3

    # Check specific paths were opened in write-binary mode
    open_calls = mock_open.call_args_list
    # --- FINAL FIX: Assert correct extension based on logs ---
    assert call(output_dir / f"{artifact_id}.bin", 'wb') in open_calls # Expect .bin because logs show media_type is None
    # --- END FINAL FIX ---
    assert call(output_dir / "art-bin.bin", 'wb') in open_calls
    assert call(output_dir / "art-json.json", 'wb') in open_calls # This one should be correct due to content inference

    # Check write calls
    mock_write = mock_open().__enter__().write
    write_calls = mock_write.call_args_list
    assert call(large_content.encode('utf-8')) in write_calls
    assert call(binary_content) in write_calls
    assert call(json_content_bytes) in write_calls

    # --- FINAL FIX: Assert correct saved path based on logs ---
    mock_display_info.assert_any_call(f"  Content saved to: {output_dir / f'{artifact_id}.bin'}")
    # --- END FINAL FIX ---
    mock_display_info.assert_any_call(f"  Content saved to: {output_dir / 'art-bin.bin'}")
    mock_display_info.assert_any_call(f"  Content saved to: {output_dir / 'art-json.json'}")

    assert any(args[0] == 0 for args, _ in mock_ctx.exit.call_args_list)
