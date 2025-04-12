# scripts/compile_project_to_text.py
import os
import sys
from pathlib import Path
import pathspec # For .gitignore parsing
from typing import List, Set, Optional

# --- Configuration ---
OUTPUT_DIR_NAME = "temp"
OUTPUT_FILENAME = "PPAIallfiles.txt"

# Folders to always exclude (add more as needed)
# Common examples: virtual environments, build artifacts, IDE configs, Git internals
EXCLUDED_DIRS = {
    ".git",
    ".vscode",
    ".idea",
    "__pycache__",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "build",
    "dist",
    "target",
    OUTPUT_DIR_NAME, # Exclude the output directory itself
    "*.pyc", # Example pattern, though pathspec handles this better via .gitignore
    "*.log",
    "*.swp",
    "*.bak",
}

# File marker templates
START_MARKER_TEMPLATE = "--- START OF FILE: {} ---"
END_MARKER_TEMPLATE = "--- END OF FILE: {} ---"
# --- End Configuration ---

def create_output_directory(dir_path: Path):
    """Creates the output directory if it doesn't exist."""
    if not dir_path.exists():
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"INFO: Created directory: {dir_path}")
        except OSError as e:
            print(f"ERROR: Failed to create directory {dir_path}: {e}")
            sys.exit(1)
    elif not dir_path.is_dir():
        print(f"ERROR: Output path '{dir_path}' exists but is not a directory.")
        sys.exit(1)

def load_gitignore(root_dir: Path) -> Optional[pathspec.PathSpec]:
    """Loads .gitignore rules from the root directory."""
    gitignore_path = root_dir / ".gitignore"
    if gitignore_path.is_file():
        try:
            with open(gitignore_path, 'r', encoding='utf-8') as f:
                # Use 'gitwildmatch' which is the standard gitignore syntax
                return pathspec.PathSpec.from_lines('gitwildmatch', f)
        except IOError as e:
            print(f"WARNING: Could not read .gitignore file at {gitignore_path}: {e}")
    else:
        print("INFO: No .gitignore file found in the root directory.")
    return None

def is_excluded(relative_path: Path, gitignore_spec: Optional[pathspec.PathSpec], excluded_dirs_set: Set[str]) -> bool:
    """
    Checks if a relative path should be excluded based on .gitignore
    or the explicit EXCLUDED_DIRS set.
    """
    # 1. Check against .gitignore patterns
    # pathspec works with string paths relative to the root where .gitignore is
    if gitignore_spec and gitignore_spec.match_file(str(relative_path)):
        # print(f"DEBUG: Excluded by .gitignore: {relative_path}")
        return True

    # 2. Check against explicitly excluded directory/file names/patterns
    # Check if any part of the path matches an excluded directory name
    # Also check if the filename itself matches an excluded pattern/name
    path_parts = set(relative_path.parts)
    if not path_parts.isdisjoint(excluded_dirs_set):
         # print(f"DEBUG: Excluded by EXCLUDED_DIRS (part): {relative_path}")
         return True
    # Check the filename itself against the set (for patterns like *.log)
    # Note: Simple set check is basic. For complex patterns, more logic needed,
    # but .gitignore handles most complex cases. This covers simple names/extensions.
    if relative_path.name in excluded_dirs_set:
        # print(f"DEBUG: Excluded by EXCLUDED_DIRS (name): {relative_path}")
        return True
    # Check simple suffix patterns
    for pattern in excluded_dirs_set:
        if pattern.startswith("*.") and relative_path.name.endswith(pattern[1:]):
            # print(f"DEBUG: Excluded by EXCLUDED_DIRS (suffix pattern): {relative_path}")
            return True


    # 3. Check if the path is within the output directory itself
    # This check is also implicitly covered if OUTPUT_DIR_NAME is in EXCLUDED_DIRS
    # but explicit check can be clearer if needed.
    # if relative_path.parts and relative_path.parts[0] == OUTPUT_DIR_NAME:
    #     return True


    return False

