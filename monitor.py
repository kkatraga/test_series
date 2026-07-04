import os
import json
import random
import requests
import re

# --- CONFIG ---
TOKEN = os.getenv("CACHE_BOT")
CHAT_ID = os.getenv("CACHE_CHAT")
DATA_FILE = "combined_output (1).json"  # References the data.json in your repository

def clean_text(text):
    """
    Removes raw newlines, unicode escape artifacts, and structural noise.
    """
    if not text:
        return ""
    
    # 1. Strip out unicode escape sequences (like \u201d, \u00a0, etc.)
    text = re.sub(r'\\u[0-9a-fA-F]{4}', ' ', text)
    
    # 2. Convert literal or raw string newlines into simple spaces
    text = text.replace('\n', ' ').replace('\\n', ' ')
    
    # 3. Collapse multiple spaces down to a single space
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def send_message(text):
    """Sends a standard text message to Telegram for question overflows."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()

def send_exam_quiz(q_data):
    """
    Parses your exam question data, handles text limits, and deploys 
    the native Telegram Quiz Poll with clickable source links.
    """
    letter_to_index = {"a": 0, "b": 1, "c": 2, "d": 3}
    correct_idx = letter_to_index.get(q_data["correct_option"].lower(), 0)

    raw_options = q_data["options"]
    sorted_keys = sorted(raw_options.keys())
    telegram_options = [raw_options[k] for k in sorted_keys]

    # 1. Clean and set up baseline question text
    raw_question_body = clean_text(q_data['question'])
    full_text = f"Q.{q_data['question_number']}: {raw_question_body}"

    # 2. Split logic if the text is longer than 300 characters
    if len(full_text) <= 300:
        poll_question = full_text
    else:
        # FIXED: Slice backwards from the end to leave exactly 300 characters for the poll
        message_chunk = full_text[:-300].strip()
        poll_question = full_text[-300:].strip()
        
        try:
            send_message(f"📖 *{message_chunk} ...*")
        except Exception as e:
            print(f"Failed to send context message for Q.{q_data['question_number']}: {e}")

    # 3. Assemble and fire the Native Telegram Poll
    url = f"https://api.telegram.org/bot{TOKEN}/sendPoll"
    payload = {
        "chat_id": CHAT_ID,
        "question": poll_question,
        "options": telegram_options,  # FIXED: Passing raw list, requests handles string conversion
        "type": "quiz",
        "correct_option_id": correct_idx,
        "is_anonymous": False
    }

    # 4. Inject Clickable Document Reference
    if "file_link" in q_data and q_data["file_link"]:
        link = q_data["file_link"]
        file_label = "test.pdf" if "test.pdf" in link else f"Source File (Q.{q_data['question_number']})"
        explanation_text = f"Source Reference: [{file_label}]({link})"
        
        # SAFEGUARD: Telegram allows max 200 characters for the entire explanation string.
        # If the generated URL is too long, drop the markdown formatting and just send the raw link.
        if len(explanation_text) <= 200:
            payload["explanation"] = explanation_text
            payload["explanation_parse_mode"] = "Markdown"
        else:
            # Fallback to absolute bare minimum to keep it under 200 chars
            payload["explanation"] = link[:200]

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"Successfully sent Question {q_data['question_number']}!")
    except Exception as e:
        print(f"Failed to send poll for Q.{q_data['question_number']}: {e}")
        # Print response text from Telegram to help diagnose if it fails for other reasons
        if hasattr(e, 'response') and e.response is not None:
            print(f"Telegram Error Body: {e.response.text}")

def main():
    # Ensure config tokens exist before executing
    if not TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_TOKEN or CHAT_ID environment variables are missing.")
        return

    # Check if the data.json file exists locally in the repository workspace
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} could not be found in the current directory.")
        return

    # Load questions array from local file
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            questions_list = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file data: {e}")
        return

    if not questions_list or not isinstance(questions_list, list):
        print("Error: data.json does not contain a valid list of questions.")
        return

    # 5. Pick exactly one question at random from the parsed JSON array
    random_question = random.choice(questions_list)
    print(f"Selected Question Number: {random_question.get('question_number')}")

    # Process and fire the quiz to Telegram
    send_exam_quiz(random_question)

if __name__ == "__main__":
    main()
