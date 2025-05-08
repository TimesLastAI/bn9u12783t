import os
import google.generativeai as genai
from flask import Flask, request, jsonify, json
from flask_cors import CORS
import werkzeug
import time
import traceback
import logging

# --- Configuration ---
# !!! WARNING: API KEY HARDCODED BELOW - FOR TEMPORARY TESTING ONLY !!!
HARDCODED_GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" # Your API Key
# !!! DO NOT COMMIT THIS KEY TO A PUBLIC REPOSITORY OR USE IN PRODUCTION !!!

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
    if gunicorn_logger:
        app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.info("Flask logger configured for non-debug mode (production).")
else:
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Flask logger running in debug mode.")

app.logger.info(f"Upload folder '{UPLOAD_FOLDER}' checked/created.")
app.logger.info("--- Python script starting up (Top of script) ---")

# --- Initialize Gemini ---
gemini_api_configured = False
api_key_to_use = HARDCODED_GEMINI_API_KEY

try:
    app.logger.info("--- Attempting to configure Gemini API (BEGIN) ---")
    app.logger.warning("!!! USING HARDCODED API KEY - FOR TEMPORARY TESTING ONLY !!!")

    loggable_key_part = "NOT_PROCESSED_FOR_LOGGING"
    if api_key_to_use:
        if len(api_key_to_use) > 8:
            loggable_key_part = f"'{api_key_to_use[:5]}...{api_key_to_use[-3:]}' (Length: {len(api_key_to_use)})"
        elif len(api_key_to_use) > 0:
            loggable_key_part = f"'{api_key_to_use}' (Length: {len(api_key_to_use)}, logged full)"
        else:
            loggable_key_part = "'EMPTY_STRING_HARDCODED'"
        app.logger.info(f"Using hardcoded API Key: {loggable_key_part}")

        placeholders = ["YOUR_API_KEY_HERE", "AIzaSyAVwcIqPRKr6b4jiL43hSCvuaFt_A92stQ"] # Your old placeholder
        if api_key_to_use in placeholders:
            app.logger.error(f"CRITICAL: The hardcoded API_KEY ('{loggable_key_part}') is a KNOWN PLACEHOLDER.")
        else:
            genai.configure(api_key=api_key_to_use)
            app.logger.info("Gemini API configured successfully using HARDCODED key.")
            gemini_api_configured = True
    else:
        app.logger.error("CRITICAL: Hardcoded GEMINI_API_KEY is None or empty.")

    # For debugging what's available in genai.types if issues persist:
    # app.logger.info(f"Available in genai.types: {dir(genai.types)}")

