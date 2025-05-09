import os
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from google import genai as google_genai_sdk
from google.genai import types as google_genai_types
from google.genai import errors as google_genai_errors
from dotenv import load_dotenv
from PIL import Image

# --- Configuration ---
load_dotenv() # Load environment variables from .env file if present
GOOGLE_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo"

if not GOOGLE_API_KEY:
    logging.error("GOOGLE_API_KEY not found in environment variables or .env file. Please set it.")

# Configure the Gemini API client using google-genai
genai_client = None
if GOOGLE_API_KEY:
    try:
        genai_client = google_genai_sdk.Client(api_key=GOOGLE_API_KEY)
        logging.info("Google GenAI SDK Client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Google GenAI SDK Client: {e}")
else:
    logging.warning("Gemini API client not initialized due to missing API key.")

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
MODEL_NAME_CHAT = 'gemini-2.5-flash-preview-04-17' # Using a specific version for stability

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
    except OSError as e:
        logging.error(f"Could not create upload folder {UPLOAD_FOLDER}: {e}")


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

def cleanup_temp_file(filepath, context_message=""):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            logging.info(f"Temporary file '{filepath}' deleted. {context_message}")
        except Exception as e_del:
            logging.error(f"Error deleting temporary file '{filepath}' {context_message}: {e_del}")


