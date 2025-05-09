import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold, Part
# from dotenv import load_dotenv # Removed for hardcoding
from PIL import Image # For validating image files

# --- Configuration ---
# load_dotenv() # Removed for hardcoding

# !!! START OF HARDCODED API KEY - FOR TESTING ONLY !!!
# !!! Replace "YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY" with your real API key. !!!
# !!! WARNING: DO NOT USE THIS IN PRODUCTION OR COMMIT TO PUBLIC REPOSITORIES. !!!
GOOGLE_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo"
# !!! END OF HARDCODED API KEY !!!

if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY":
    logging.error("GOOGLE_API_KEY is not set or is still the placeholder value. Please replace 'YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY' with your actual key.")
    # In a real test, you'd want to ensure the key is valid. For now, we'll just check if it's the placeholder.
    # For this example, we'll let it proceed but Gemini calls will fail if it's the placeholder or invalid.

# Configure the Gemini API client
try:
    if GOOGLE_API_KEY and GOOGLE_API_KEY != "YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY":
        genai.configure(api_key=GOOGLE_API_KEY)
    else:
        logging.warning("Gemini API not configured due to missing or placeholder API key.")
except Exception as e:
    logging.error(f"Failed to configure Gemini API: {e}")


# Flask App Setup
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Constants ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'webp', 'heic', 'heif', # Images
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'json', # Documents
    'py', 'js', 'html', 'css', 'java', 'c', 'cpp', 'php', 'rb', 'swift', 'kt', 'go', 'ts', 'md' # Code
}
MODEL_NAME = 'gemini-1.5-flash-latest' # Or 'gemini-1.5-pro-latest'

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# System Prompt for the AI
SYSTEM_PROMPT = """You are a helpful and versatile AI assistant.
Your primary goal is to provide accurate, informative, and engaging responses.
If you need to search the web to answer a question or find current information, you have the capability to do so.
When a user uploads a file, analyze its content in conjunction with their prompt.
Be polite and conversational. Structure your answers clearly. If generating code, use markdown code blocks.
If you are unsure about something or cannot fulfill a request, explain why clearly and politely.
"""

# Safety Settings for Gemini
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_image(filepath):
    try:
        img = Image.open(filepath)
        img.verify() # Verify that it is, in fact an image
        Image.open(filepath).load() # Try to load image data
        return True
    except (IOError, SyntaxError, Image.UnidentifiedImageError) as e:
        logging.warning(f"Invalid image file {filepath}: {e}")
        return False

