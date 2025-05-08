import os
# MODIFIED IMPORT:
import google.generativeai as genai
from google.genai import types # Keeping this for now, may need aliasing if 'google.genai' is the conflicting part

from flask import Flask, request, jsonify, json
from flask_cors import CORS
import werkzeug
import time
import traceback
import logging

# --- Configuration ---
# !!! WARNING: API KEY HARDCODED BELOW - FOR TEMPORARY TESTING ONLY !!!
HARDCODED_GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" # Your key
# !!! DO NOT COMMIT THIS KEY TO A PUBLIC REPOSITORY !!!

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    # This print might not show in Render logs if gunicorn starts first, use logger
    # print(f"Created upload folder: {UPLOAD_FOLDER}")

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}})

# --- Setup Flask Logging ---
if not app.debug: # In production (like on Render by default unless DEBUG=True env var is set)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)
    # Avoid duplicate logging if gunicorn also configures root logger
    app.logger.propagate = False # Add this for production with gunicorn
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.info("Flask logger configured for non-debug mode (production).")
else: # For local debugging if you run `python app.py`
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Flask logger running in debug mode.")

app.logger.info(f"Created upload folder: {UPLOAD_FOLDER}") # Log after logger is set
app.logger.info("--- Python script starting up (Top of script) ---")

# --- Initialize Gemini ---
gemini_api_configured = False
api_key_to_use = HARDCODED_GEMINI_API_KEY

try:
    app.logger.info("--- Attempting to configure Gemini API (BEGIN) ---")
    app.logger.warning("!!! USING HARDCODED API KEY - FOR TEMPORARY TESTING ONLY !!!")

    if not api_key_to_use:
        app.logger.error("CRITICAL_FAIL: Hardcoded API Key is empty or None. This should not happen.")
    else:
        loggable_key_part = "COULD_NOT_PROCESS_KEY_FOR_LOGGING"
        if len(api_key_to_use) > 8:
            loggable_key_part = f"'{api_key_to_use[:5]}...{api_key_to_use[-3:]}' (Length: {len(api_key_to_use)})"
        elif len(api_key_to_use) > 0 :
             loggable_key_part = f"'{api_key_to_use}' (Length: {len(api_key_to_use)}, logged in full as it's short)"
        else:
            loggable_key_part = "'EMPTY_STRING'"

        app.logger.info(f"Using hardcoded API Key: {loggable_key_part}. Attempting genai.configure().")
        # This 'genai' should now be from 'import google.generativeai as genai'
        genai.configure(api_key=api_key_to_use)
        app.logger.info("Gemini API configured successfully via genai.configure() using the hardcoded key.")
        gemini_api_configured = True

except Exception as e:
    imported_genai_module_details = "unknown"
    if 'genai' in globals():
        imported_genai_module_details = f"Name: {getattr(genai, '__name__', 'N/A')}, Path: {getattr(genai, '__file__', 'N/A')}"

    app.logger.error(f"ERROR: Exception during Gemini API configuration. Imported 'genai' module details: {imported_genai_module_details}. ExceptionType: {type(e).__name__}, Message: {e}")
    app.logger.error(traceback.format_exc())

app.logger.info(f"--- Gemini API Configuration Status at end of init block: {gemini_api_configured} ---")


