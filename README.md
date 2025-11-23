# Mbox Command-Line Search Tool

A fast, memory-efficient command-line tool for searching huge `mbox` email archives.

### Core Features

*   **Fast:** Searches are nearly instantaneous after the initial indexing.
*   **Memory Efficient:** Handles `mbox` files of any size (tested on 7GB+) without loading them into memory.
*   **Polished & Interactive CLI:** Clean, paginated results with headers and dynamic controls.
*   **Smart Highlighting:** Search terms are highlighted in both the summary view and the full email view.
*   **Dynamic Page Size:** Interactively increase or decrease the number of results shown per page.
*   **No Dependencies:** Relies only on Python 3's standard libraries. No `pip install` required.

## Prerequisites

*   **Python 3.x** must be installed and available in your PATH.

## Installation

1.  Clone this repository or download the scripts to your local machine.
2.  Make the scripts executable:
    ```bash
    chmod +x create_index.py
    chmod +x search_index.py
    ```

## Usage

Using the tool is a two-step process.

### Step 1: Create the Index (One-Time Task)

First, you must create the search index from your `mbox` file. This is the slowest part, but you only need to do it once.

**Syntax**
```bash
./create_index.py <path/to/your/mbox_file>
```

This will create a new file named `my_archive-index.db` in the same directory. If you ever add new emails to your `mbox` file, you will need to delete the old index file and run this script again.

### Step 2: Search the Index

Now you can search as many times as you want.

**Syntax**
```bash
./search_index.py <path/to/your/mbox_file> "your search term"
```

**Example Output and Interactive Controls**
The script will display a paginated list of matching emails with your search term highlighted.

```
--- Found 42 matching emails ---
--- Page 1 of 3 (Page Size: 20) ---
No.   Date               From                                Subject
----- ------------------ ----------------------------------- ----------------------------------------------------------------------
[001] 21 Nov 2025 10:15  | Alice <alice@example.com>         | Fwd: Final notes on Project
[002] 20 Nov 2025 16:45  | Bob <bob@example.com>             | Re: Project timeline adjustment
...

Enter # to view, n/p for page, +/- to change page size, or q to quit:
```
