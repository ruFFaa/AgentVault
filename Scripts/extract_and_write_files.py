# scripts/extract_and_write_files.py (v10.3 - Output Written Test Files - Adapted for Extension Filter)
import re
import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Optional

# --- Configuration ---
# NEW: Set the desired file extension filter.
# Use "all" to extract all files, or specify an extension like ".md", ".py", ".txt"
FILE_EXTENSION_FILTER = "all"  # Options: "all", ".md", ".txt", ".py", etc.

# Regex to find START or CREATE markers. Handles optional newline after marker.
START_MARKER_PATTERN = re.compile(
    r"---\s*(START OF FILE|CREATE_FILE):\s*(.*?)\s*---\s*\n?", # Optional newline after marker
    re.MULTILINE
)
# Template for end marker regex - more flexible with whitespace
END_MARKER_TEMPLATE = r"---\s*END OF FILE:\s*{}\s*---"

# Regex to find and remove code fences, handling more variations
CODE_FENCE_PATTERN = re.compile(
    r"^\s*```(?:[a-zA-Z]*)?(?:\s*language=[\"']?[a-zA-Z]+[\"']?)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL | re.MULTILINE
)

# Regex for pre-processing spacing between blocks
BLOCK_SPACING_PATTERN = re.compile(
    r"(---\s*END OF FILE:.*?---)"
    r"\s*"
    r"(---\s*(?:START|CREATE)_FILE:.*?---)",
    re.MULTILINE | re.DOTALL
)

# --- NEW: Marker for written test files ---
WRITTEN_TEST_FILE_MARKER = "WRITTEN_TEST_FILE:"


# --- Helper Functions ---
def ensure_dir_exists(file_path: Path) -> None:
    """Creates parent directories for a file if they don't exist."""
    dir_path = file_path.parent
    if dir_path and not dir_path.exists():
        print(f"  Creating directory: {dir_path}")
        os.makedirs(dir_path, exist_ok=True)

def normalize_path(path_str: str) -> str:
    """Normalizes path string to use forward slashes and strip extra whitespace."""
    normalized = path_str.strip().replace('\\', '/')
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
    return normalized

def write_file(target_path: Path, content: str, action: str) -> bool:
    """Writes content to the target file path, ensuring final newline."""
    try:
        ensure_dir_exists(target_path)
        with open(target_path, 'wb') as f:
            normalized_content = "\n".join(content.splitlines())
            if normalized_content and not normalized_content.endswith('\n'):
                normalized_content += "\n"
            elif not normalized_content:
                 pass
            f.write(normalized_content.encode('utf-8'))

        chars_count = len(content)
        action_word = 'Created' if action == 'CREATE_FILE' else 'Wrote'
        print(f"  Successfully {action_word} {target_path} ({chars_count} chars extracted)")
        return True
    except IOError as e:
        print(f"  ERROR: Could not write file {target_path}. Check permissions. Error: {e}")
        return False
    except Exception as e:
        print(f"  ERROR: Unexpected error writing file {target_path}: {e}")
        return False

def is_path_safe(path_str: str, project_root: Path) -> Tuple[bool, Optional[str]]:
    """Validates if a path is safe to write to."""
    path_str = normalize_path(path_str)
    if os.path.isabs(path_str):
        return False, f"Absolute path detected: '{path_str}'. Only relative paths are allowed."
    if '..' in path_str or path_str.startswith('/'):
        return False, f"Potential directory traversal detected in path: '{path_str}'."
    target_path = (project_root / path_str).resolve()
    try:
        resolved_root = project_root.resolve()
        if not str(target_path).startswith(str(resolved_root)):
            return False, f"Resolved path '{target_path}' is outside project root '{resolved_root}'."
    except Exception as e:
        return False, f"Could not resolve paths for security check: {e}."
    return True, None

def process_content(raw_content: str) -> str:
    """Process the raw content to remove code fences if present."""
    if not raw_content.strip():
        return ""
    stripped_content = raw_content.strip()
    fence_match = CODE_FENCE_PATTERN.match(stripped_content)
    if fence_match:
        content = fence_match.group(1)
        print("  (Code fences detected and removed)")
    else:
        content = raw_content.strip()
    return content

