#!/usr/bin/env python3
import sqlite3
import argparse
import sys
import re
import math
import os
from email import policy
from email.parser import BytesParser

# --- Configuration ---
PAGE_SIZE = 20

# --- ANSI escape codes for terminal colors ---
HIGHLIGHT_COLOR = '\033[91m'
HEADER_COLOR = '\033[94m'
PROMPT_COLOR = '\033[93m'
RESET_COLOR = '\033[0m'

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
    
    highlighted_body = re.sub(f'({re.escape(search_term)})', f'{HIGHLIGHT_COLOR}\\1{RESET_COLOR}', body, flags=re.IGNORECASE)
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


def search_and_display(mbox_file, index_file, search_term):
    """Searches the index and handles the interactive paginated view."""
    if not os.path.exists(index_file):
        print(f"Error: Index file not found at '{index_file}'", file=sys.stderr)
        print(f"Please run 'python3 create_index.py \"{mbox_file}\"' first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(index_file)
    cur = conn.cursor()
    
    query = """
        SELECT
            emails.id,
            emails.sender,
            emails.subject,
            emails.date
        FROM emails
        JOIN email_fts ON emails.id = email_fts.rowid
        WHERE email_fts MATCH ?
        ORDER BY emails.date DESC
    """
    
    # THE FIX IS HERE: Sanitize the search term for FTS5 by wrapping it in quotes
    # and escaping any internal quotes. This treats it as a literal phrase.
    sanitized_term = '"' + search_term.replace('"', '""') + '"'
    
    cur.execute(query, (sanitized_term,))
    results = cur.fetchall()

    if not results:
        print("No matches found.")
        conn.close()
        return

    current_page = 0
    total_pages = math.ceil(len(results) / PAGE_SIZE)

    while True:
        print("\n--- Found {} matching emails ---".format(len(results)))
        if total_pages > 1: print(f"--- Page {current_page + 1} of {total_pages} ---")

        start_index = current_page * PAGE_SIZE
        page_results = results[start_index : start_index + PAGE_SIZE]

        for i, row in enumerate(page_results):
            display_index = start_index + i + 1
            _, sender, subject, date = row
            print(f"[{display_index:03d}] {HEADER_COLOR}{date:<30}{RESET_COLOR} | {sender[:35]:<35} | {subject[:50]}")

        prompt = f"\n{PROMPT_COLOR}Enter # to view, 'n'/'p' for next/prev page, or 'q' to quit: {RESET_COLOR}"
        try:
            choice = input(prompt).lower()
            if choice == 'q': break
            elif choice == 'n':
                if current_page < total_pages - 1: current_page += 1
                else: print("Already on the last page.")
            elif choice == 'p':
                if current_page > 0: current_page -= 1
                else: print("Already on the first page.")
            else:
                choice_index = int(choice) - 1
                if 0 <= choice_index < len(results):
                    row_id_to_view = results[choice_index][0]
                    # Pass the original search term for highlighting, not the sanitized one
                    view_email(mbox_file, conn, row_id_to_view, search_term)
                else: print("Invalid number.")
        except (ValueError, IndexError): print("Invalid input.")
        except KeyboardInterrupt: print("\nExiting."); break
    
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search an mbox index file. The index is assumed to be named [mbox_file_base]-index.db."
    )
    parser.add_argument("search_term", help="The term to search for.")
    parser.add_argument("mbox_file", help="The path to the original mbox file.")
    args = parser.parse_args()
    
    base_name, _ = os.path.splitext(args.mbox_file)
    index_file = base_name + "-index.db"

    search_and_display(args.mbox_file, index_file, args.search_term)