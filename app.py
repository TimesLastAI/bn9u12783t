import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from google import genai as google_genai_sdk
from google.genai import types as google_genai_types
from google.genai import errors as google_genai_errors # For error handling
from dotenv import load_dotenv
from PIL import Image

# --- Configuration ---
load_dotenv()
GOOGLE_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo"

if not GOOGLE_API_KEY:
    logging.error("CRITICAL: GOOGLE_API_KEY not found in environment variables or .env file. Please set it.")

genai_client = None
if GOOGLE_API_KEY:
    try:
        genai_client = google_genai_sdk.Client(api_key=GOOGLE_API_KEY)
        logging.info("Google GenAI SDK Client initialized successfully.")
    except Exception as e:
        logging.error(f"CRITICAL: Failed to initialize Google GenAI SDK Client: {e}")
else:
    logging.warning("Gemini API client not initialized due to missing API key.")

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER # Ensure Flask config is set
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'webp', 'heic', 'heif',
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'csv', 'json',
    'py', 'js', 'html', 'css', 'java', 'c', 'cpp', 'php', 'rb', 'swift', 'kt', 'go', 'ts', 'md'
}
MODEL_NAME_CHAT = 'gemini-2.5-flash-preview-04-17'

if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
    except OSError as e:
        logging.error(f"Could not create upload folder {UPLOAD_FOLDER}: {e}")

SYSTEM_PROMPT = """You are a helpful and versatile AI assistant.
Your primary goal is to provide accurate, informative, and engaging responses.
When a user uploads a file, analyze its content in conjunction with their prompt.
Be polite and conversational. Structure your answers clearly. If generating code, use markdown code blocks.
If you are unsure about something or cannot fulfill a request, explain why clearly and politely.
""" # Make sure your full prompt is here