except Exception as e:
    genai_module_details = "Genai module not inspected before error."
    if 'genai' in globals() and genai:
        genai_module_details = f"Name: {getattr(genai, '__name__', 'N/A')}, Path: {getattr(genai, '__file__', 'N/A')}"
    app.logger.error(f"ERROR: Exception during Gemini API configuration (using hardcoded key). Loggable key: {loggable_key_part}. Genai details: {genai_module_details}. ExceptionType: {type(e).__name__}, Message: {e}")
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
        app.logger.error("Chat handler: Gemini API not configured. Check startup logs.")
        return jsonify({"error": "Backend Gemini API not configured. Please check server logs."}), 500

    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    history_json = request.form.get('history', '[]')
    conversation_id = request.form.get('conversation_id', '')

    try:
        history_context = json.loads(history_json)
        if not isinstance(history_context, list):
            raise ValueError("History is not a list")
    except Exception as e:
        app.logger.warning(f"Invalid history format: {e}. Received: {history_json[:200]}")
        return jsonify({"error": "Invalid history format."}), 400

    current_user_parts = []
    uploaded_file_details_for_frontend = None
    temp_file_path = None

    try:
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            if not filename:
                app.logger.warning(f"Uploaded file name '{uploaded_file_obj.filename}' sanitized to empty.")
                return jsonify({"error": "Invalid or insecure file name provided."}), 400
            # ... (rest of file processing) ...
            unique_filename = f"{conversation_id or 'conv'}_{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            uploaded_file_obj.save(temp_file_path)
            uploaded_gemini_file = genai.upload_file(path=temp_file_path, display_name=filename)
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

        if text_prompt:
            current_user_parts.append({"text": text_prompt})

        if not current_user_parts:
            return jsonify({"error": "No prompt or file content provided."}), 400

        system_instruction = """...""" # Your system prompt
        prompt_injection = [
            {"role": "user", "parts": [{"text": system_instruction}]},
            {"role": "model", "parts": [{"text": "Understood."}]}
        ]
        gemini_contents = prompt_injection + history_context + [{"role": "user", "parts": current_user_parts}]

        # *** MODIFIED TOOL DEFINITION ***
        # To enable Google Search, pass an empty dictionary to google_search_retrieval.
        # This tells the Tool to use its default Google Search capability.
        tools_list = [
            genai.types.Tool(
                google_search_retrieval={}  # Use an empty dict to enable default Google Search
            )
        ]
        app.logger.info(f"Tools configured: {tools_list}")

        generation_settings = genai.types.GenerationConfig()
        model_name_to_use = "models/gemini-2.5-flash-preview-04-17"
        model_instance = genai.GenerativeModel(model_name=model_name_to_use)
        
        app.logger.info(f"Calling model.generate_content on '{model_instance.model_name}' with tools.")
        response = model_instance.generate_content(
            contents=gemini_contents,
            generation_config=generation_settings,
            tools=tools_list
        )
        app.logger.info("Received response from Gemini generate_content.")

        reply_text = ""
        # ... (rest of your response processing logic, which seemed fine) ...
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason_val = response.prompt_feedback.block_reason
            block_message_val = getattr(response.prompt_feedback, 'block_reason_message', "No specific message.")
            app.logger.warning(f"Gemini response blocked. Reason: {block_reason_val}, Message: {block_message_val}")
            return jsonify({"error": f"Content blocked by AI: {block_reason_val}. {block_message_val}"}), 400

        if not response.candidates:
            app.logger.warning("No candidates in Gemini response.")
            return jsonify({"error": "No response generated (no candidates)."}), 500
        
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text is not None:
                    reply_text += part.text
                elif hasattr(part, 'function_call'): # Note: function_call from Google Search is handled by the model
                     app.logger.info(f"Model used a tool (function_call likely part of search): {part.function_call}")
        elif hasattr(response, 'text') and response.text is not None:
             reply_text = response.text
        else:
            app.logger.warning("Response candidate has no text parts or direct .text content.")
            # If the model only made a tool call and didn't return text in the same turn, reply_text could be empty.
            # This is expected if the tool call is for information gathering. The model should then generate text in a subsequent turn.
            # For simple Google Search retrieval, the model usually incorporates the search results directly into its text response.

        result = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            result["uploaded_file_details"] = uploaded_file_details_for_frontend
        
        return jsonify(result)

    except genai.types.BlockedPromptException as bpe:
        # ... (your existing BlockedPromptException handling) ...
        block_reason = getattr(bpe.response.prompt_feedback, 'block_reason', "Unknown")
        block_message = getattr(bpe.response.prompt_feedback, 'block_reason_message', "No specific message.")
        app.logger.warning(f"BlockedPromptException. Reason: {block_reason}, Msg: {block_message}")
        return jsonify({"error": f"Blocked by AI: {block_reason}. {block_message}"}),400

    except Exception as e:
        app.logger.error(f"Unhandled error in chat_handler: {type(e).__name__} - {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e_remove:
                app.logger.error(f"Failed to remove temp file '{temp_file_path}': {e_remove}")

if __name__ == '__main__':
    if not gemini_api_configured:
        app.logger.critical("CRITICAL: Gemini API not configured (hardcoded key). Server not started effectively.")
    else:
        app.logger.info("Starting Flask dev server (Gemini API configured with HARDCODED key).")
        app.logger.warning("!!! SERVER RUNNING WITH HARDCODED API KEY - INSECURE !!!")
        app.run(host='0.0.0.0', port=5000, debug=True)
