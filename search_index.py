#!/usr/bin/env python3
import sqlite3
import argparse
import sys
import re
import math
import os
from email import policy, utils
from email.parser import BytesParser
from datetime import datetime

# --- Configuration ---
DEFAULT_PAGE_SIZE = 20 # <<< NEW: Default page size constant

# --- ANSI escape codes for terminal colors ---
HIGHLIGHT_COLOR = '\033[91m'  # Red
HEADER_COLOR = '\033[94m'     # Blue
PROMPT_COLOR = '\033[93m'     # Yellow
RESET_COLOR = '\033[0m'

def highlight_summary(text, search_term):
    """Case-insensitively highlights a search term in a string."""
    if not search_term:
        return text
    return re.sub(
        f'({re.escape(search_term)})',
        f'{HIGHLIGHT_COLOR}\\1{RESET_COLOR}',
        text,
        flags=re.IGNORECASE
    )

def format_date(date_str):
    """Parses a standard email date string and formats it cleanly."""
    if not date_str:
        return "No Date"
    try:
        dt = utils.parsedate_to_datetime(date_str)
        return dt.strftime('%d %b %Y %H:%M')
    except (TypeError, ValueError):
        return date_str.split(',')[1][:18].strip() if ',' in date_str else date_str[:18]

def display_email(email_bytes, search_term):
    """Parses and prints a single email from its raw bytes, with highlighting."""
    message = BytesParser(policy=policy.default).parsebytes(email_bytes)
    print("\n" + "=" * 80)
    for header in ['From', 'To', 'Subject', 'Date']:
        value = message.get(header, 'N/A')
        print(f"{HEADER_COLOR}{header:<10}:{RESET_COLOR} {value}")
    print("-" * 80)

    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                try: body = part.get_payload(decode=True).decode(errors='ignore')
                except: continue
                break
    else:
        try: body = message.get_payload(decode=True).decode(errors='ignore')
        except: body = "[Could not decode email body]"
    
    highlighted_body = highlight_summary(body, search_term)
    print(highlighted_body)
    print("=" * 80 + "\n")


def view_email(mbox_file, index_conn, row_id, search_term):
    """Fetches a single email from the mbox file using its offset."""
    cur = index_conn.cursor()
    cur.execute("SELECT start_offset, end_offset FROM emails WHERE id = ?", (row_id,))
    res = cur.fetchone()
    if not res:
        print("Could not find that email.")
        return
    
    start_offset, end_offset = res
    size = end_offset - start_offset

    try:
        with open(mbox_file, 'rb') as f:
            f.seek(start_offset)
            email_bytes = f.read(size)
            display_email(email_bytes, search_term)
    except FileNotFoundError:
        print(f"Error: Mbox file '{mbox_file}' not found.", file=sys.stderr)
    except Exception as e:
        print(f"Error reading from mbox file: {e}", file=sys.stderr)


def search_and_display(mbox_file, index_file, search_term): # <<< CHANGED: page_size removed
    """Searches the index and handles the interactive paginated view."""
    if not os.path.exists(index_file):
        print(f"Error: Index file not found at '{index_file}'", file=sys.stderr)
        print(f"Please run 'python3 create_index.py \"{mbox_file}\"' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(index_file)
    cur = conn.cursor()
    
    query = """
        SELECT emails.id, emails.sender, emails.subject, emails.date
        FROM emails JOIN email_fts ON emails.id = email_fts.rowid
        WHERE email_fts MATCH ? ORDER BY emails.date DESC
    """
    
    sanitized_term = '"' + search_term.replace('"', '""') + '"'
    cur.execute(query, (sanitized_term,))
    results = cur.fetchall()

    if not results:
        print("No matches found.")
        conn.close()
        return

    current_page = 0
    current_page_size = DEFAULT_PAGE_SIZE # <<< NEW: Use a mutable variable for page size

    while True:
        # <<< NEW: Recalculate total pages inside the loop in case page size changes
        total_pages = math.ceil(len(results) / current_page_size)
        # <<< NEW: Ensure current page is valid after a page size change
        current_page = min(current_page, total_pages - 1)

        print("\n--- Found {} matching emails ---".format(len(results)))
        if total_pages > 1: print(f"--- Page {current_page + 1} of {total_pages} (Page Size: {current_page_size}) ---")
        
        print(f"{HEADER_COLOR}{'No.':<5} {'Date':<18} {'From':<35} {'Subject':<70}{RESET_COLOR}")
        print(f"{HEADER_COLOR}{'-'*5} {'-'*18} {'-'*35} {'-'*70}{RESET_COLOR}")

        start_index = current_page * current_page_size
        page_results = results[start_index : start_index + current_page_size]

        for i, row in enumerate(page_results):
            display_index = start_index + i + 1
            _, sender, subject, date = row
            
            clean_date = format_date(date)
            sender_display = highlight_summary(sender[:35], search_term)
            subject_display = highlight_summary(subject[:70], search_term)

            print(f"[{display_index:03d}] {clean_date:<18} | {sender_display:<35} | {subject_display}")

        # <<< NEW: Updated prompt with +/- controls
        prompt = f"\n{PROMPT_COLOR}Enter # to view, n/p for page, +/- to change page size, or q to quit: {RESET_COLOR}"
        try:
            choice = input(prompt).lower()
            if choice == 'q': break
            elif choice == 'n':
                if current_page < total_pages - 1: current_page += 1
                else: print("Already on the last page.")
            elif choice == 'p':
                if current_page > 0: current_page -= 1
                else: print("Already on the first page.")
            # <<< NEW: Logic to handle page size changes
            elif choice == '+':
                current_page_size = min(100, current_page_size + 10) # Cap at 100
                print(f"Page size increased to {current_page_size}.")
            elif choice == '-':
                current_page_size = max(10, current_page_size - 10) # Minimum of 10
                print(f"Page size decreased to {current_page_size}.")
            else:
                choice_index = int(choice) - 1
                if 0 <= choice_index < len(results):
                    row_id_to_view = results[choice_index][0]
                    view_email(mbox_file, conn, row_id_to_view, search_term)
                else: print("Invalid number.")
        except (ValueError, IndexError): print("Invalid input.")
        except KeyboardInterrupt: print("\nExiting."); break
    
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search an mbox index file. The index is assumed to be named [mbox_file_base]-index.db."
    )
    # <<< CHANGED: Removed the page-size argument
    parser.add_argument("mbox_file", help="The path to the original mbox file.")
    parser.add_argument("search_term", help="The term to search for.")
    args = parser.parse_args()
    
    base_name, _ = os.path.splitext(args.mbox_file)
    index_file = base_name + "-index.db"

    search_and_display(args.mbox_file, index_file, args.search_term)