# --- API Routes ---
@app.route('/chat', methods=['POST'])
def chat_handler():
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY":
        return jsonify({"error": "API key not configured correctly on the server."}), 500

    try:
        prompt_text = request.form.get('prompt', '')
        history_json = request.form.get('history', '[]')
        # conversation_id = request.form.get('conversation_id') # Not directly used by Gemini but good for logging

        uploaded_file_details_for_frontend = None
        gemini_file_part = None
        temp_file_path = None

        # 1. Handle File Upload
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(temp_file_path)
                logging.info(f"File '{filename}' saved to '{temp_file_path}'")

                file_ext = filename.rsplit('.', 1)[1].lower()
                if file_ext in {'png', 'jpg', 'jpeg', 'webp', 'heic', 'heif'}:
                    if not is_valid_image(temp_file_path):
                        os.remove(temp_file_path)
                        return jsonify({"error": f"Uploaded file '{filename}' is not a valid or supported image."}), 400

                logging.info(f"Uploading '{filename}' to Gemini...")
                gemini_uploaded_file = genai.upload_file(path=temp_file_path, display_name=filename)
                logging.info(f"File '{filename}' uploaded to Gemini. URI: {gemini_uploaded_file.uri}")

                gemini_file_part = gemini_uploaded_file
                uploaded_file_details_for_frontend = {
                    "uri": gemini_uploaded_file.uri,
                    "mime_type": gemini_uploaded_file.mime_type,
                    "name": filename
                }
            elif file and file.filename:
                logging.warning(f"File type not allowed: {file.filename}")
                return jsonify({"error": f"File type not allowed: {file.filename}. Permitted: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        # 2. Prepare History for Gemini
        try:
            frontend_history = json.loads(history_json)
        except json.JSONDecodeError:
            logging.error("Invalid history JSON received.")
            return jsonify({"error": "Invalid history format."}), 400

        gemini_history = []
        for entry in frontend_history:
            role = entry.get('role')
            parts_data = entry.get('parts', [])
            if not role or not parts_data:
                logging.warning(f"Skipping invalid history entry: {entry}")
                continue

            current_parts = []
            for part_item in parts_data:
                if 'text' in part_item and part_item['text']:
                    current_parts.append(part_item['text'])
                elif 'file_data' in part_item:
                    fd = part_item['file_data']
                    if fd.get('file_uri') and fd.get('mime_type'):
                        current_parts.append(Part.from_uri(uri=fd['file_uri'], mime_type=fd['mime_type']))
                    else:
                        logging.warning(f"Skipping history file_data with missing uri or mime_type: {fd}")
            if current_parts:
                 gemini_history.append({'role': role, 'parts': current_parts})


        # 3. Initialize Model and Chat
        model = genai.GenerativeModel(
            MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            safety_settings=SAFETY_SETTINGS,
            tools=[genai.protos.Tool(google_search_retrieval=genai.protos.GoogleSearchRetrieval())]
        )
        chat = model.start_chat(history=gemini_history)

        # 4. Prepare current user message parts
        user_message_parts = []
        if prompt_text:
            user_message_parts.append(prompt_text)
        if gemini_file_part:
            user_message_parts.append(gemini_file_part)

        if not user_message_parts:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return jsonify({"error": "Cannot send an empty message."}), 400

        # 5. Send Message to Gemini
        logging.info(f"Sending to Gemini. History length: {len(gemini_history)}, Prompt: '{prompt_text[:50]}...', File: {gemini_file_part.name if gemini_file_part else 'None'}")
        response = chat.send_message(user_message_parts)
        logging.info("Received response from Gemini.")

        # 6. Process and Return Response
        reply_text = ""
        if response.parts:
            for part in response.parts:
                if hasattr(part, 'text'):
                    reply_text += part.text
        elif response.text:
             reply_text = response.text
        else:
            logging.warning("Gemini response had no processable parts or text.")
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason.name
                logging.error(f"Prompt blocked by Gemini. Reason: {block_reason}")
                safety_ratings_info = []
                for rating in response.prompt_feedback.safety_ratings:
                    safety_ratings_info.append(f"{rating.category.name}: {rating.probability.name}")
                error_message = f"Error: Your request was blocked due to content policy ({block_reason})."
                if safety_ratings_info:
                    error_message += f" Details: {'; '.join(safety_ratings_info)}"
                return jsonify({"error": error_message}), 400
            reply_text = "I'm sorry, I couldn't generate a response for that."

        response_data = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            response_data["uploaded_file_details"] = uploaded_file_details_for_frontend

        return jsonify(response_data)

    except genai.types.BlockedPromptException as e:
        logging.error(f"BlockedPromptException: {e}")
        error_message = "Error: Your request was blocked by the content safety filter."
        if e.response and e.response.prompt_feedback and e.response.prompt_feedback.block_reason:
            error_message += f" Reason: {e.response.prompt_feedback.block_reason.name}."
        return jsonify({"error": error_message}), 400
    except genai.types.StopCandidateException as e:
        logging.error(f"StopCandidateException: {e}")
        error_message = "Error: The response generation was stopped."
        if e.response and e.response.candidates and e.response.candidates[0].finish_reason:
             error_message += f" Reason: {e.response.candidates[0].finish_reason.name}."
        return jsonify({"error": error_message}), 400
    except Exception as e:
        logging.exception("An unexpected error occurred in /chat")
        if "API key not valid" in str(e) or "PERMISSION_DENIED" in str(e): # More specific check for API key issues
            return jsonify({"error": "Server-side API key issue. It might be invalid or lack permissions."}), 500
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

    finally:
        # 7. Cleanup Temporary File
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logging.info(f"Temporary file '{temp_file_path}' deleted.")
            except Exception as e:
                logging.error(f"Error deleting temporary file '{temp_file_path}': {e}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! WARNING: GOOGLE_API_KEY is not set or is still the placeholder value.  !!!")
        print("!!! Please replace 'YOUR_ACTUAL_GOOGLE_AI_STUDIO_API_KEY' in app.py with   !!!")
        print("!!! your actual Google AI Studio API key for the application to work.      !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        print("Using hardcoded GOOGLE_API_KEY. Remember this is for testing ONLY.")
    app.run(debug=True, port=5000)
