import json
import os
import google.generativeai as genai
import time

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

INPUT_FILE = 'parsed_chat_log.json'
OUTPUT_FILE = 'enriched_chat_log.json'
HISTORY_WINDOW = 15 # Number of previous messages to provide as context

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest')

PROMPT_TEMPLATE = """
You are a sophisticated data enrichment AI for Elyx, a preventative healthcare service. Your task is to analyze a conversation log entry and return a structured JSON object with analytical tags.

**Instructions:**
1.  Analyze the `current_message_to_analyze` in the context of the `conversation_history`.
2.  Determine the primary `topic` from the allowed list.
3.  Determine if the `current_message_to_analyze` initiates a new conversational thread (`initiator`). A message is an initiator if it brings up a new subject not directly prompted by the immediately preceding messages.
4.  Critically, determine if the message is a direct consequence of a *previous* message in the history. If it is, explain the connection in `event_link_rationale` and provide the `id` of the causal message in `linked_event_id`.
5.  Respond ONLY with a single, valid JSON object containing the tags. Do not add explanations, apologies, or any text outside the JSON structure.

**Allowed Topics:**
["Onboarding", "Medical Decision", "Nutrition", "Exercise", "Travel", "Logistics", "Member Query", "Setback", "Internal Metrics", "Data Analysis", "Follow-up"]

**CONTEXT**
**Conversation History (Most Recent First):**
{conversation_history}

**Current Message to Analyze:**
{current_message}

**YOUR JSON OUTPUT:**
"""

def enrich_data():
    # Load the existing enriched data if it exists, otherwise load the original data
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            messages = json.load(f)
        print(f"Loaded existing enriched data with {len(messages)} messages.")
    else:
        with open(INPUT_FILE, 'r') as f:
            messages = json.load(f)
        print(f"Loaded original data with {len(messages)} messages.")

    # Check which messages need categorization (starting from id=94)
    uncategorized_indices = []
    for i, message in enumerate(messages):
        # Only process messages with id >= 94
        if message.get('id', 0) >= 94:
            # Check if the message lacks any of the required tags or has "Uncategorized" topic
            if ('topic' not in message or 
                message.get('topic') == 'Uncategorized' or
                'initiator' not in message or 
                'event_link_rationale' not in message or 
                'linked_event_id' not in message):
                uncategorized_indices.append(i)
    
    print(f"Found {len(uncategorized_indices)} uncategorized messages to process...")
    
    if len(uncategorized_indices) == 0:
        print("All messages are already categorized!")
        return

    for count, i in enumerate(uncategorized_indices, 1):
        message = messages[i]
        
        # Create context window
        start_index = max(0, i - HISTORY_WINDOW)
        history = messages[start_index:i]
        
        # Format the context for the prompt
        history_str = json.dumps(history[::-1], indent=2) # Reversed for "most recent first"
        current_message_str = json.dumps(message, indent=2)

        prompt = PROMPT_TEMPLATE.format(
            conversation_history=history_str,
            current_message=current_message_str
        )

        try:
            print(f"Processing message {message['id']} ({count} of {len(uncategorized_indices)} uncategorized messages, index {i + 1} in dataset)...")
            response = model.generate_content(prompt)
            
            # Clean up the response to ensure it's valid JSON
            response_text = response.text.strip().replace('```json', '').replace('```', '')
            
            # Parse the JSON response from the LLM
            tags = json.loads(response_text)
            
            # Update only the necessary fields in the existing message object
            messages[i].update(tags)
            
        except Exception as e:
            print(f"Error processing message {message['id']}: {e}")
            print("Could not add tags. Moving to the next message.")
            # Optionally add empty tags on error
            messages[i].update({
                "topic": "Uncategorized",
                "initiator": False,
                "event_link_rationale": None,
                "linked_event_id": None
            })
        
        # Save progress periodically (every 10 messages)
        if count % 10 == 0:
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(messages, f, indent=4)
            print(f"Progress saved after processing {count} uncategorized messages")
        
        # To avoid hitting API rate limits
        time.sleep(1) 

    # Save the final enriched data
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(messages, f, indent=4)
        
    print(f"\nSuccessfully enriched data and saved to '{OUTPUT_FILE}'!")


if __name__ == "__main__":
    if GOOGLE_API_KEY == 'YOUR_GOOGLE_API_KEY':
        print("Error: Please add your Google AI API key to the script.")
    else:
        enrich_data()