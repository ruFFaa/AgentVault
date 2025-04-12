import click
from typing import List, Any
from rich.console import Console
from rich.table import Table

# Instantiate a Rich Console for enhanced terminal output (like tables)
console = Console()

def display_error(message: str):
    """Displays an error message to stderr in red."""
    click.secho(f"ERROR: {message}", fg='red', err=True)

def display_warning(message: str):
    """Displays a warning message to stdout in yellow."""
    click.secho(f"WARNING: {message}", fg='yellow')

def display_success(message: str):
    """Displays a success message to stdout in green."""
    click.secho(f"SUCCESS: {message}", fg='green')

def display_info(message: str):
    """Displays an informational message to stdout."""
    click.echo(message)

def display_table(title: str, columns: List[str], data: List[List[Any]]):
    """
    Displays data in a formatted table using Rich.

    Args:
        title: The title of the table.
        columns: A list of strings representing the column headers.
        data: A list of lists, where each inner list represents a row.
              Items in the inner list correspond to the columns.
    """
    if not data:
        display_info(f"{title}: No data to display.")
        return

    table = Table(title=title, show_header=True, header_style="bold magenta")

    # Add columns
    for col_name in columns:
        # Add sensible defaults, adjust justify/style as needed later
        table.add_column(col_name, style="dim", justify="left")

    # Add rows
    try:
        for row in data:
            # Convert all items in the row to string for safety before adding
            table.add_row(*[str(item) for item in row])
    except Exception as e:
        display_error(f"Failed to add row data to table: {e}")
        # Optionally print raw data on error
        # display_info("Raw data:")
        # for row in data:
        #     display_info(str(row))
        return # Stop if table formatting fails

    # Print the table to the console
    console.print(table)
