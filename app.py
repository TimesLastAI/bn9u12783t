# --- (Keep imports and config the same) ---
import os
import google.generativeai as genai
# REMOVE or comment out: from google.generativeai import types # Not needed for parts now
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import werkzeug
import time
import traceback

# --- (Keep GEMINI_API_KEY and UPLOAD_FOLDER) ---
GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" # Use os.environ.get in production!
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created upload folder: {UPLOAD_FOLDER}")
    except OSError as e:
        print(f"ERROR: Could not create upload folder {UPLOAD_FOLDER}: {e}")

# --- (Keep Flask App Setup and CORS) ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}})
print("CORS configured for /chat with origins: *")

# --- (Keep Gemini Client Initialization) ---
model = None
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY missing.")
else:
    try:
        print("Configuring Gemini client...")
        genai.configure(api_key=GEMINI_API_KEY)
        # Use a valid model name, e.g., 1.5 Pro or 1.5 Flash
        model_name = 'gemini-1.5-pro-latest' # Or 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel(model_name)
        print(f"Gemini client initialized with model: {model_name}")
    except Exception as e:
        print(f"ERROR: Failed to configure or initialize Gemini client: {e}")
        traceback.print_exc()


@app.route('/')
def root():
    return jsonify({"status": "Backend is running", "gemini_configured": model is not None}), 200


@app.route('/chat', methods=['POST'])
def chat_handler():
    if model is None:
         print("ERROR: /chat called but Gemini model is not available.")
         return jsonify({"error": "Backend Gemini client not configured. Check API Key/Server Logs."}), 500

    print("-" * 20)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Received request on /chat")

    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')

    print(f"Form Data - Prompt: '{text_prompt}'")
    print(f"File Received: {'Yes, filename: ' + uploaded_file_obj.filename if uploaded_file_obj and uploaded_file_obj.filename else 'No'}")

    if not text_prompt and not uploaded_file_obj:
        print("ERROR: Request rejected - No prompt or file provided.")
        return jsonify({"error": "No prompt or file provided"}), 400

    # --- Prepare parts for Gemini (MODIFIED) ---
    gemini_parts = [] # This will now hold strings and/or file objects
    uploaded_gemini_file_info = None
    temp_file_path = None

    try:
        # --- Handle File Upload (if provided) ---
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            unique_filename = f"{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            try:
                print(f"Attempting to save uploaded file temporarily to: {temp_file_path}")
                uploaded_file_obj.save(temp_file_path)
                print(f"File saved successfully. Size: {os.path.getsize(temp_file_path)} bytes")

                print("Uploading file to Gemini API...")
                uploaded_gemini_file_info = genai.upload_file(path=temp_file_path)
                print(f"Gemini file upload successful. URI: {uploaded_gemini_file_info.uri}, MIME Type: {uploaded_gemini_file_info.mime_type}")

                # *** MODIFICATION HERE ***
                # Append the File object returned by upload_file directly
                gemini_parts.append(uploaded_gemini_file_info)
                # No need for types.Part.from_uri anymore

            except Exception as upload_err:
                 print(f"ERROR: Gemini file upload or saving failed: {upload_err}")
                 traceback.print_exc()
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path)
                     except Exception: pass
                 return jsonify({"error": f"Failed processing uploaded file: {upload_err}"}), 500

        # --- Handle Text Prompt (if provided) ---
        if text_prompt:
            # *** MODIFICATION HERE ***
            # Append the text string directly
            gemini_parts.append(text_prompt)
            # No need for types.Part.from_text anymore

        if not gemini_parts:
             print("ERROR: Cannot generate content with no parts (logic error?).")
             return jsonify({"error": "Internal error: No content parts generated"}), 500

        # --- Call Gemini API ---
        print(f"Calling Gemini generate_content with {len(gemini_parts)} parts...")
        # The library now understands a list containing strings and File objects
        # No need to construct types.Content manually for a simple user turn

        # *** MODIFICATION HERE (if you were using types.Content before) ***
        # Just pass the list of parts directly as the contents for a single turn message
        contents_for_gemini = gemini_parts

        # --- (Keep Safety Settings and Generation Config) ---
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            # ... other settings ...
        ]
        generation_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
        )

        # Call generate_content (passing parts directly)
        response = model.generate_content(
            contents=contents_for_gemini, # Pass the list directly
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        print("Gemini generate_content response received.")

        # --- (Keep Response Processing, Error Handling, and Finally block the same) ---
        reply_text = ""
        error_msg = None
        try:
            # ... (rest of the response processing logic remains the same) ...
            if response.candidates:
                 candidate = response.candidates[0]
                 if candidate.content and candidate.content.parts:
                     reply_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                     print(f"Successfully extracted reply text (len={len(reply_text)}).")
                 # ... (rest of error checking for candidate) ...
            # ... (rest of error checking for response) ...
        except Exception as resp_err:
            # ... (response error handling) ...
            error_msg = "Error processing the model's response."

        if error_msg:
            print(f"Returning error to frontend: {error_msg}")
            return jsonify({"error": error_msg}), 500
        else:
            print(f"Returning success reply to frontend (len={len(reply_text)}).")
            return jsonify({"reply": reply_text})

    except Exception as e:
        print(f"ERROR: An unexpected error occurred in /chat handler: {e}")
        traceback.print_exc()
        return jsonify({"error": f"An internal server error occurred on the backend."}), 500

    finally:
        # --- (Keep cleanup logic) ---
        if temp_file_path and os.path.exists(temp_file_path):
            # ... (cleanup) ...
        print("-" * 20)


# --- (Keep __main__ block for local testing if desired) ---
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=5000, debug=True)
