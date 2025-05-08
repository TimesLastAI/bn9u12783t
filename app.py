import os
from google import genai # Assuming this is your intended import for the google-generativeai main module
from google.genai import types # Assuming this is your intended import for its types
from flask import Flask, request, jsonify, json
from flask_cors import CORS
import werkzeug  # For secure_filename
import time
import traceback
import logging # Import standard logging

# --- Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo") # IMPORTANT: Replace or use env var
if GEMINI_API_KEY == "YOUR_API_KEY_HERE" or GEMINI_API_KEY == "AIzaSyAVwcIqPRKr6b4jiL43hSCvuaFt_A92stQ": # Also check against your placeholder
    print("\n---> WARNING: Using placeholder API Key. <---")
    print("---> SET the GEMINI_API_KEY environment variable or replace the placeholder in app.py! <---\n")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}}) # Adjust "*" to your frontend domain in production
print("CORS configured for /chat with origins: *")

# --- Setup Flask Logging ---
if not app.debug:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info("Flask logger configured for non-debug mode.")
else:
    app.logger.setLevel(logging.DEBUG)
    app.logger.info("Flask logger running in debug mode.")


# --- Initialize Gemini ---
gemini_api_configured = False
try:
    app.logger.info(f"Attempting to configure Gemini API...")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE" or GEMINI_API_KEY == "AIzaSyAVwcIqPRKr6b4jiL43hSCvuaFt_A92stQ":
        app.logger.error("CRITICAL: Gemini API Key is missing or is a placeholder. SET the GEMINI_API_KEY environment variable.")
    else:
        genai.configure(api_key=GEMINI_API_KEY) # Configure the API key globally
        app.logger.info("Gemini API configured successfully.")
        gemini_api_configured = True
except Exception as e:
    app.logger.error(f"ERROR: Failed to configure Gemini API: {e}")
    app.logger.error(traceback.format_exc())

# --- Routes ---
@app.route('/')
def root():
    app.logger.info("Root endpoint '/' accessed.")
    return jsonify({"status": "Backend running", "gemini_api_configured": gemini_api_configured}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    app.logger.info("Chat handler '/chat' invoked (POST).")
    if not gemini_api_configured:
        app.logger.error("Chat handler: Gemini API not configured.")
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
            if not filename: # Sanity check after secure_filename
                app.logger.warning(f"Uploaded file name '{uploaded_file_obj.filename}' was sanitized to an empty string.")
                return jsonify({"error": "Invalid or insecure file name provided."}), 400

            unique_filename = f"{conversation_id or 'conv'}_{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
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
                # Use genai.upload_file (from the main 'genai' module)
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

        system_instruction = """...""" # Your extensive system prompt remains here
        prompt_injection = [
            {"role": "user", "parts": [{"text": system_instruction}]},
            {"role": "model", "parts": [{"text": "Understood."}]}
        ]
        gemini_contents = prompt_injection + history_context + [{"role": "user", "parts": current_user_parts}]
        app.logger.debug(f"Prepared 'gemini_contents' with {len(gemini_contents)} total items. Last user part has {len(current_user_parts)} part(s).")

        # --- Tools and Generation Config ---
        # Use types.Tool and types.GoogleSearchRetrieval for Google Search
        tools_list = [types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())]
        
        # GenerationConfig for parameters like temperature, top_p, etc.
        # The 'tools' parameter is passed separately to generate_content.
        generation_settings = types.GenerationConfig(
            # Add any specific generation parameters here if needed, e.g.:
            # temperature=0.7,
            # max_output_tokens=2048,
            # response_mime_type="text/plain" # Can be set if you want to ensure specific mime type
        )
        app.logger.debug(f"GenerationConfig prepared. Tools enabled: Google Search.")

        # --- Model Instantiation and Call ---
        model_name_to_use = "models/gemini-2.5-flash-preview-04-17" # Your original model name
        app.logger.info(f"Initializing GenerativeModel with: '{model_name_to_use}'")
        
        # Create a GenerativeModel instance
        model_instance = genai.GenerativeModel(model_name=model_name_to_use)
        
        app.logger.info(f"Calling model.generate_content on '{model_instance.model_name}'")
        try:
            response = model_instance.generate_content(
                contents=gemini_contents,
                generation_config=generation_settings, # Pass the GenerationConfig object
                tools=tools_list                       # Pass tools list separately
            )
            app.logger.info("Received response from Gemini generate_content.")
            app.logger.debug(f"Full Gemini Response (first 500 chars): {str(response)[:500]}")
        except Exception as e_gemini_generate:
            app.logger.error(f"Error during Gemini generate_content call: {e_gemini_generate}")
            app.logger.error(traceback.format_exc())
            return jsonify({"error": f"AI model failed to generate response: {e_gemini_generate}"}), 500

        # Extract reply
        reply_text = ""
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            block_message = response.prompt_feedback.block_reason_message if hasattr(response.prompt_feedback, 'block_reason_message') else "No specific message."
            app.logger.warning(f"Gemini response was blocked. Reason: {block_reason}, Message: {block_message}")
            return jsonify({"error": f"Content blocked by AI safety filters: {block_reason}. {block_message}"}), 400

        if not response.candidates:
            app.logger.warning("No candidates in Gemini response after successful call (and not blocked).")
            return jsonify({"error": "No response generated by the model (no candidates)."}), 500
        
        candidate = response.candidates[0]
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'text') and part.text: # Check if text exists and is not empty
                    reply_text += part.text
                # elif hasattr(part, 'function_call'): # Handle function calls if your model uses them
                #    app.logger.info(f"Model returned a function call: {part.function_call}")
        elif hasattr(response, 'text') and response.text:
             reply_text = response.text
        else:
            app.logger.warning("Gemini response candidate has no text parts or direct .text attribute.")
            # Check for tool calls that might not return immediate text
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, 'function_call'):
                        app.logger.info(f"Model returned a function call, but no immediate text: {part.function_call}")
                        # Here you would handle the function call and potentially make another call to the model
                        # For now, if only a function call is returned without text, reply_text will be empty.
                        break # Or continue if multiple parts could exist


        app.logger.info(f"Extracted reply_text (first 100 chars): '{reply_text[:100]}'")

        result = {"reply": reply_text}
        if uploaded_file_details_for_frontend:
            result["uploaded_file_details"] = uploaded_file_details_for_frontend
        
        app.logger.info("Chat handler finished successfully. Sending response to frontend.")
        return jsonify(result)

    except types.BlockedPromptException as bpe: # Use 'types' as per your import
        block_reason = "Unknown"
        block_message = "No specific message."
        if bpe.response and bpe.response.prompt_feedback:
            block_reason = bpe.response.prompt_feedback.block_reason
            block_message = bpe.response.prompt_feedback.block_reason_message if hasattr(bpe.response.prompt_feedback, 'block_reason_message') else "No specific message."
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
    if not gemini_api_configured:
        app.logger.critical("ERROR: Cannot start server - Gemini API not configured. Check API key and initialization logs.")
    else:
        app.logger.info("Starting Flask development server.")
        app.run(host='0.0.0.0', port=5000, debug=True)
