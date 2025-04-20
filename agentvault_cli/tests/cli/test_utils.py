import pytest
from unittest.mock import patch, MagicMock, ANY
from rich.table import Table

# Import the module to test
from agentvault_cli import utils

# --- Test display_table ---

@patch('agentvault_cli.utils.console.print')
@patch('agentvault_cli.utils.display_info')
def test_display_table_with_data(mock_display_info: MagicMock, mock_console_print: MagicMock):
    """Test display_table with valid data prints a table."""
    title = "Test Table"
    columns = ["ID", "Name", "Value", "Active"]
    data = [
        [1, "Item A", 123.45, True],
        [2, "Item B", 678, False],
        [3, "Item C", None, True], # Test None value
    ]

    utils.display_table(title, columns, data)

    # Assert console.print was called once
    mock_console_print.assert_called_once()
    # Assert the argument passed to console.print was a rich Table instance
    call_args, _ = mock_console_print.call_args
    assert isinstance(call_args[0], Table)
    # Assert the table has the correct title
    assert call_args[0].title == title
    # Assert display_info was NOT called (because data was not empty)
    mock_display_info.assert_not_called()

@patch('agentvault_cli.utils.console.print')
@patch('agentvault_cli.utils.display_info')
def test_display_table_empty_data(mock_display_info: MagicMock, mock_console_print: MagicMock):
    """Test display_table with empty data calls display_info."""
    title = "Empty Table"
    columns = ["Col1", "Col2"]
    data = []

    utils.display_table(title, columns, data)

    # Assert display_info was called once with the correct message
    mock_display_info.assert_called_once_with(f"{title}: No data to display.")
    # Assert console.print was NOT called
    mock_console_print.assert_not_called()

@patch('agentvault_cli.utils.console.print')
@patch('agentvault_cli.utils.display_info')
@patch('agentvault_cli.utils.display_error')
@patch('rich.table.Table.add_row') # Patch the method that might fail
def test_display_table_add_row_error(
    mock_add_row: MagicMock,
    mock_display_error: MagicMock,
    mock_display_info: MagicMock,
    mock_console_print: MagicMock
):
    """Test display_table handles exceptions during add_row."""
    title = "Error Table"
    columns = ["A", "B"]
    data = [["row1_a", "row1_b"], ["row2_a", "row2_b"]]
    error_message = "Simulated add_row failure"

    # Configure the mock add_row to raise an exception on the first call
    mock_add_row.side_effect = Exception(error_message)

    utils.display_table(title, columns, data)

    # Assert display_error was called once
    mock_display_error.assert_called_once()
    # Check that the error message includes the exception detail
    call_args, _ = mock_display_error.call_args
    assert f"Failed to add row data to table: {error_message}" in call_args[0]

    # Assert console.print was NOT called because the function should return early
    mock_console_print.assert_not_called()
    # Assert display_info was NOT called (data wasn't empty)
    mock_display_info.assert_not_called()
