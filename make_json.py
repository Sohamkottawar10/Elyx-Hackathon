import re
import json

def parse_chat_log(input_file_path, output_file_path):
    """
    Parses a semi-structured chat log file into a clean JSON format.
    """
    with open(input_file_path, 'r', encoding='utf-8') as f:
        full_log = f.read()

    # --- 1. Pre-processing and Cleaning the Raw Text ---
    
    # Remove month/week headers and other non-chat text lines
    lines = full_log.splitlines()
    cleaned_lines = []
    for line in lines:
        # Filter out headers, dividers, and descriptive text
        if not (line.strip().startswith(('Month', 'Week', '____', 'Of course.', 'Here is the detailed'))):
            cleaned_lines.append(line)
    
    cleaned_log = "\n".join(cleaned_lines)
    
    # Normalize lines where a new message starts after an asterisk on the same line
    cleaned_log = re.sub(r'\* \[', '\n[', cleaned_log)
    # Remove any remaining asterisks
    cleaned_log = cleaned_log.replace('*', '')

    # --- 2. Regex Parsing to Extract Chat Data ---
    
    # Regex to capture timestamp, sender (with role), and the full message text.
    # It uses a lookahead (?=\n\[|\Z) to correctly capture multi-line messages.
    log_pattern = re.compile(r"\[(.*?)\] (.*?): (.*?)(?=\n\[|\Z)", re.DOTALL)

    parsed_data = []
    message_id_counter = 1

    for match in log_pattern.finditer(cleaned_log):
        timestamp, sender, message_text = match.groups()

        # Clean up extracted parts
        sender_clean = sender.strip()
        message_clean = message_text.strip()
        
        # --- 3. Structuring the Data ---
        
        # Extract role from parentheses, default to "Member" if not found
        role_match = re.search(r"\((.*?)\)", sender_clean)
        if role_match:
            role = role_match.group(1)
            name = sender_clean.split('(')[0].strip()
        else:
            role = "Member"
            name = sender_clean

        # Skip empty messages that might result from cleaning
        if not message_clean:
            continue

        parsed_data.append({
            "id": message_id_counter,
            "timestamp": timestamp.strip(),
            "sender_name": name,
            "sender_role": role,
            "message": message_clean
        })
        message_id_counter += 1

    # --- 4. Saving to JSON File ---
    
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(parsed_data, f, indent=4)
        
    print(f"✅ Successfully parsed {len(parsed_data)} messages into '{output_file_path}'!")


if __name__ == "__main__":
    parse_chat_log('chat_log.txt', 'parsed_chat_log.json')