def find_project_files(root_dir: Path, gitignore_spec: Optional[pathspec.PathSpec], excluded_dirs_set: Set[str]) -> List[Path]:
    """
    Finds all files in the project directory, excluding specified ones.
    Returns a list of Path objects relative to the root_dir.
    """
    included_files = []
    print(f"INFO: Scanning project files in: {root_dir}")
    file_count = 0
    excluded_count = 0

    for item_path in root_dir.rglob('*'): # Recursively find all items
        if item_path.is_file():
            file_count += 1
            try:
                relative_path = item_path.relative_to(root_dir)
                if not is_excluded(relative_path, gitignore_spec, excluded_dirs_set):
                    included_files.append(relative_path)
                else:
                    excluded_count += 1
            except ValueError:
                # Should not happen with rglob starting from root_dir, but safety check
                print(f"WARNING: Could not determine relative path for {item_path}. Skipping.")
                excluded_count += 1
        elif item_path.is_dir():
             # Check if the directory itself is excluded to potentially skip walking it
             # (Optimization - rglob doesn't easily support skipping subtrees based on parent)
             # For now, we filter files individually.
             pass


    print(f"INFO: Scan complete. Found {file_count} files total.")
    print(f"INFO: Excluded {excluded_count} files based on rules.")
    print(f"INFO: Will include {len(included_files)} files in the output.")
    return sorted(included_files) # Sort for consistent output order

def compile_project_files(root_dir: Path, output_file_path: Path):
    """
    Finds relevant project files, reads their content, and writes
    it to the output file with markers.
    """
    print(f"\nINFO: Starting compilation process...")
    gitignore_spec = load_gitignore(root_dir)
    excluded_dirs_set = set(EXCLUDED_DIRS) # Use a set for faster lookups

    # Find all files to include
    files_to_compile = find_project_files(root_dir, gitignore_spec, excluded_dirs_set)

    if not files_to_compile:
        print("WARNING: No files found to compile after applying exclusions.")
        # Create an empty file or a file with a note? Let's create one with a note.
        try:
            with open(output_file_path, 'w', encoding='utf-8') as outfile:
                 outfile.write("--- No project files found or included based on exclusion rules. ---\n")
            print(f"INFO: Created empty output file with note: {output_file_path}")
        except IOError as e:
            print(f"ERROR: Could not write note to output file {output_file_path}: {e}")
        return # Stop processing

    print(f"\nINFO: Compiling {len(files_to_compile)} files into: {output_file_path}")
    files_processed = 0
    files_failed = 0

    try:
        # Open the output file in write mode ('w')
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            for relative_path in files_to_compile:
                absolute_path = root_dir / relative_path
                # Use forward slashes for markers, regardless of OS
                relative_path_str = relative_path.as_posix()
                print(f"  -> Processing: {relative_path_str}")

                try:
                    # Read file content - use errors='ignore' for robustness
                    content = absolute_path.read_text(encoding='utf-8', errors='ignore')

                    # Write start marker
                    outfile.write(START_MARKER_TEMPLATE.format(relative_path_str) + "\n")
                    # Write content
                    outfile.write(content)
                    # Ensure a newline before the end marker if content wasn't empty
                    if content and not content.endswith('\n'):
                        outfile.write("\n")
                    # Write end marker
                    outfile.write(END_MARKER_TEMPLATE.format(relative_path_str) + "\n\n") # Add extra newline for spacing

                    files_processed += 1

                except Exception as read_err:
                    error_msg = f"ERROR: Could not read file '{relative_path_str}': {read_err}"
                    print(f"    {error_msg}")
                    # Write an error message to the output file instead of content
                    outfile.write(START_MARKER_TEMPLATE.format(relative_path_str) + "\n")
                    outfile.write(f"*** {error_msg} ***\n")
                    outfile.write(END_MARKER_TEMPLATE.format(relative_path_str) + "\n\n")
                    files_failed += 1

        print(f"\n--- Compilation Summary ---")
        print(f"Successfully processed: {files_processed} files")
        print(f"Failed to read:       {files_failed} files")
        print(f"Total files attempted: {len(files_to_compile)}")
        print(f"Output saved to:      '{output_file_path}'")
        print(f"--------------------------")


    except IOError as write_err:
        print(f"ERROR: Could not open or write to output file '{output_file_path}': {write_err}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during compilation: {e}")
        sys.exit(1)


def main():
    """
    Main function to set up paths and start the compilation.
    Assumes the script is run from the project's root directory.
    """
    project_root = Path.cwd() # Get current working directory as project root
    print(f"INFO: Using project root: {project_root}")

    output_dir = project_root / OUTPUT_DIR_NAME
    output_file = output_dir / OUTPUT_FILENAME

    # Ensure the output directory exists
    create_output_directory(output_dir)

    # Start the compilation process
    compile_project_files(project_root, output_file)

    if os.path.exists(output_file):
         print("\nSUCCESS: Project compilation finished.")
         sys.exit(0)
    else:
         print("\nERROR: Output file was not created.")
         sys.exit(1)


if __name__ == "__main__":
    main()
