import os
# Correct import for the 'google-genai' pip package
import google.generativeai as genai 

from flask import Flask, request, jsonify, json
from flask_cors import CORS
import werkzeug
import time
import traceback
import logging
import sys # For logging sys.path if import fails

# --- Configuration ---
# !!! USING HARDCODED API KEY - TEMPORARY FOR DEBUGGING INSTALLATION !!!
HARDCODED_GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" 
# !!! REMOVE AND USE ENVIRONMENT VARIABLES AFTER TESTING !!!

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}})

# --- Setup Flask Logging ---
if not app.debug:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.propagate = False
    gunicorn_logger = logging.getLogger('gunicorn.error')
    if gunicorn_logger: app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.info("Flask logger configured for non-debug mode (production).")
else:
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Flask logger running in debug mode.")

app.logger.info(f"Upload folder '{UPLOAD_FOLDER}' checked/created.")
app.logger.info("--- Python script starting up (Top of script) ---")
app.logger.info(f"Python sys.path at startup: {sys.path}") # Log python path

# --- Initialize Gemini (using google-genai SDK pattern) ---
gemini_api_configured = False
api_key_to_use = HARDCODED_GEMINI_API_KEY

try:
    app.logger.info("--- Attempting to configure Gemini API (genai.configure pattern) ---")
    app.logger.warning("!!! USING HARDCODED API KEY - FOR TEMPORARY DEBUGGING !!!")

    loggable_key_part = "'NOT_PROCESSED_YET'"
    if api_key_to_use:
        if len(api_key_to_use) > 8: loggable_key_part = f"'{api_key_to_use[:5]}...{api_key_to_use[-3:]}'"
        else: loggable_key_part = f"'{api_key_to_use}' (short key)"
        app.logger.info(f"Using hardcoded API Key: {loggable_key_part} for genai.configure().")
        
        # This is the configuration for the 'google-genai' package
        genai.configure(api_key=api_key_to_use)
        app.logger.info("genai.configure() called successfully with HARDCODED key.")
        gemini_api_configured = True
    else:
        app.logger.error("CRITICAL: Hardcoded GEMINI_API_KEY is None or empty.")

except AttributeError as ae: # Specifically catch if 'genai' object doesn't have 'configure'
    app.logger.error(f"AttributeError during genai.configure(): {ae}. This might mean the wrong 'google.generativeai' module was imported (e.g., from an older conflicting package if 'google-generativeai' pip package was also installed).")
    app.logger.error(f"Path to imported 'genai' module (if available): {getattr(genai, '__file__', 'N/A')}")
    app.logger.error(traceback.format_exc())
except Exception as e:
    app.logger.error(f"ERROR: Exception during Gemini API configuration. Key: {loggable_key_part}. Exception: {type(e).__name__} - {e}")
    app.logger.error(traceback.format_exc())

app.logger.info(f"--- Gemini API Configuration Status at end of init block: {gemini_api_configured} ---")