def extract_file_blocks(input_text: str) -> List[Dict]:
    """Extracts all file blocks from the input text."""
    file_blocks = []
    start_matches = list(START_MARKER_PATTERN.finditer(input_text))
    if not start_matches:
        print("ERROR: No valid '--- START OF FILE:' or '--- CREATE_FILE:' markers found.")
        return []
    print(f"Found {len(start_matches)} potential file block(s) to process.")
    for i, start_match in enumerate(start_matches):
        action = start_match.group(1).strip()
        relative_path_str = start_match.group(2).strip()
        content_start_index = start_match.end()
        print(f"\nProcessing Block {i+1}: Action: {action}, Path: {relative_path_str}")
        escaped_path = re.escape(relative_path_str)
        end_marker_regex_str = END_MARKER_TEMPLATE.format(escaped_path)
        end_marker_pattern = re.compile(end_marker_regex_str, re.MULTILINE)
        end_match = end_marker_pattern.search(input_text, content_start_index)
        if not end_match:
            print(f"  ERROR: Could not find matching '--- END OF FILE: {relative_path_str} ---' marker. Skipping block.")
            continue
        content_end_index = end_match.start()
        raw_content = input_text[content_start_index:content_end_index]
        processed_content = process_content(raw_content)
        file_blocks.append({
            'action': action,
            'path': relative_path_str,
            'raw_content': raw_content,
            'content': processed_content
        })
        print(f"  Content length: {len(processed_content)} chars")
    return file_blocks

# --- Main Logic ---
def process_ai_output(input_text: str, project_root_dir: Path, force_overwrite: bool = False) -> bool:
    """
    Parses AI output, extracts file blocks based on FILE_EXTENSION_FILTER,
    writes them, and prints markers for written test files.
    """
    print(f"\nProcessing AI output against project root: {project_root_dir}")
    if not project_root_dir.is_dir():
        print(f"ERROR: Project root directory does not exist: {project_root_dir}")
        return False

    # Normalize filter setting for comparison
    normalized_filter = FILE_EXTENSION_FILTER.strip().lower()
    if normalized_filter != "all" and not normalized_filter.startswith('.'):
         print(f"WARNING: File extension filter '{FILE_EXTENSION_FILTER}' should ideally start with a '.'. Adjusting comparison.")
         # No adjustment needed for Path.suffix comparison, but good to warn.

    processed_text = BLOCK_SPACING_PATTERN.sub(r"\1\n\2", input_text)
    if processed_text != input_text:
        print("INFO: Pre-processed AI output to ensure newlines between file blocks.")

    file_blocks = extract_file_blocks(processed_text)
    if not file_blocks:
        return False

    success_count = 0
    failure_count = 0
    skipped_filter_count = 0 # Counter for files skipped due to filter
    written_test_files_count = 0 # Counter for test files

    for block in file_blocks:
        action = block['action']
        relative_path_str = block['path']
        content = block['content']

        # --- NEW: File Extension Filtering Logic ---
        if normalized_filter != "all":
            file_path_obj = Path(relative_path_str)
            file_extension = file_path_obj.suffix.lower() # Gets extension like '.txt', or '' if no extension

            # Compare the file's extension with the filter
            if file_extension != normalized_filter:
                print(f"  INFO: Skipping '{relative_path_str}' - extension '{file_extension}' does not match filter '{FILE_EXTENSION_FILTER}'.")
                skipped_filter_count += 1
                continue # Skip processing this block
        # --- END NEW ---

        is_safe, error_msg = is_path_safe(relative_path_str, project_root_dir)
        if not is_safe:
            print(f"  ERROR: {error_msg} Skipping.")
            failure_count += 1
            continue

        normalized_relative_path = normalize_path(relative_path_str)
        target_path = (project_root_dir / normalized_relative_path).resolve()

        write_success = False
        should_skip = False

        if action == "CREATE_FILE":
            if target_path.exists() and not force_overwrite:
                print(f"  WARNING: File '{target_path}' already exists. Skipping creation (use --force to overwrite).")
                should_skip = True
            elif target_path.exists() and force_overwrite:
                print(f"  INFO: File '{target_path}' exists, overwriting due to --force flag.")
                write_success = write_file(target_path, content, action)
            else:
                write_success = write_file(target_path, content, action)
        elif action == "START OF FILE":
            write_success = write_file(target_path, content, action)
        else:
            print(f"  ERROR: Unknown action '{action}' for path '{relative_path_str}'. Skipping.")
            write_success = False

        if should_skip:
            # If skipped due to existing file (not filter), count as failure/skipped
            failure_count += 1 # Or adjust counting logic if needed, keeping simple for now
            continue # Skip counting success and marker printing

        if write_success:
            success_count += 1
            # --- NEW: Check if it's a test file and print marker ---
            # Use the normalized relative path for the check and output
            if normalized_relative_path.startswith("tests/"):
                print(f"{WRITTEN_TEST_FILE_MARKER}{normalized_relative_path}")
                written_test_files_count += 1
            # --- END NEW ---
        else:
            # Only count as failure if writing actually failed, not if skipped by filter/force flag logic above
             if not should_skip: # Check if it wasn't skipped for other reasons
                failure_count += 1


    print(f"\n--- Processing Summary ---")
    print(f"Total File Blocks Found: {len(file_blocks)}")
    if normalized_filter != "all":
        print(f"Filter Applied: '{FILE_EXTENSION_FILTER}'")
        print(f"Skipped by Filter: {skipped_filter_count}")
    print(f"Successfully Written/Created: {success_count}")
    print(f"Skipped (Exists/Unsafe/Error): {failure_count}") # Adjusted label slightly
    if written_test_files_count > 0:
        print(f"Test Files Written/Created: {written_test_files_count}")
    print(f"--------------------------")

    # Consider a run successful if at least one file was processed successfully OR
    # if all relevant files were processed (even if some were skipped by filter)
    # and there were no actual errors.
    # Let's keep the original success condition for minimal changes:
    # Success if blocks were found and no failures occurred during writing/safety checks.
    if len(file_blocks) > 0 and failure_count == 0:
         # Also check if *any* files passed the filter if a filter was active
        if normalized_filter == "all" or success_count > 0 or (skipped_filter_count > 0 and success_count == 0 and failure_count == 0):
             # If filter active, success means no errors, even if all matching files were skipped (e.g. by --force)
             # or if all files were filtered out but no errors occurred. Let's refine this:
             # Success = No actual write/safety errors occurred.
             return True
        # If a filter was active and *all* blocks were skipped *only* by the filter, it's not really a failure.
        # Let's simplify: Success means no *errors* occurred for the files attempted.
        # return True # Original logic might be best here to avoid complexity.
    # Let's stick to the original definition of success: blocks found and no write/safety failures.
    if len(file_blocks) > 0 and failure_count == 0:
       return True

    return False

