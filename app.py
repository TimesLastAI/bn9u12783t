import os
# Imports based on your working examples and the older SDK pattern
from google import genai
from google.genai import types

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
    if gunicorn_logger: app.logger.handlers.extend(gunicorn_logger.handlers)
    app.logger.info("Flask logger configured for non-debug mode (production).")
else:
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Flask logger running in debug mode.")

app.logger.info(f"Upload folder '{UPLOAD_FOLDER}' checked/created.")
app.logger.info("--- Python script starting up (Top of script) ---")

# --- Initialize Gemini Client (Pattern from your examples) ---
gemini_client = None
gemini_api_configured = False
api_key_to_use = HARDCODED_GEMINI_API_KEY

try:
    app.logger.info("--- Attempting to initialize Gemini Client (genai.Client pattern) ---")
    app.logger.warning("!!! USING HARDCODED API KEY - FOR TEMPORARY TESTING ONLY !!!")

    loggable_key_part = "NOT_PROCESSED"
    if api_key_to_use:
        if len(api_key_to_use) > 8: loggable_key_part = f"'{api_key_to_use[:5]}...{api_key_to_use[-3:]}'"
        elif len(api_key_to_use) > 0: loggable_key_part = f"'{api_key_to_use}' (short key)"
        else: loggable_key_part = "'EMPTY_STRING_HARDCODED'"
        app.logger.info(f"Using hardcoded API Key: {loggable_key_part} to init genai.Client.")

        gemini_client = genai.Client(api_key=api_key_to_use)
        app.logger.info("Successfully initialized genai.Client with HARDCODED key.")
        gemini_api_configured = True
    else:
        app.logger.error("CRITICAL: Hardcoded GEMINI_API_KEY is None or empty.")

except Exception as e:
    app.logger.error(f"ERROR: Exception during Gemini Client initialization. Key: {loggable_key_part}. Exception: {type(e).__name__} - {e}")
    app.logger.error(traceback.format_exc())

app.logger.info(f"--- Gemini API Configuration Status at end of init block: {gemini_api_configured} ---")

