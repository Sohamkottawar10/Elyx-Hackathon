import json
from flask import Flask, render_template
from datetime import datetime
import logging
import re

# Configure basic logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

def get_full_conversation_thread(chat_data, start_id, max_depth=5):
    """Traces back a conversation thread using the 'linked_event_id'."""
    thread = []
    id_to_message = {item['id']: item for item in chat_data}
    current_id = start_id
    
    for _ in range(max_depth):
        if current_id and current_id in id_to_message:
            message_item = id_to_message[current_id]
            thread.append(message_item)
            current_id = message_item.get('linked_event_id')
        else:
            break
            
    return thread[::-1] # Reverse to show in chronological order

def find_related_message(chat_data, start_index, topic, keyword_regex):
    """Finds the first message near a given index matching a topic and keyword."""
    # Search backwards from the event
    for i in range(start_index, -1, -1):
        msg = chat_data[i]
        if msg.get('topic') == topic and re.search(keyword_regex, msg['message'], re.IGNORECASE):
            return msg
    # If not found, search forwards
    for i in range(start_index + 1, len(chat_data)):
        msg = chat_data[i]
        if msg.get('topic') == topic and re.search(keyword_regex, msg['message'], re.IGNORECASE):
            return msg
    return None

def process_chat_data():
    """Loads and processes the ENRICHED chat log with context-aware data extraction."""
    try:
        with open('enriched_chat_log.json', 'r', encoding='utf-8') as f_in:
            chat_data = json.load(f_in)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading or parsing JSON file: {e}")
        return {"events": [], "kpis": {}, "analytics": {}, "stories": {}, "groups": []}

    timeline_events = []
    
    # --- Dynamic KPI Generation ---
    timeline_kpis = {
        "2025-01-13": {"apob": "Not tested", "hrv_trend": "Baseline", "exercise_focus": "Assessment"}
    }
    latest_kpis = timeline_kpis["2025-01-13"].copy()
    for item in chat_data:
        timestamp_str = item.get('timestamp')
        if not timestamp_str: continue
        try:
            date_key = datetime.strptime(timestamp_str, "%Y-%m-%d, %I:%M %p").strftime("%Y-%m-%d")
            message = item['message']
            new_apob = re.search(r"apob.*?(\d+\s*mg/dL)", message, re.IGNORECASE)
            new_hrv = re.search(r"hrv.*?(\+\d+%)", message, re.IGNORECASE)
            if not new_hrv: new_hrv = re.search(r"hrv recovered (\d+%) faster", message, re.IGNORECASE)
            msg_lower = message.lower()
            new_exercise = "Strength & HIIT" if "strength & hiit" in msg_lower else ("Strength Training" if "strength" in msg_lower or "resistance" in msg_lower else ("Mobility Focus" if "mobility" in msg_lower else None))
            if new_apob or new_hrv or new_exercise:
                if date_key not in timeline_kpis:
                    timeline_kpis[date_key] = latest_kpis.copy()
                if new_apob: timeline_kpis[date_key]['apob'] = new_apob.group(1)
                if new_hrv: timeline_kpis[date_key]['hrv_trend'] = new_hrv.group(1)
                if new_exercise: timeline_kpis[date_key]['exercise_focus'] = new_exercise
                latest_kpis = timeline_kpis[date_key]
        except ValueError:
            logging.warning(f"Skipping KPI processing for item with invalid timestamp: {timestamp_str}")
            continue
    kpis = latest_kpis
    
    hours_per_specialist = {}

    TOPIC_EVENT_MAP = {
        "Onboarding": {"content": "Onboarding & Blood Panel", "className": "blood-test"},
        "Medical Decision": {"content": "Medical Decision", "className": "medication"},
        "Nutrition": {"content": "Plan Update", "className": "plan-change"},
        "Exercise": {"content": "Plan Update", "className": "plan-change"},
        "Travel": {"content": "Travel & Logistics", "className": "travel"},
        "Setback": {"content": "Setback Encountered", "className": "setback"},
        "Follow-up": {"content": "Progress Update", "className": "plan-change"},  # Added
        "Data Analysis": {"content": "Data Review", "className": "medication"},    # Added
        "Uncategorized": {"content": "General Update", "className": "plan-change"} # Added
    }
    
    groups = [
        {"id": "blood-test", "content": "Onboarding"},
        {"id": "medication", "content": "Medical Decisions & Data"},
        {"id": "plan-change", "content": "Plan Updates & Progress"},
        {"id": "travel", "content": "Travel & Logistics"},
        {"id": "setback", "content": "Setbacks & Friction"}
    ]
    
    for i, item in enumerate(chat_data):
        topic = item.get('topic', 'Uncategorized').strip()
        if topic in TOPIC_EVENT_MAP:
            event_details = TOPIC_EVENT_MAP[topic]
            
            timestamp_str = item.get('timestamp')
            if not timestamp_str:
                logging.warning(f"Skipping event with ID {item.get('id')} due to missing timestamp.")
                continue
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d, %I:%M %p")
            except ValueError:
                logging.warning(f"Skipping event with ID {item.get('id')} due to invalid timestamp format: {timestamp_str}")
                continue

            modal_data = {"type": topic, "title": event_details["content"]}
            
            # --- FIX: Added safety checks for all find_related_message calls ---
            try:
                if topic == "Onboarding":
                    modal_data['kpis'] = [{"label": "Initial ApoB", "value": "115 mg/dL"}, {"label": "Initial HRV Insight", "value": "Drops 20-25% post-travel"}]
                    modal_data['member_goal'] = "Reduce risk of heart disease and enhance cognitive function."
                
                elif topic == "Medical Decision":
                    modal_data['trace_chain'] = get_full_conversation_thread(chat_data, item['id'])
                    key_data_match = re.search(r"(\d+\s*mg/dL)", item['message']) or re.search(r"(\d+)", item['message'])
                    modal_data['key_data_point'] = key_data_match.group(1) if key_data_match else "N/A"

                elif topic in ["Nutrition", "Exercise"]:
                    modal_data['rationale'] = item['message']
                    if "hiit" in item['message'].lower():
                        modal_data['before_after'] = {"before": "Zone 2 Cardio", "after": "Strength & HIIT"}
                    else:
                        modal_data['before_after'] = {"before": "General Mobility", "after": "Targeted Resistance"}
                
                elif topic == "Travel":
                    hrv_msg = find_related_message(chat_data, i, "Data Analysis", r"hrv.*?(\d+%)")
                    sleep_msg = find_related_message(chat_data, i, "Data Analysis", r"sleep duration dropped by ([\d\w\s]+)")
                    # Safely access message content
                    hrv_impact = re.search(r"(\d+%)", hrv_msg['message']).group(1) if hrv_msg else "N/A"
                    sleep_impact = re.search(r"([\d\w\s]+)", sleep_msg['message']).group(1) if sleep_msg else "N/A"
                    modal_data['impact'] = {"hrv": hrv_impact, "sleep": sleep_impact}
                    
                    protocol_msg = find_related_message(chat_data, i, "Travel", "protocol")
                    modal_data['protocol_summary'] = protocol_msg['message'] if protocol_msg else "Standard travel advice provided."

                elif topic == "Setback":
                    modal_data['problem'] = item['message']
                    resolution_msg = find_related_message(chat_data, i, "Follow-up", "solution|resolved|fixed|new plan") or find_related_message(chat_data, i, "Nutrition", "feedback")
                    modal_data['solution'] = resolution_msg['message'] if resolution_msg else "Team acknowledged the issue."
                    
                    cost_msg = find_related_message(chat_data, i, "Internal Metrics", r"(\d+(\.\d)?)\s*hours")
                    internal_cost = re.search(r"(\d+(\.\d)?)\s*hours", cost_msg['message']).group(1) + " Hours" if cost_msg else "N/A"
                    modal_data['internal_cost'] = internal_cost
                
                # NEW CASES FOR ADDITIONAL TOPICS
                elif topic == "Follow-up":
                    modal_data['update_content'] = item['message']
                    modal_data['sender_info'] = f"{item['sender_name']} ({item['sender_role']})"
                    
                elif topic == "Data Analysis":
                    modal_data['analysis_content'] = item['message']
                    modal_data['analyst'] = f"{item['sender_name']} ({item['sender_role']})"
                    
                elif topic == "Uncategorized":
                    modal_data['general_content'] = item['message']
                    modal_data['sender_info'] = f"{item['sender_name']} ({item['sender_role']})"
                    
            except Exception as e:
                logging.error(f"Error building modal data for event ID {item.get('id')}: {e}")
                # Skip creating a modal for this event if data building fails
                pass

            event = {
                "id": item['id'],
                "content": event_details["content"],
                "start": timestamp.isoformat(),
                "className": event_details["className"],
                "group": event_details["className"],
                "modal_data": modal_data
            }
            timeline_events.append(event)

    for item in chat_data:
        hours_per_specialist[item['sender_role']] = hours_per_specialist.get(item['sender_role'], 0) + 0.2
    analytics_data = {"labels": list(hours_per_specialist.keys()), "values": [round(v, 2) for v in hours_per_specialist.values()]}

    return {"events": timeline_events, "kpis": kpis, "timeline_kpis": timeline_kpis, "analytics": analytics_data, "groups": groups}

@app.route('/')
def dashboard():
    processed_data = process_chat_data()
    return render_template('index.html', **processed_data)

@app.route('/analytics')
def analytics():
    processed_data = process_chat_data()
    return render_template('analytics.html', analytics_data=processed_data['analytics'])

if __name__ == '__main__':
    app.run(debug=True)
