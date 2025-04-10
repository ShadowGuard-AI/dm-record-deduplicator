# dm-record-deduplicator
Identifies and removes duplicate records based on a configurable set of columns. Can be used to obfuscate the true size of a dataset. CLI tool with options for specifying key columns, and methods for handling near-duplicate records with a user-defined similarity threshold. - Focused on Tools designed to generate or mask sensitive data with realistic-looking but meaningless values

## Install
`git clone https://github.com/ShadowStrikeHQ/dm-record-deduplicator`

## Usage
`./dm-record-deduplicator [params]`

## Parameters
- `-h`: Show help message and exit
- `-k`: List of column names to use for identifying duplicates.
- `-t`: No description provided
- `-n`: Enable near-duplicate detection based on similarity threshold.
- `-l`: Path to the log file.

## License
Copyright (c) ShadowStrikeHQ