SAFETY_SETTINGS = [
    google_genai_types.SafetySetting(category=google_genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    google_genai_types.SafetySetting(category=google_genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    google_genai_types.SafetySetting(category=google_genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    google_genai_types.SafetySetting(category=google_genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]

GOOGLE_SEARCH_TOOL = [] # Search grounding disabled as per previous error

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_image(filepath):
    try:
        img = Image.open(filepath)
        img.verify()
        Image.open(filepath).load() # Re-open after verify
        return True
    except Exception:
        return False

def cleanup_temp_file(filepath, context_message=""):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            logging.info(f"Temporary file '{filepath}' deleted. {context_message}")
        except Exception as e_del:
            logging.error(f"Error deleting temporary file '{filepath}' {context_message}: {e_del}")

@app.route('/chat', methods=['POST'])
def chat_handler():
    if not genai_client:
        return jsonify({"error": "API client not initialized. Check server logs."}), 500

    temp_file_path = None
    try:
        prompt_text = request.form.get('prompt', '')
        history_json = request.form.get('history', '[]')
        uploaded_file_details_for_frontend = None
        gemini_sdk_uploaded_file_object = None

        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(temp_file_path)
                logging.info(f"File '{filename}' saved to '{temp_file_path}'")
                if filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'webp', 'heic', 'heif'} and not is_valid_image(temp_file_path):
                    cleanup_temp_file(temp_file_path, "Context: Invalid image uploaded.")
                    return jsonify({"error": f"Uploaded file '{filename}' is not a valid image."}), 400
                
                gemini_sdk_uploaded_file_object = genai_client.files.upload(path=temp_file_path, display_name=filename)
                logging.info(f"File '{filename}' uploaded. URI: {gemini_sdk_uploaded_file_object.uri}")
                uploaded_file_details_for_frontend = {"uri": gemini_sdk_uploaded_file_object.uri, "mime_type": gemini_sdk_uploaded_file_object.mime_type, "name": filename}
            elif file and file.filename:
                return jsonify({"error": f"File type not allowed: {file.filename}."}), 400

        frontend_history = json.loads(history_json)
        gemini_chat_history = []
        for entry in frontend_history:
            role, parts_data = entry.get('role'), entry.get('parts', [])
            if not role or not parts_data: continue
            current_parts_for_sdk = []
            for item in parts_data:
                if 'text' in item and item['text'] is not None:
                    current_parts_for_sdk.append(google_genai_types.Part.from_text(text=item['text']))
                elif 'file_data' in item and item['file_data'].get('file_uri') and item['file_data'].get('mime_type'):
                    fd = item['file_data']
                    current_parts_for_sdk.append(google_genai_types.Part.from_uri(uri=fd['file_uri'], mime_type=fd['mime_type']))
            if current_parts_for_sdk:
                gemini_chat_history.append(google_genai_types.Content(role=role, parts=current_parts_for_sdk))

        contents_for_generate = list(gemini_chat_history)
        current_user_message_parts_sdk = []
        if prompt_text:
            current_user_message_parts_sdk.append(google_genai_types.Part.from_text(text=prompt_text))
        if gemini_sdk_uploaded_file_object:
            current_user_message_parts_sdk.append(google_genai_types.Part.from_uri(uri=gemini_sdk_uploaded_file_object.uri, mime_type=gemini_sdk_uploaded_file_object.mime_type))

        if not current_user_message_parts_sdk:
            cleanup_temp_file(temp_file_path, "Context: Empty message.")
            return jsonify({"error": "Cannot send an empty message."}), 400
        contents_for_generate.append(google_genai_types.Content(role='user', parts=current_user_message_parts_sdk))

        logging.info(f"Sending to Gemini. Contents length: {len(contents_for_generate)}")
        current_generation_config = google_genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            safety_settings=SAFETY_SETTINGS,
            tools=GOOGLE_SEARCH_TOOL
        )
        response = genai_client.models.generate_content(
            model=MODEL_NAME_CHAT, contents=contents_for_generate, config=current_generation_config
        )
        logging.info("Received response from Gemini.")

        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason.name if hasattr(response.prompt_feedback.block_reason, 'name') else str(response.prompt_feedback.block_reason)
            logging.error(f"Prompt blocked. Reason: {block_reason}")
            cleanup_temp_file(temp_file_path, "Context: Prompt blocked.")
            return jsonify({"error": f"Request blocked due to content policy ({block_reason})."}), 400

        # MODIFIED: How to extract reply_text from GenerateContentResponse
        reply_text = ""
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text: # Make sure part.text is not None or empty if that's desired
                    reply_text += part.text
        elif hasattr(response, 'text') and response.text: # Fallback for direct .text if available
            reply_text = response.text
        # If neither, reply_text remains "" (empty string)

        response_data = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            response_data["uploaded_file_details"] = uploaded_file_details_for_frontend
        return jsonify(response_data)

    except google_genai_errors.ClientError as e:
        logging.error(f"ClientError (google-genai): Status {e.status_code if hasattr(e, 'status_code') else 'N/A'} - {e}")
        error_message = f"Invalid request: {e.message}" if hasattr(e, 'message') and e.message else f"A client-side API error occurred: {str(e)}"
        cleanup_temp_file(temp_file_path, f"Context: ClientError - {error_message}")
        return jsonify({"error": error_message}), 400
    except google_genai_errors.APIError as e: # MODIFIED: Catching the base APIError
        logging.error(f"APIError (google-genai): {e}")
        cleanup_temp_file(temp_file_path, "Context: APIError caught.")
        return jsonify({"error": f"An API error occurred: {str(e)}"}), 500
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError for history: {e}")
        return jsonify({"error": f"Invalid history format sent from client: {str(e)}"}), 400
    except Exception as e:
        logging.exception("An unexpected error occurred in /chat")
        cleanup_temp_file(temp_file_path, "Context: General Exception caught.")
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        cleanup_temp_file(temp_file_path, "Context: Finally block.")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    app_logger = logging.getLogger(__name__)
    if not GOOGLE_API_KEY or not genai_client:
        app_logger.critical("CRITICAL: API Key or GenAI Client is not initialized. Application may not function.")
    else:
        app_logger.info("Flask app starting. Gemini client initialized.")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port) # debug=False for Render