# --- API Routes ---
@app.route('/chat', methods=['POST'])
def chat_handler():
    if not genai_client:
        return jsonify({"error": "Gemini API client not initialized on the server. Check API key."}), 500

    temp_file_path = None # Initialize here to ensure it's in scope for finally/except blocks
    try:
        prompt_text = request.form.get('prompt', '')
        history_json = request.form.get('history', '[]')

        uploaded_file_details_for_frontend = None
        gemini_sdk_uploaded_file_object = None

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
                        cleanup_temp_file(temp_file_path, "Context: Invalid image uploaded.")
                        return jsonify({"error": f"Uploaded file '{filename}' is not a valid or supported image."}), 400

                logging.info(f"Uploading '{filename}' to Gemini using google-genai SDK...")
                gemini_sdk_uploaded_file_object = genai_client.files.upload(path=temp_file_path, display_name=filename)
                logging.info(f"File '{filename}' uploaded. URI: {gemini_sdk_uploaded_file_object.uri}, Name: {gemini_sdk_uploaded_file_object.name}")

                uploaded_file_details_for_frontend = {
                    "uri": gemini_sdk_uploaded_file_object.uri,
                    "mime_type": gemini_sdk_uploaded_file_object.mime_type,
                    "name": filename
                }
            elif file and file.filename: # File present but not allowed type
                logging.warning(f"File type not allowed: {file.filename}")
                return jsonify({"error": f"File type not allowed: {file.filename}. Permitted: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        # 2. Prepare History for google-genai SDK
        try:
            frontend_history = json.loads(history_json)
        except json.JSONDecodeError:
            logging.error("Invalid history JSON received.")
            return jsonify({"error": "Invalid history format."}), 400

        gemini_chat_history = []
        for entry in frontend_history:
            role = entry.get('role')
            parts_data = entry.get('parts', [])
            if not role or not parts_data:
                logging.warning(f"Skipping invalid history entry: {entry}")
                continue

            current_parts_for_sdk = []
            for part_item in parts_data:
                if 'text' in part_item and part_item['text'] is not None: # Check for None too
                    current_parts_for_sdk.append(google_genai_types.Part.from_text(text=part_item['text'])) # CORRECTED
                elif 'file_data' in part_item:
                    fd = part_item['file_data']
                    if fd.get('file_uri') and fd.get('mime_type'):
                        current_parts_for_sdk.append(google_genai_types.Part.from_uri(uri=fd['file_uri'], mime_type=fd['mime_type']))
                    else:
                        logging.warning(f"Skipping history file_data with missing uri or mime_type: {fd}")

            if current_parts_for_sdk:
                gemini_chat_history.append(google_genai_types.Content(role=role, parts=current_parts_for_sdk))

        # 3. Construct full contents for the current API call
        contents_for_generate = []
        contents_for_generate.extend(gemini_chat_history)

        # 4. Prepare current user message parts for google-genai SDK
        current_user_message_parts_sdk = []
        if prompt_text: # Ensure prompt_text is not empty before adding
            current_user_message_parts_sdk.append(google_genai_types.Part.from_text(text=prompt_text)) # CORRECTED
        if gemini_sdk_uploaded_file_object:
            current_user_message_parts_sdk.append(google_genai_types.Part.from_uri(
                uri=gemini_sdk_uploaded_file_object.uri,
                mime_type=gemini_sdk_uploaded_file_object.mime_type
            ))

        if not current_user_message_parts_sdk: # No text and no file for the current turn
            cleanup_temp_file(temp_file_path, "Context: Empty message sent by user.") # Clean up if file was uploaded but no text prompt
            return jsonify({"error": "Cannot send an empty message (no text or file provided for the current turn)."}), 400

        contents_for_generate.append(google_genai_types.Content(role='user', parts=current_user_message_parts_sdk))

        # 5. Send Message to Gemini using google-genai
        logging.info(f"Sending to Gemini with google-genai. Full contents length: {len(contents_for_generate)}, Prompt: '{prompt_text[:50]}...', File: {gemini_sdk_uploaded_file_object.name if gemini_sdk_uploaded_file_object else 'None'}")

        current_generation_config = google_genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            safety_settings=SAFETY_SETTINGS,
            tools=GOOGLE_SEARCH_TOOL
        )

        response = genai_client.models.generate_content(
            model=MODEL_NAME_CHAT,
            contents=contents_for_generate,
            config=current_generation_config
        )
        logging.info("Received response from Gemini.")

        # 6. Process and Return Response

        # Check for blocking in the response object itself first
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback and \
           hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
            block_reason_name = response.prompt_feedback.block_reason.name if hasattr(response.prompt_feedback.block_reason, 'name') else str(response.prompt_feedback.block_reason)
            logging.error(f"Prompt blocked by Gemini. Reason: {block_reason_name}")
            safety_ratings_info = []
            if hasattr(response.prompt_feedback, 'safety_ratings') and response.prompt_feedback.safety_ratings:
                for rating in response.prompt_feedback.safety_ratings:
                    rating_category_name = rating.category.name if hasattr(rating.category, 'name') else str(rating.category)
                    rating_probability_name = rating.probability.name if hasattr(rating.probability, 'name') else str(rating.probability)
                    safety_ratings_info.append(f"{rating_category_name}: {rating_probability_name}")
            error_message = f"Error: Your request was blocked due to content policy ({block_reason_name})."
            if safety_ratings_info:
                error_message += f" Details: {'; '.join(safety_ratings_info)}"
            cleanup_temp_file(temp_file_path, "Context: Prompt blocked by Gemini.")
            return jsonify({"error": error_message}), 400

        reply_text = ""
        if response.parts:
            for part in response.parts:
                if hasattr(part, 'text'):
                    reply_text += part.text
        elif hasattr(response, 'text') and response.text: # Check if response.text exists and is not empty
             reply_text = response.text
        else: # No parts and no direct text, or response.text is empty
            logging.warning("Gemini response had no processable text parts or direct text attribute was empty.")
            # This might happen if the model legitimately has nothing to say, or if it's a tool call response without text.
            # For a chat bot, usually some text is expected. If it's an empty but valid response, return it as such.
            # If we expect text and get none, it might be an implicit issue or model preference.
            # For now, we'll consider it an empty valid reply if not blocked and no error raised.
            reply_text = "" # Or "I'm sorry, I don't have a text response for that." if you prefer

        response_data = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            response_data["uploaded_file_details"] = uploaded_file_details_for_frontend

        return jsonify(response_data)

    except google_genai_errors.InvalidArgumentError as e:
        logging.error(f"InvalidArgumentError (google-genai): {e}")
        cleanup_temp_file(temp_file_path, "Context: InvalidArgumentError caught.")
        return jsonify({"error": f"Invalid request: Your prompt or content may have been blocked or is invalid. Details: {str(e)}"}), 400
    except google_genai_errors.GoogleAPIError as e:
        logging.error(f"GoogleAPIError (google-genai): {e}")
        cleanup_temp_file(temp_file_path, "Context: GoogleAPIError caught.")
        return jsonify({"error": f"An API error occurred with the AI service: {str(e)}"}), 500
    except Exception as e:
        logging.exception("An unexpected error occurred in /chat")
        cleanup_temp_file(temp_file_path, "Context: General Exception caught.")
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        # Final cleanup attempt for the temp file, regardless of what happened in try/except
        # This primarily catches cases where an unhandled exception might occur before specific cleanup
        # or if the file wasn't cleaned up in an error branch for some reason.
        cleanup_temp_file(temp_file_path, "Context: Finally block.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    app_logger = logging.getLogger(__name__) # Use a named logger for the app itself

    if not GOOGLE_API_KEY:
        app_logger.critical("CRITICAL: GOOGLE_API_KEY is not set. The application will not function.")
    elif not genai_client:
        app_logger.critical("CRITICAL: Gemini API client failed to initialize. Check API key & logs.")
    else:
        app_logger.info("Flask app starting. Gemini client initialized.")

    # Consider PORT from environment for deployment flexibility (e.g. Render sets PORT env var)
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port) # host='0.0.0.0' is important for Render
