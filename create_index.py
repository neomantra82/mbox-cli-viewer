#!/usr/bin/env python3
import sqlite3
import argparse
import sys
import os
from email import policy
from email.parser import BytesParser

def get_email_text_content(message):
    """Extracts all text from an email message for indexing."""
    text_content = []
    for part in message.walk():
        if part.get_content_maintype() == 'text':
            try:
                payload = part.get_payload(decode=True)
                # Decode using UTF-8, replacing any characters that fail
                text_content.append(payload.decode('utf-8', errors='replace'))
            except Exception:
                continue
    return "\n".join(text_content)

def iterate_mbox_messages(mbox_file_path):
    """
    A memory-efficient generator that yields the start offset, end offset,
    and raw bytes of each message in an mbox file.
    This manually parses the file to ensure accurate offsets.
    """
    start_offset = 0
    with open(mbox_file_path, 'rb') as f:
        message_lines = []
        for line in f:
            # A line starting with b'From ' signals the start of a new message
            if line.startswith(b'From '):
                # If we have lines stored, it means we've reached the end of the previous message
                if message_lines:
                    current_pos = f.tell()
                    end_offset = current_pos - len(line)
                    yield start_offset, end_offset, b''.join(message_lines)
                    
                    # The next message starts where the last one ended
                    start_offset = end_offset
                    message_lines = [line]
                else:
                    # This is the very first 'From ' line
                    message_lines.append(line)
            else:
                message_lines.append(line)
        
        # Yield the very last message in the file
        if message_lines:
            end_offset = f.tell()
            yield start_offset, end_offset, b''.join(message_lines)

def create_index(mbox_file, index_file):
    """Reads the mbox file and builds an SQLite FTS5 index."""
    
    print(f"Database will be stored at: {index_file}")
    conn = sqlite3.connect(index_file)
    cur = conn.cursor()

    # Create tables for metadata and full-text search
    cur.execute("CREATE TABLE IF NOT EXISTS emails (id INTEGER PRIMARY KEY, message_id TEXT UNIQUE, sender TEXT, subject TEXT, date TEXT, start_offset INTEGER, end_offset INTEGER)")
    cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS email_fts USING fts5(sender, subject, body, content='emails', content_rowid='id')")

    print(f"Opening and processing mbox file: {mbox_file}")
    print("Starting indexing process. This may take a significant amount of time...")
    
    parser = BytesParser(policy=policy.default)
    processed_count = 0

    try:
        # Use our robust generator to iterate through the file
        for start_offset, end_offset, message_bytes in iterate_mbox_messages(mbox_file):
            message = parser.parsebytes(message_bytes)
            
            processed_count += 1
            if processed_count % 100 == 0:
                print(f"\rProcessed {processed_count} emails...", end="", flush=True)

            msg_id = message.get('Message-ID', f'missing-id-{start_offset}')
            sender = message.get('From', 'No Sender')
            subject = message.get('Subject', 'No Subject')
            date = message.get('Date', 'No Date')
            body = get_email_text_content(message)

            try:
                cur.execute("INSERT OR IGNORE INTO emails (message_id, sender, subject, date, start_offset, end_offset) VALUES (?, ?, ?, ?, ?, ?)",
                            (msg_id, sender, subject, date, start_offset, end_offset))
                last_id = cur.lastrowid
                if last_id > 0:
                    cur.execute("INSERT INTO email_fts (rowid, sender, subject, body) VALUES (?, ?, ?, ?)",
                                (last_id, sender, subject, body))
            except Exception as e:
                print(f"\nCould not process email at offset {start_offset}: {e}")

    except FileNotFoundError:
        print(f"Error: The file '{mbox_file}' was not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred during indexing: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nCommitting changes to the database...")
    conn.commit()
    conn.close()
    print(f"Indexing complete! Processed a total of {processed_count} emails.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a search index from an mbox file. The index will be named [mbox_file_base]-index.db."
    )
    parser.add_argument("mbox_file", help="The path to the mbox file.")
    args = parser.parse_args()
    
    base_name, _ = os.path.splitext(args.mbox_file)
    index_file = base_name + "-index.db"
    
    create_index(args.mbox_file, index_file)