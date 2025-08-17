import json
import os
import google.generativeai as genai
import time

GOOGLE_API_KEY = 'AIzaSyDHqCKMOPFAhr_zD4wuWzVGl1Pv6qF0glQ'

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
    # Load the parsed data
    with open(INPUT_FILE, 'r') as f:
        messages = json.load(f)

    enriched_messages = []
    
    print(f"Starting enrichment for {len(messages)} messages...")

    for i, message in enumerate(messages):
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
            print(f"Processing message {message['id']} of {len(messages)}...")
            response = model.generate_content(prompt)
            
            # Clean up the response to ensure it's valid JSON
            response_text = response.text.strip().replace('```json', '').replace('```', '')
            
            # Parse the JSON response from the LLM
            tags = json.loads(response_text)
            
            # Add the new tags to the original message object
            message.update(tags)
            
        except Exception as e:
            print(f"Error processing message {message['id']}: {e}")
            print("Could not add tags. Moving to the next message.")
            # Optionally add empty tags on error
            message.update({
                "topic": "Uncategorized",
                "initiator": False,
                "event_link_rationale": None,
                "linked_event_id": None
            })
        
        enriched_messages.append(message)
        
        # To avoid hitting API rate limits
        time.sleep(1) 

    # Save the final enriched data
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(enriched_messages, f, indent=4)
        
    print(f"\nSuccessfully enriched data and saved to '{OUTPUT_FILE}'!")


if __name__ == "__main__":
    if GOOGLE_API_KEY == 'YOUR_GOOGLE_API_KEY':
        print("Error: Please add your Google AI API key to the script.")
    else:
        enrich_data()