# --- Routes ---
@app.route('/')
def root():
    app.logger.info(f"Root endpoint '/' accessed. API Configured: {gemini_api_configured}")
    return jsonify({"status": "Backend running (google-genai pattern)", "gemini_api_configured": gemini_api_configured}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    app.logger.info("Chat handler '/chat' invoked (POST).")
    if not gemini_api_configured:
        app.logger.error("Chat handler: Gemini API (genai.configure pattern) not configured.")
        return jsonify({"error": "Backend Gemini API not configured. Check server logs."}), 500

    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    history_json = request.form.get('history', '[]')

    try:
        history_context = json.loads(history_json)
        if not isinstance(history_context, list): raise ValueError("History not a list")
    except Exception as e:
        return jsonify({"error": f"Invalid history format: {e}"}), 400

    current_user_parts = [] # For genai.GenerativeModel parts
    uploaded_file_details_for_frontend = None
    temp_file_path = None

    try:
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            if not filename: return jsonify({"error": "Invalid file name."}), 400
            
            unique_filename = f"{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            uploaded_file_obj.save(temp_file_path)
            app.logger.info(f"File saved to {temp_file_path}. Uploading using genai.upload_file...")

            # File upload for 'google-genai' SDK
            gemini_uploaded_file_response = genai.upload_file(path=temp_file_path, display_name=filename)
            app.logger.info(f"File uploaded via genai.upload_file. URI: {gemini_uploaded_file_response.uri}")

            current_user_parts.append({"file_data": {"mime_type": gemini_uploaded_file_response.mime_type, "file_uri": gemini_uploaded_file_response.uri}})
            uploaded_file_details_for_frontend = {
                "uri": gemini_uploaded_file_response.uri, "mime_type": gemini_uploaded_file_response.mime_type, "name": gemini_uploaded_file_response.display_name
            }

        if text_prompt:
            current_user_parts.append({"text": text_prompt})

        if not current_user_parts:
            return jsonify({"error": "No prompt or file content provided."}), 400
        
        # System prompt (should be part of history_context from frontend)
        # Your frontend should construct history_context like:
        # [ {"role": "user", "parts": [{"text": "SYSTEM PROMPT"}]}, {"role": "model", "parts": [{"text":"OK"}]}, ...chat... ]
        sdk_contents = history_context + [{"role": "user", "parts": current_user_parts}]
        
        tools_for_sdk = [
            genai.types.Tool(google_search_retrieval={}) # For 'google-genai' SDK
        ]
        app.logger.info(f"Tools for 'google-genai' SDK: {tools_for_sdk}")

        generation_config_sdk = genai.types.GenerationConfig(
            # temperature=0.7 # example
        )
        
        # Model selection - try a GA model first for tool support
        # model_name_to_use = "models/gemini-2.5-flash-preview-04-17"
        model_name_to_use = "gemini-1.5-flash-latest" # Recommended for tool testing
        # model_name_to_use = "gemini-pro" # Alternative GA model

        app.logger.info(f"Using model '{model_name_to_use}' with genai.GenerativeModel.")
        model_instance = genai.GenerativeModel(
            model_name=model_name_to_use,
            # system_instruction= # If your system prompt isn't in history, add it here for some models
            )
        
        app.logger.info(f"Calling model.generate_content on '{model_instance.model_name}' with tools.")
        response = model_instance.generate_content(
            contents=sdk_contents,
            generation_config=generation_config_sdk,
            tools=tools_for_sdk
        )
        app.logger.info("Received response from model.generate_content.")
        
        reply_text = ""
        # ... (response processing logic - from previous correct versions)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            return jsonify({"error": f"Content blocked: {response.prompt_feedback.block_reason}"}), 400

        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    reply_text += part.text
                # Handle function calls if necessary (though google_search_retrieval is usually automatic)
        
        result = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            result["uploaded_file_details"] = uploaded_file_details_for_frontend
        
        return jsonify(result)

    except google.api_core.exceptions.InvalidArgument as e_invalid_arg:
        app.logger.error(f"InvalidArgument from Google API: {e_invalid_arg}")
        if "Search Grounding is not supported" in str(e_invalid_arg):
            return jsonify({"error": f"Model '{model_name_to_use}' does not support search grounding. Try a different model."}), 400
        return jsonify({"error": f"API Argument Error: {e_invalid_arg}"}), 400
    except Exception as e:
        app.logger.error(f"Unhandled error in chat_handler: {type(e).__name__} - {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path)
            except Exception as e_remove: app.logger.error(f"Failed to remove temp: {e_remove}")

if __name__ == '__main__':
    if not gemini_api_configured:
        app.logger.critical("CRITICAL: Gemini API (genai.configure pattern) NOT configured.")
    else:
        app.logger.info("Starting Flask dev server (genai.configure pattern, HARDCODED key).")
        app.logger.warning("!!! SERVER RUNNING WITH HARDCODED API KEY - INSECURE !!!")
    app.run(host='0.0.0.0', port=5000, debug=True)
