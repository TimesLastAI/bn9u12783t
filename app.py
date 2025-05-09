import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from google import genai as google_genai_sdk # Renamed to avoid conflict if old one was around
from google.genai import types as google_genai_types
from google.genai import errors as google_genai_errors # For error handlingfrom dotenv import load_dotenv
from PIL import Image # For validating image files

# --- Configuration ---
load_dotenv()
# !!! IMPORTANT: For testing, you had the key hardcoded. !!!
# !!! Reverting to .env for better practice. Ensure your .env file has: !!!
# !!! GOOGLE_API_KEY="YOUR_GEMINI_API_KEY" !!!
# !!! OR that it's set as an environment variable on Render. !!!
GOOGLE_API_KEY = os.getenv("AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo")

if not GOOGLE_API_KEY:
    logging.error("GOOGLE_API_KEY not found in environment variables or .env file. Please set it.")
    # Exit or raise for a real app. For now, let calls fail if key is missing.

# Configure the Gemini API client using google-genai
# This client is created once globally.
try:
    if GOOGLE_API_KEY:
        # For google-genai, client is initialized directly, no global configure
        genai_client = google_genai_sdk.Client(api_key=GOOGLE_API_KEY)
    else:
        genai_client = None # Will cause errors if used, but prevents crash on startup
        logging.warning("Gemini API client not initialized due to missing API key.")
except Exception as e:
    genai_client = None
    logging.error(f"Failed to initialize Gemini API client: {e}")

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
# Model names in google-genai might be like 'gemini-1.5-flash-001' or 'models/gemini-1.5-flash-latest'
# The 'models/' prefix is often needed for tuned models or specific versions.
# For standard models, often the short name is fine.
# Let's use the one compatible with chat and general generation from the new SDK context.
MODEL_NAME_CHAT = 'gemini-1.5-flash-latest' # Model for chat
MODEL_NAME_FILES = 'gemini-1.5-flash-latest' # Model for file processing, often same as chat

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

