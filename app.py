import json
from flask import Flask, render_template
from datetime import datetime
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

def get_full_conversation_thread(chat_data, start_id):
    """
    Traces back a conversation thread using the 'linked_event_id'.
    """
    thread = []
    id_to_message = {item['id']: item for item in chat_data}
    current_id = start_id
    
    # Trace back the conversation up to 5 steps or until the start
    for _ in range(5):
        if current_id and current_id in id_to_message:
            message_item = id_to_message[current_id]
            thread.append(message_item)
            current_id = message_item.get('linked_event_id')
        else:
            break
            
    return thread[::-1] # Reverse to show in chronological order

def process_chat_data():
    """
    Loads and processes the ENRICHED chat log with robust error handling.
    """
    try:
        # FIX 1: Added encoding='utf-8' for robust file reading.
        with open('enriched_chat_log.json', 'r', encoding='utf-8') as f_in:
            chat_data = json.load(f_in)
    except FileNotFoundError:
        logging.error("Error: enriched_chat_log.json not found!")
        return {"events": [], "kpis": {}, "analytics": {}, "stories": {}}
    except json.JSONDecodeError:
        logging.error("Error: Could not decode enriched_chat_log.json. Check for syntax errors.")
        return {"events": [], "kpis": {}, "analytics": {}, "stories": {}}

    timeline_events = []
    trace_stories = {}
    
    # Timeline-based KPI data - different values at different stages
    timeline_kpis = {
        "2025-01-13": {"apob": "Not tested", "hrv_trend": "Baseline", "exercise_focus": "Assessment"},
        "2025-03-04": {"apob": "115 mg/dL", "hrv_trend": "+5%", "exercise_focus": "Initial Plan"},
        "2025-06-27": {"apob": "102 mg/dL", "hrv_trend": "+10%", "exercise_focus": "Strength & HIIT"},
        "2025-08-15": {"apob": "95 mg/dL", "hrv_trend": "+15%", "exercise_focus": "Advanced Training"}
    }
    
    kpis = {
        "apob": "102 mg/dL",
        "hrv_trend": "+10%",
        "exercise_focus": "Strength & HIIT"
    }
    
    hours_per_specialist = {}

    TOPIC_EVENT_MAP = {
        "Onboarding": {"content": "Onboarding & Blood Panel", "className": "blood-test"},
        "Medical Decision": {"content": "Medical Decision", "className": "medication"},
        "Nutrition": {"content": "Nutrition Plan Update", "className": "plan-change"},
        "Exercise": {"content": "Exercise Plan Update", "className": "plan-change"},
        "Travel": {"content": "Travel Period", "className": "travel"},
        "Logistics": {"content": "Logistics Handled", "className": "travel"},
        "Member Query": {"content": "Member Question", "className": "plan-change"},
        "Setback": {"content": "Setback Encountered", "className": "setback"},
        "Internal Metrics": {"content": "Internal Metrics Review", "className": "metrics"},
        "Data Analysis": {"content": "Data Analysis", "className": "data-analysis"},
        "Follow-up": {"content": "Team Follow-up", "className": "plan-change"}
    }
    
    events_created = 0
    for item in chat_data:
        msg_id = item['id']
        sender = item['sender_role']
        
        # FIX 2: Use .strip() to remove leading/trailing whitespace from the topic.
        topic = item.get('topic', 'Uncategorized').strip()

        timestamp_str = item.get('timestamp')
        if not timestamp_str:
            continue
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d, %I:%M %p")

        hours_per_specialist[sender] = hours_per_specialist.get(sender, 0) + 0.2

        if topic in TOPIC_EVENT_MAP:
            event_details = TOPIC_EVENT_MAP[topic]
            event = {
                "id": msg_id,
                "content": event_details["content"],
                "start": timestamp.isoformat(),
                "className": event_details["className"]
            }

            if topic == "Medical Decision":
                trace_id = f"trace_{msg_id}"
                event["trace_id"] = trace_id
                
                thread = get_full_conversation_thread(chat_data, msg_id)
                trace_stories[trace_id] = {
                    "title": f"Tracing the 'Why' for this Decision",
                    "steps": [
                        {
                            "icon": "question_answer", 
                            "text": f"<strong>{step['sender_name']} ({step['sender_role']}):</strong> \"{step['message']}\"",
                            "rationale": f"{step['event_link_rationale']}"
                        } for step in thread
                    ]
                }
            
            timeline_events.append(event)
            events_created += 1

    logging.info(f"Processing complete. Found {len(chat_data)} messages, created {events_created} timeline events.")
    
    analytics_data = {
        "labels": list(hours_per_specialist.keys()),
        "values": [round(v, 2) for v in hours_per_specialist.values()]
    }

    return {
        "events": timeline_events,
        "kpis": kpis,
        "timeline_kpis": timeline_kpis,
        "analytics": analytics_data,
        "stories": trace_stories
    }

@app.route('/')
def dashboard():
    processed_data = process_chat_data()
    return render_template(
        'index.html', 
        timeline_events=processed_data['events'],
        kpis=processed_data['kpis'],
        timeline_kpis=processed_data['timeline_kpis'],
        trace_stories=processed_data['stories']
    )

@app.route('/analytics')
def analytics():
    processed_data = process_chat_data()
    return render_template(
        'analytics.html',
        analytics_data=processed_data['analytics']
    )

if __name__ == '__main__':
    app.run(debug=True)