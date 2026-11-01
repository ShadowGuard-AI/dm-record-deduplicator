import argparse
import logging
import pandas as pd
import os
import sys
from typing import List, Union
import difflib
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the CLI tool.
    """
    parser = argparse.ArgumentParser(
        description="Identifies and removes duplicate records based on a configurable set of columns."
    )
    parser.add_argument("input_file", help="Path to the input CSV file.")
    parser.add_argument("output_file", help="Path to the output CSV file.")
    parser.add_argument(
        "-k",
        "--key_columns",
        nargs="+",
        required=True,
        help="List of column names to use for identifying duplicates.",
    )
    parser.add_argument(
        "-t",
        "--similarity_threshold",
        type=float,
        default=0.9,
        help="Similarity threshold for near-duplicate detection (0.0 - 1.0). Similarity is the difflib ratio, an edit based measure, averaged over the key columns.",
    )
    parser.add_argument(
        "-n",
        "--near_duplicate",
        action="store_true",
        help="Enable near-duplicate detection based on similarity threshold. Rows are compared across all rows regardless of the first key column, and input row order is preserved in the output."
    )
    parser.add_argument(
        "-l",
        "--log_file",
        default="dm_record_deduplicator.log",
        help="Path to the log file.",
    )
    return parser.parse_args()


def is_valid_file(file_path: str) -> bool:
    """
    Checks if the given file path exists and is a file.

    Args:
        file_path: The path to the file.

    Returns:
        True if the file exists and is a file, False otherwise.
    """
    return os.path.exists(file_path) and os.path.isfile(file_path)


def is_valid_directory(dir_path: str) -> bool:
    """
    Checks if the given directory path exists and is a directory.

    Args:
        dir_path: The path to the directory.

    Returns:
        True if the directory exists and is a directory, False otherwise.
    """
    return os.path.exists(dir_path) and os.path.isdir(dir_path)


def validate_args(args: argparse.Namespace) -> None:
    """
    Validates the command-line arguments.

    Args:
        args: The argparse.Namespace object containing the parsed arguments.

    Raises:
        ValueError: If any of the arguments are invalid.
    """

    if not is_valid_file(args.input_file):
        raise ValueError(f"Input file '{args.input_file}' does not exist or is not a file.")

    # Validation has a side effect here, and I keep it visible: checking
    # the arguments creates the output directory when it is missing, so a
    # run that then fails on a bad key column still leaves a new directory
    # behind.
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not is_valid_directory(output_dir) and output_dir != "":
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            raise ValueError(f"Cannot create output directory '{output_dir}': {e}")


    if not (0.0 <= args.similarity_threshold <= 1.0):
        raise ValueError("Similarity threshold must be between 0.0 and 1.0.")

    # Validate column names against the input file (check header row)
    try:
        df = pd.read_csv(args.input_file, nrows=0)  # Read only the header
        for col in args.key_columns:
            if col not in df.columns:
                raise ValueError(f"Key column '{col}' not found in the input file.")
    except pd.errors.EmptyDataError:
        raise ValueError("Input file is empty.")
    except FileNotFoundError:
        raise ValueError(f"Input file '{args.input_file}' not found.")
    except Exception as e:
        raise ValueError(f"Error reading input file: {e}")


def deduplicate_records(
    input_file: str,
    output_file: str,
    key_columns: List[str],
    similarity_threshold: float = 0.9,
    near_duplicate: bool = False
) -> None:
    """
    Identifies and removes duplicate records from a CSV file.

    Args:
        input_file: Path to the input CSV file.
        output_file: Path to the output CSV file.
        key_columns: List of column names to use for identifying duplicates.
        similarity_threshold: Similarity threshold for near-duplicate detection.
        near_duplicate: Flag to enable near duplicate detection
    """
    try:
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(input_file)

        # Filling missing key values with an empty string is a decision,
        # not just error avoidance: two rows that are both missing the same
        # key value become equal on that column, and in exact mode they
        # deduplicate against each other. A row with a missing key and a
        # row with a genuinely empty key are also the same thing from here
        # on. The fill happens on the frame that gets written out, too.
        df[key_columns] = df[key_columns].fillna("")

        # Identify duplicate records based on the specified key columns
        if not near_duplicate:
            df_deduplicated = df.drop_duplicates(subset=key_columns, keep="first")
        else:
            # Near duplicate implementation
            # In a real-world scenario, near-duplicate detection would involve more complex algorithms,
            # such as string similarity measures (e.g., Levenshtein distance) or embedding-based approaches.
            # The following example demonstrates a simplified approach:

            def are_near_duplicates(row1, row2, key_columns, threshold):
                # The score is a plain average across the key columns, and
                # averages hide single columns: with ten key columns, one
                # column that shares nothing at all still lets a pair pass
                # a 0.9 threshold if the other nine match. A pair where one
                # side is text and the other is a number scores zero on
                # that column even when the digits are the same, because
                # only two strings take the ratio path and the equality
                # check compares across types.
                similarity_score = 0.0
                for col in key_columns:
                    if isinstance(row1[col], str) and isinstance(row2[col], str):
                        similarity_score += difflib.SequenceMatcher(None, row1[col], row2[col]).ratio()
                    elif row1[col] == row2[col]:
                        similarity_score += 1.0
                similarity_score /= len(key_columns)
                return similarity_score >= threshold

            # Greedy and first come first kept: each row is compared only
            # against rows already kept, never against rows already dropped.
            # Near duplication is not transitive here. If A matches B and B
            # matches C but A does not match C, B is dropped against A and C
            # is then kept, so the output can still hold a pair one step
            # apart. Which rows survive depends on input order throughout.
            kept = []
            deduplicated_rows = []
            for i in range(len(df)):
                row = df.iloc[i]
                if any(are_near_duplicates(row, k, key_columns, similarity_threshold) for k in kept):
                    continue
                kept.append(row)
                deduplicated_rows.append(row)
            df_deduplicated = pd.DataFrame(deduplicated_rows, columns=df.columns)

        # Write the deduplicated DataFrame to a new CSV file
        df_deduplicated.to_csv(output_file, index=False)

        logging.info(f"Deduplication complete. Output written to: {output_file}")

    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
        raise
    except pd.errors.EmptyDataError:
        logging.error(f"Input file is empty: {input_file}")
        raise
    except Exception as e:
        logging.error(f"An error occurred during deduplication: {e}")
        raise


def main():
    """
    Main function to execute the deduplication process.
    """
    args = setup_argparse()

    resolved_input = Path(args.input_file).resolve()
    if Path(args.output_file).resolve() == resolved_input:
        print("Error: Output file must not be the same as the input file.")
        sys.exit(1)
    if Path(args.log_file).resolve() == resolved_input:
        print("Error: Log file must not be the same as the input file.")
        sys.exit(1)

    # Configure logging to file
    log_file = args.log_file
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)

    try:
        validate_args(args)
        deduplicate_records(
            args.input_file,
            args.output_file,
            args.key_columns,
            args.similarity_threshold,
            args.near_duplicate
        )
    except ValueError as e:
        logging.error(f"Invalid arguments: {e}")
        print(f"Error: {e}")  # Print to console for user feedback
        # Exit non-zero: callers and scripts need the failure signal.
        # This used to fall through and exit 0 on a missing input file
        # or an unknown key column, the two failures a user hits most.
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        print(f"Error: {e}")  # Print to console for user feedback
        sys.exit(1)
    finally:
        #Remove the file handler after main is done to ensure logs are correctly managed in future executions
        logging.getLogger().removeHandler(file_handler)

if __name__ == "__main__":
    # Example usage:
    # Create a dummy CSV file for testing
    # Run the tool from the command line, e.g.:
    # python main.py input.csv output.csv -k id name
    # python main.py input.csv output.csv -k id name -t 0.8 -n

    # Example with more arguments
    # python main.py input.csv output.csv -k id name email -t 0.7 -n -l custom.log
    main()