# --- Routes ---
@app.route('/')
def root():
    app.logger.info(f"Root endpoint '/' accessed. Gemini configured status: {gemini_api_configured}")
    return jsonify({"status": "Backend running", "gemini_api_configured": gemini_api_configured}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    app.logger.info("Chat handler '/chat' invoked (POST).")
    if not gemini_api_configured:
        app.logger.error("Chat handler: Gemini API not configured. This is unexpected if hardcoding was intended to work.")
        return jsonify({"error": "Backend Gemini API not configured."}), 500

    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    history_json = request.form.get('history', '[]')
    conversation_id = request.form.get('conversation_id', '')

    app.logger.debug(f"Received data: conversation_id='{conversation_id}', has_file='{uploaded_file_obj is not None}', text_prompt_len='{len(text_prompt)}', history_json_len='{len(history_json)}'")

    try:
        history_context = json.loads(history_json)
        if not isinstance(history_context, list):
            app.logger.warning("Invalid history format: Not a list.")
            raise ValueError("History is not a list")
        app.logger.debug(f"History parsed successfully. {len(history_context)} items.")
    except Exception as e:
        app.logger.warning(f"Invalid history format: {e}. Received: {history_json[:200]}")
        return jsonify({"error": "Invalid history format."}), 400

    current_user_parts = []
    uploaded_file_details_for_frontend = None
    temp_file_path = None

    try:
        if uploaded_file_obj and uploaded_file_obj.filename:
            app.logger.info(f"Processing uploaded file. Original filename: '{uploaded_file_obj.filename}', mimetype: '{uploaded_file_obj.mimetype}'")
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            if not filename:
                app.logger.warning(f"Uploaded file name '{uploaded_file_obj.filename}' was sanitized to an empty string.")
                return jsonify({"error": "Invalid or insecure file name provided."}), 400

            unique_filename = f"{conversation_id or 'conv'}_{int(time.time())}_{filename}"
            temp__path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            app.logger.info(f"Attempting to save uploaded file to temporary path: '{temp_file_path}'")
            try:
                uploaded_file_obj.save(temp_file_path)
                app.logger.info(f"File saved successfully to '{temp_file_path}'")
            except Exception as e_save:
                app.logger.error(f"Error saving uploaded file to '{temp_file_path}': {e_save}")
                app.logger.error(traceback.format_exc())
                return jsonify({"error": f"Could not save uploaded file: {e_save}"}), 500

            app.logger.info("Attempting to upload file to Gemini service...")
            try:
                # This 'genai' should be the one from 'import google.generativeai as genai'
                uploaded_gemini_file = genai.upload_file(path=temp_file_path, display_name=filename)
                app.logger.info(f"File uploaded to Gemini successfully. URI: '{uploaded_gemini_file.uri}', MIME type: '{uploaded_gemini_file.mime_type}', Display Name: '{uploaded_gemini_file.display_name}'")
            except Exception as e_gemini_upload:
                app.logger.error(f"Error uploading file to Gemini service: {e_gemini_upload}")
                app.logger.error(traceback.format_exc())
                return jsonify({"error": f"Failed to upload file to AI service: {e_gemini_upload}"}), 500

            file_data_part = {
                "file_data": {
                    "mime_type": uploaded_gemini_file.mime_type,
                    "file_uri": uploaded_gemini_file.uri
                }
            }
            current_user_parts.append(file_data_part)
            uploaded_file_details_for_frontend = {
                "uri": uploaded_gemini_file.uri,
                "mime_type": uploaded_gemini_file.mime_type,
                "name": uploaded_gemini_file.display_name
            }
            app.logger.debug(f"Prepared file_data_part for Gemini and details for frontend: {uploaded_file_details_for_frontend}")

        if text_prompt:
            current_user_parts.append({"text": text_prompt})
            app.logger.debug(f"Text prompt added to current_user_parts.")

        if not current_user_parts:
            app.logger.warning("No prompt text or file content provided to form user parts.")
            return jsonify({"error": "No prompt or file content provided."}), 400

        system_instruction = """...""" # Your system prompt
        prompt_injection = [
            {"role": "user", "parts": [{"text": system_instruction}]},
            {"role": "model", "parts": [{"text": "Understood."}]}
        ]
        gemini_contents = prompt_injection + history_context + [{"role": "user", "parts": current_user_parts}]
        app.logger.debug(f"Prepared 'gemini_contents' with {len(gemini_contents)} total items.")

        # Ensure 'types' is correctly sourced. If 'from google.genai import types' is problematic,
        # you might need to use 'genai.types.Tool' etc. or alias 'types' like 'genai_types'
        tools_list = [types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())] # Or genai.types.Tool(...)
        generation_settings = types.GenerationConfig() # Or genai.types.GenerationConfig()
        app.logger.debug(f"GenerationConfig prepared. Tools enabled: Google Search.")

        model_name_to_use = "models/gemini-2.5-flash-preview-04-17" # Your model
        app.logger.info(f"Initializing GenerativeModel with: '{model_name_to_use}'")
        
        # This 'genai' should be the one from 'import google.generativeai as genai'
        model_instance = genai.GenerativeModel(model_name=model_name_to_use)
        
        app.logger.info(f"Calling model.generate_content on '{model_instance.model_name}'")
        try:
            response = model_instance.generate_content(
                contents=gemini_contents,
                generation_config=generation_settings,
                tools=tools_list
            )
            app.logger.info("Received response from Gemini generate_content.")
            app.logger.debug(f"Full Gemini Response (first 500 chars): {str(response)[:500]}")
        except Exception as e_gemini_generate:
            app.logger.error(f"Error during Gemini generate_content call: {e_gemini_generate}")
            app.logger.error(traceback.format_exc())
            return jsonify({"error": f"AI model failed to generate response: {e_gemini_generate}"}), 500

        reply_text = ""
        # (Your response processing logic...)
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            block_message = getattr(response.prompt_feedback, 'block_reason_message', "No specific message.")
            app.logger.warning(f"Gemini response was blocked. Reason: {block_reason}, Message: {block_message}")
            return jsonify({"error": f"Content blocked by AI safety filters: {block_reason}. {block_message}"}), 400

        if not response.candidates:
            app.logger.warning("No candidates in Gemini response after successful call (and not blocked).")
            return jsonify({"error": "No response generated by the model (no candidates)."}), 500
        
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text:
                    reply_text += part.text
        elif hasattr(response, 'text') and response.text: # Fallback for simpler responses
             reply_text = response.text
        else:
            app.logger.warning("Gemini response candidate has no text parts or direct .text attribute.")
            if candidate.content and candidate.content.parts: # Check for function calls
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call'):
                        app.logger.info(f"Model returned a function call, but no immediate text: {part.function_call}")
                        break # Or handle function call

        app.logger.info(f"Extracted reply_text (first 100 chars): '{reply_text[:100]}'")
        result = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            result["uploaded_file_details"] = uploaded_file_details_for_frontend
        
        app.logger.info("Chat handler finished successfully. Sending response to frontend.")
        return jsonify(result)

    except types.BlockedPromptException as bpe: # Or genai.types.BlockedPromptException
        block_reason = "Unknown"
        block_message = "No specific message."
        if bpe.response and bpe.response.prompt_feedback:
            block_reason = bpe.response.prompt_feedback.block_reason
            block_message = getattr(bpe.response.prompt_feedback, 'block_reason_message', "No specific message.")
        app.logger.warning(f"Gemini API request blocked (BlockedPromptException). Reason: {block_reason}, Message: {block_message}")
        return jsonify({"error": f"Request blocked by content safety filters: {block_reason}. {block_message}"}), 400
    except Exception as e:
        app.logger.error(f"Unhandled error in chat_handler's main try block: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                app.logger.info(f"Successfully removed temporary file: '{temp_file_path}'")
            except Exception as e_remove:
                app.logger.error(f"Failed to remove temporary file '{temp_file_path}': {e_remove}")
        app.logger.info("Chat handler 'finally' block executed.")


if __name__ == '__main__':
    # Note: When running with gunicorn, this __main__ block might not be the primary entry point for Flask's app.run.
    # Gunicorn runs the 'app' object directly.
    # The 'debug=True' for app.run() is for local development with `python app.py`.
    # On Render, gunicorn handles serving, and Flask's debug mode is usually controlled by an ENV var.
    if not gemini_api_configured:
        app.logger.critical("CRITICAL_SERVER_START_FAIL: Cannot start Flask server because Gemini API was not configured. Check startup logs for errors from genai.configure().")
    else:
        app.logger.info("Starting Flask development server (Gemini API was configured via hardcoded key).")
        app.logger.warning("!!! SERVER RUNNING WITH HARDCODED API KEY - INSECURE - FOR TESTING ONLY !!!")
        # For local testing:
        app.run(host='0.0.0.0', port=5000, debug=True)
