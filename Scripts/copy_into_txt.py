# copy_into_txt.py (Adapted for extract_and_write_files.py v10.3+)

import sys
import os

# --- Configuration ---
OUTPUT_DIR_NAME = "temp"
OUTPUT_FILENAME = "compiledprojectfiles.txt"
# --- End Configuration ---

def create_output_directory(dir_path):
    """Creates the output directory if it doesn't exist."""
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            print(f"INFO: Created directory: {dir_path}")
        except OSError as e:
            print(f"ERROR: Failed to create directory {dir_path}: {e}")
            sys.exit(1) # Exit if directory creation fails
    elif not os.path.isdir(dir_path):
        print(f"ERROR: Output path '{dir_path}' exists but is not a directory.")
        sys.exit(1)

def compile_files(input_file_paths, output_file_path):
    """
    Reads content from input files and writes it, along with headers compatible
    with the extractor script, to the specified output file.
    """
    print(f"INFO: Compiling files into: {output_file_path}")
    try:
        # Open the output file in write mode ('w'). This will overwrite the file
        # if it already exists. Use utf-8 encoding for broad compatibility.
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            for file_path in input_file_paths:
                # Use the file path exactly as provided in the argument initially
                raw_file_path = file_path
                # Normalize path separators to forward slashes for markers
                relative_path = raw_file_path.replace('\\', '/')
                print(f"INFO: Processing '{raw_file_path}' as '{relative_path}'...")

                # Check if the input file exists and is actually a file using the raw path
                if not os.path.isfile(raw_file_path):
                    warning_msg = f"WARNING: File not found or is not a regular file: '{raw_file_path}'. Skipping."
                    print(warning_msg)
                    # Write a note about the skipped file to the output using the new marker format
                    # The extractor might ignore this block, but it keeps the format consistent.
                    outfile.write(f"--- START OF FILE: {relative_path} ---\n")
                    outfile.write(f"*** SKIPPED: {warning_msg} ***\n")
                    outfile.write(f"--- END OF FILE: {relative_path} ---\n\n")
                    continue # Move to the next file path

                try:
                    # Read the content of the input file using the raw path
                    with open(raw_file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        # Using errors='ignore' can help prevent crashes if a file
                        # contains characters that don't match the encoding, though
                        # some data might be lost. For source code, utf-8 is usually safe.
                        content = infile.read()

                    # Write a header indicating the start of the file's content (Extractor Format)
                    outfile.write(f"--- START OF FILE: {relative_path} ---\n")
                    # --- REMOVED: Optional markdown code block start ---
                    # outfile.write("```\n")
                    # Write the actual file content
                    outfile.write(content)
                    # --- REMOVED: Optional markdown code block end ---
                    # outfile.write("\n```\n")
                    # Write a footer indicating the end of the file's content (Extractor Format)
                    # Ensure a newline before the end marker if content doesn't end with one
                    if content and not content.endswith('\n'):
                        outfile.write("\n")
                    outfile.write(f"--- END OF FILE: {relative_path} ---\n\n") # Add double newline for separation
                    print(f"  -> Successfully added content from '{raw_file_path}'")

                except Exception as read_err:
                    error_msg = f"ERROR: Could not read file '{raw_file_path}': {read_err}"
                    print(error_msg)
                    # Write an error message to the output file instead of content, using the new marker format
                    outfile.write(f"--- START OF FILE: {relative_path} ---\n")
                    outfile.write(f"*** ERROR READING FILE: {error_msg} ***\n")
                    outfile.write(f"--- END OF FILE: {relative_path} ---\n\n")

        print(f"\nSUCCESS: Compilation complete. Output saved to '{output_file_path}'")

    except IOError as write_err:
        print(f"ERROR: Could not open or write to output file '{output_file_path}': {write_err}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during compilation: {e}")
        sys.exit(1)

def main():
    """
    Main function to parse arguments and orchestrate the file compilation.
    """
    # Get command-line arguments, excluding the script name itself (sys.argv[0])
    input_files = sys.argv[1:]

    # Check if any input files were provided
    if not input_files:
        script_name = os.path.basename(sys.argv[0])
        print(f"Usage: python {script_name} <file1_path> [file2_path ...]")
        print("ERROR: No input files specified.")
        sys.exit(1) # Exit with an error code

    # Define the full path for the output file
    # os.path.join correctly handles path separators for different OS for the *output file itself*
    output_path = os.path.join(OUTPUT_DIR_NAME, OUTPUT_FILENAME)

    # Ensure the output directory exists
    create_output_directory(OUTPUT_DIR_NAME)

    # Start the compilation process
    compile_files(input_files, output_path)

# Standard Python entry point check
if __name__ == "__main__":
    main()