# Safety Settings for Gemini (using google.genai.types)
SAFETY_SETTINGS = [
    google_genai_types.SafetySetting(
        category=google_genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    google_genai_types.SafetySetting(
        category=google_genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    google_genai_types.SafetySetting(
        category=google_genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
    google_genai_types.SafetySetting(
        category=google_genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=google_genai_types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    ),
]

# Tool for Google Search
GOOGLE_SEARCH_TOOL = [google_genai_types.Tool(google_search_retrieval=google_genai_types.GoogleSearchRetrieval())]

# Generation Configuration
DEFAULT_GENERATION_CONFIG = google_genai_types.GenerateContentConfig(
    # system_instruction=SYSTEM_PROMPT, # System instruction often better as first part of 'contents' for chat
    safety_settings=SAFETY_SETTINGS,
    tools=GOOGLE_SEARCH_TOOL,
    # temperature=0.7, # Optional: Adjust creativity
    # max_output_tokens=2048, # Optional: Adjust max response length
)

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_image(filepath):
    try:
        img = Image.open(filepath)
        img.verify()
        Image.open(filepath).load()
        return True
    except (IOError, SyntaxError, Image.UnidentifiedImageError) as e:
        logging.warning(f"Invalid image file {filepath}: {e}")
        return False

# --- API Routes ---
@app.route('/chat', methods=['POST'])
def chat_handler():
    if not genai_client:
        return jsonify({"error": "Gemini API client not initialized on the server. Check API key."}), 500

    try:
        prompt_text = request.form.get('prompt', '')
        history_json = request.form.get('history', '[]')

        uploaded_file_details_for_frontend = None
        gemini_sdk_uploaded_file_object = None # This will be the object from client.files.upload
        temp_file_path = None

        # 1. Handle File Upload using google-genai client
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

                logging.info(f"Uploading '{filename}' to Gemini using google-genai SDK...")
                # Use client.files.upload
                gemini_sdk_uploaded_file_object = genai_client.files.upload(path=temp_file_path, display_name=filename)
                logging.info(f"File '{filename}' uploaded. URI: {gemini_sdk_uploaded_file_object.uri}, Name: {gemini_sdk_uploaded_file_object.name}")

                uploaded_file_details_for_frontend = {
                    "uri": gemini_sdk_uploaded_file_object.uri, # URI to store in frontend history
                    "mime_type": gemini_sdk_uploaded_file_object.mime_type,
                    "name": filename # Original filename for display
                }
            elif file and file.filename:
                logging.warning(f"File type not allowed: {file.filename}")
                return jsonify({"error": f"File type not allowed: {file.filename}. Permitted: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        # 2. Prepare History for google-genai SDK
        # History for google-genai's chat needs to be list[types.Content]
        try:
            frontend_history = json.loads(history_json)
        except json.JSONDecodeError:
            logging.error("Invalid history JSON received.")
            return jsonify({"error": "Invalid history format."}), 400

        gemini_chat_history = []
        # Add system prompt as the first "user" or "system" message if chat.create doesn't take it directly
        # For now, we'll pass system_instruction in GenerateContentConfig of send_message.
        # Alternatively, a Content object with the system prompt can be the first item if supported.
        # Let's assume system_instruction in config is sufficient for chat.

        for entry in frontend_history:
            role = entry.get('role') # Should be 'user' or 'model'
            parts_data = entry.get('parts', [])
            if not role or not parts_data:
                logging.warning(f"Skipping invalid history entry: {entry}")
                continue

            current_parts_for_sdk = []
            for part_item in parts_data:
                if 'text' in part_item and part_item['text']:
                    current_parts_for_sdk.append(google_genai_types.Part.from_text(part_item['text']))
                elif 'file_data' in part_item: # This is from frontend's history storage
                    fd = part_item['file_data']
                    if fd.get('file_uri') and fd.get('mime_type'):
                        # Recreate Part from URI for files previously uploaded
                        current_parts_for_sdk.append(google_genai_types.Part.from_uri(uri=fd['file_uri'], mime_type=fd['mime_type']))
                    else:
                        logging.warning(f"Skipping history file_data with missing uri or mime_type: {fd}")

            if current_parts_for_sdk:
                gemini_chat_history.append(google_genai_types.Content(role=role, parts=current_parts_for_sdk))

        # 3. Initialize Chat Session (or use generate_content for simplicity if chat object is complex here)
        # The google-genai SDK's `client.chats.create` is for persistent chat objects.
        # For stateless request/response with history, `client.models.generate_content` is often simpler.
        # Let's use `client.models.generate_content` and manage history manually for now,
        # as it more directly maps to the previous structure and clearly takes system_instruction.
        # If true multi-turn stateful chat on server is needed, client.chats.create is the way.

        # Construct full contents for the current call, including history and new prompt
        contents_for_generate = []

        # Add system prompt as the first content if not using it in config, or if model prefers it this way
        # Some models work better with system prompt as first Content object.
        # For `generate_content`, system_instruction in config is usually fine.
        # Let's add it to history to be explicit if system_instruction in config doesn't cover all cases.
        # contents_for_generate.append(google_genai_types.Content(role='user', parts=[google_genai_types.Part.from_text(f"[SYSTEM PROMPT]\n{SYSTEM_PROMPT}")]))
        # No, system_instruction in GenerateContentConfig is the correct place for google-genai

        contents_for_generate.extend(gemini_chat_history) # Add the past conversation

        # 4. Prepare current user message parts for google-genai SDK
        current_user_message_parts_sdk = []
        if prompt_text:
            current_user_message_parts_sdk.append(google_genai_types.Part.from_text(prompt_text))
        if gemini_sdk_uploaded_file_object: # This is the File object from client.files.upload
            # Convert the File object to a Part for generate_content
            current_user_message_parts_sdk.append(google_genai_types.Part.from_uri(
                uri=gemini_sdk_uploaded_file_object.uri,
                mime_type=gemini_sdk_uploaded_file_object.mime_type
            ))


        if not current_user_message_parts_sdk:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return jsonify({"error": "Cannot send an empty message."}), 400

        contents_for_generate.append(google_genai_types.Content(role='user', parts=current_user_message_parts_sdk))

        # 5. Send Message to Gemini using google-genai
        logging.info(f"Sending to Gemini with google-genai. History length: {len(gemini_chat_history)}, Prompt: '{prompt_text[:50]}...', File: {gemini_sdk_uploaded_file_object.name if gemini_sdk_uploaded_file_object else 'None'}")

        # Create a specific generation config for this call, including the system prompt
        current_generation_config = google_genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT, # Apply system prompt here
            safety_settings=SAFETY_SETTINGS,
            tools=GOOGLE_SEARCH_TOOL
        )

        response = genai_client.models.generate_content(
            model=MODEL_NAME_CHAT, # Or a more specific model name like 'gemini-1.5-flash-001'
            contents=contents_for_generate,
            config=current_generation_config
        )
        logging.info("Received response from Gemini.")

        # 6. Process and Return Response
        reply_text = ""
        if response.parts:
            for part in response.parts:
                if hasattr(part, 'text'):
                    reply_text += part.text
        elif hasattr(response, 'text'): # Fallback for simpler responses or if response object is directly text container
             reply_text = response.text
        else:
            logging.warning("Gemini response had no processable parts or text.")
            # Check for blocked response
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = response.prompt_feedback.block_reason.name
                logging.error(f"Prompt blocked by Gemini. Reason: {block_reason}")
                safety_ratings_info = []
                if response.prompt_feedback.safety_ratings: # Check if safety_ratings exists
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

    except google_genai_errors.BlockedPromptError as e: # Specific error for blocked prompts
        logging.error(f"BlockedPromptError (google-genai): {e}")
        error_message = "Error: Your request was blocked by the content safety filter."
        # The 'e' object itself might contain useful details, or you might need to inspect its properties.
        return jsonify({"error": error_message}), 400
    except google_genai_errors.APIError as e: # General API errors from google-genai
        logging.error(f"APIError (google-genai): Code {e.code if hasattr(e, 'code') else 'N/A'} - {e.message if hasattr(e, 'message') else str(e)}")
        if hasattr(e, 'code') and e.code == 403: # Example: Permission denied
             return jsonify({"error": "Server-side API key issue (Permission Denied). Please check key and enabled APIs."}), 500
        elif "API key not valid" in str(e) or (hasattr(e, 'code') and e.code == 401): # Unauthorized
            return jsonify({"error": "Server-side API key is invalid or not authorized."}), 500
        return jsonify({"error": f"An API error occurred: {str(e)}"}), 500
    except Exception as e:
        logging.exception("An unexpected error occurred in /chat") # Logs traceback
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
    if not GOOGLE_API_KEY:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! WARNING: GOOGLE_API_KEY is not set in environment variables or .env.   !!!")
        print("!!! The application will likely not function correctly.                    !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    elif not genai_client:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! WARNING: Gemini API client failed to initialize. Check API key & logs. !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        print("Gemini client initialized. Using GOOGLE_API_KEY from environment.")
    app.run(debug=True, port=5000)