# --- Routes ---
@app.route('/')
def root():
    app.logger.info(f"Root endpoint '/' accessed. Client Initialized: {gemini_api_configured}")
    return jsonify({"status": "Backend running", "gemini_api_configured": gemini_api_configured}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    app.logger.info("Chat handler '/chat' invoked (POST).")
    if not gemini_client or not gemini_api_configured:
        app.logger.error("Chat handler: Gemini client not initialized or API not configured.")
        return jsonify({"error": "Backend Gemini client not initialized. Check server logs."}), 500

    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    history_json = request.form.get('history', '[]')

    try:
        history_context = json.loads(history_json)
        if not isinstance(history_context, list): raise ValueError("History not a list")
    except Exception as e:
        app.logger.warning(f"Invalid history format: {e}. Received: {history_json[:200]}")
        return jsonify({"error": "Invalid history format."}), 400

    current_user_parts_for_sdk = []
    uploaded_file_details_for_frontend = None
    temp_file_path = None

    try:
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            if not filename:
                return jsonify({"error": "Invalid file name."}), 400
            
            unique_filename = f"{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            uploaded_file_obj.save(temp_file_path)
            app.logger.info(f"File saved to {temp_file_path}. Uploading to Gemini Files API...")

            gemini_uploaded_file_obj = gemini_client.files.upload(file=temp_file_path)
            app.logger.info(f"File uploaded to Gemini. URI: {gemini_uploaded_file_obj.uri}")

            current_user_parts_for_sdk.append(types.Part.from_uri(
                file_uri=gemini_uploaded_file_obj.uri,
                mime_type=gemini_uploaded_file_obj.mime_type
            ))
            uploaded_file_details_for_frontend = {
                "uri": gemini_uploaded_file_obj.uri, "mime_type": gemini_uploaded_file_obj.mime_type, "name": gemini_uploaded_file_obj.display_name
            }

        if text_prompt:
            current_user_parts_for_sdk.append(types.Part.from_text(text=text_prompt))

        if not current_user_parts_for_sdk:
            return jsonify({"error": "No prompt or file content provided."}), 400

        sdk_contents = []
        # System prompt handling: Your system prompt should ideally be the first message(s) in history_context.
        # Or, construct it here if it's static and needs to be prepended.
        # Example static system prompt prepending:
        # system_instruction_text = "You are a helpful assistant." # Your actual system prompt
        # sdk_contents.append(types.Content(role="user", parts=[types.Part.from_text(system_instruction_text)]))
        # sdk_contents.append(types.Content(role="model", parts=[types.Part.from_text("Understood.")]))

        for hist_item in history_context: # Process actual chat history
            sdk_hist_parts = []
            for part_data in hist_item.get("parts", []):
                if "text" in part_data:
                    sdk_hist_parts.append(types.Part.from_text(text=part_data["text"]))
                elif "file_data" in part_data and "file_uri" in part_data["file_data"] and "mime_type" in part_data["file_data"]:
                     sdk_hist_parts.append(types.Part.from_uri(
                         file_uri=part_data["file_data"]["file_uri"],
                         mime_type=part_data["file_data"]["mime_type"]
                     ))
            if sdk_hist_parts:
                 sdk_contents.append(types.Content(role=hist_item["role"], parts=sdk_hist_parts))
        
        sdk_contents.append(types.Content(role="user", parts=current_user_parts_for_sdk))
        
        # Tool configuration
        tools_for_sdk_call = [
            types.Tool(google_search=types.GoogleSearch()),
        ]
        app.logger.info(f"Tools configured for SDK call: {tools_for_sdk_call}")

        # This is the GenerateContentConfig object that holds tools and other settings
        sdk_generate_content_config = types.GenerateContentConfig(
            tools=tools_for_sdk_call,
            # response_mime_type="text/plain", # Optional
        )
        
        model_to_use = "models/gemini-2.5-flash-preview-04-17"
        app.logger.info(f"Calling client.models.generate_content on '{model_to_use}' with config.")

        # *** MODIFIED API CALL: Use 'config=' parameter ***
        response = gemini_client.models.generate_content( # Non-streaming version for now
            model=model_to_use,
            contents=sdk_contents,
            generation_config=sdk_generate_content_config # Use 'generation_config' if that's what this client.models.generate_content expects
                                                       # OR use 'config=sdk_generate_content_config' if that's the correct param name
                                                       # The error message will guide us if this is still wrong for this specific SDK version.
                                                       # Based on your example for streaming, it was 'config'. Let's try that.
        )
        # *** Re-checking your example, it used 'config'. Let's stick to that for the client.models.generate_content call ***
        response = gemini_client.models.generate_content(
            model=model_to_use,
            contents=sdk_contents,
            config=sdk_generate_content_config # <<<<----- CORRECTED PARAMETER NAME
        )

        app.logger.info("Received response from Gemini generate_content.")
        
        reply_text = ""
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            return jsonify({"error": f"Content blocked by API: {response.prompt_feedback.block_reason}"}), 400

        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.text:
                    reply_text += part.text
        elif hasattr(response, 'text') and response.text:
            reply_text = response.text
        
        result = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            result["uploaded_file_details"] = uploaded_file_details_for_frontend
        
        return jsonify(result)

    except Exception as e:
        app.logger.error(f"Unhandled error in chat_handler: {type(e).__name__} - {str(e)}")
        app.logger.error(traceback.format_exc())
        # Check if the error is due to the model not supporting tools
        if "Search Grounding is not supported" in str(e) or (hasattr(e, 'grpc_status_code') and e.grpc_status_code == 3): # 3 is often InvalidArgument
            app.logger.warning("The model likely does not support the requested tool (Google Search). Consider changing the model.")
            return jsonify({"error": f"Model error: {str(e)}. Search tool might not be supported by this model."}), 400
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path)
            except Exception as e_remove: app.logger.error(f"Failed to remove temp: {e_remove}")

if __name__ == '__main__':
    if not gemini_api_configured:
        app.logger.critical("CRITICAL: Gemini Client not initialized (hardcoded key). Server not effective.")
    else:
        app.logger.info("Starting Flask dev server (Gemini Client initialized with HARDCODED key).")
        app.logger.warning("!!! SERVER RUNNING WITH HARDCODED API KEY - INSECURE !!!")
        app.run(host='0.0.0.0', port=5000, debug=True)