# --- Command Line Interface ---
def main():
    parser = argparse.ArgumentParser(
        description="Processes AI-generated output, writes files based on extension filter, and marks written test files."
    )
    parser.add_argument("input_file", type=str, help="Path to the text file containing the AI's output.")
    parser.add_argument("project_root", type=str, help="Path to the root directory of the target project.")
    parser.add_argument("-f", "--force", action="store_true", help="Force overwrite files for CREATE_FILE action.")
    # Optional: Add argument to override FILE_EXTENSION_FILTER from command line
    # parser.add_argument("-ext", "--extension_filter", type=str, default=FILE_EXTENSION_FILTER, help=f"File extension filter (e.g., '.md', 'all'). Default: '{FILE_EXTENSION_FILTER}'")

    args = parser.parse_args()

    # Optional: If using the command-line argument override
    # global FILE_EXTENSION_FILTER
    # FILE_EXTENSION_FILTER = args.extension_filter

    ai_output_text = ""
    input_file_path = Path(args.input_file)
    if not input_file_path.is_file():
        print(f"ERROR: Input file not found: {input_file_path}")
        sys.exit(1)
    try:
        print(f"Reading AI output from: {input_file_path}")
        with open(input_file_path, 'r', encoding='utf-8') as f:
            ai_output_text = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read input file {input_file_path}: {e}")
        sys.exit(1)

    project_root_path = Path(args.project_root)
    success = process_ai_output(ai_output_text, project_root_path, args.force)

    if success:
        print("\nFile extraction and writing completed successfully (respecting filter).")
        sys.exit(0)
    else:
        print("\nFile extraction and writing completed with errors, warnings, or no matching files found/processed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
