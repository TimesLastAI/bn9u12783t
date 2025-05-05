import os
import google.generativeai as genai
from google.generativeai import types # <<<--- ADD THIS IMPORT BACK
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import werkzeug
import time
import traceback

# --- Configuration ---
# !! SECURITY WARNING: Hardcoding API keys is not recommended. Use environment variables in production. !!
GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" # Your hardcoded key
UPLOAD_FOLDER = 'uploads'

if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created upload folder: {UPLOAD_FOLDER}")
    except OSError as e:
        print(f"ERROR: Could not create upload folder {UPLOAD_FOLDER}: {e}")

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}})
print("CORS configured for /chat with origins: *")

# --- Gemini Client Initialization ---
model = None
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY is missing in the code. Backend cannot function.")
else:
    try:
        print("Configuring Gemini client...")
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = 'gemini-1.5-pro-latest' # Or 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel(model_name)
        print(f"Gemini client initialized with model: {model_name}")
    except Exception as e:
        print(f"ERROR: Failed to configure or initialize Gemini client: {e}")
        traceback.print_exc()

# --- Routes ---

@app.route('/')
def root():
    print("Root route '/' accessed.")
    return jsonify({"status": "Backend is running", "gemini_configured": model is not None}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    if model is None:
         print("ERROR: /chat endpoint called but Gemini model is not available.")
         return jsonify({"error": "Backend Gemini client not configured. Check API Key/Server Logs."}), 500

    print("-" * 20)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Received POST request on /chat from: {request.remote_addr}")

    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')

    print(f"Form Data - Prompt: '{text_prompt}'")
    print(f"File Received: {'Yes, filename: ' + uploaded_file_obj.filename if uploaded_file_obj and uploaded_file_obj.filename else 'No'}")

    if not text_prompt and not uploaded_file_obj:
        print("ERROR: Request rejected - No prompt or file provided.")
        return jsonify({"error": "No prompt or file provided"}), 400

    gemini_parts = []
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
                gemini_parts.append(uploaded_gemini_file_info) # Append file object
            except Exception as upload_err:
                 print(f"ERROR: Gemini file upload or saving failed: {upload_err}")
                 traceback.print_exc()
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path)
                     except Exception: pass
                 return jsonify({"error": f"Failed processing uploaded file: {upload_err}"}), 500

        # --- Handle Text Prompt (if provided) ---
        if text_prompt:
            gemini_parts.append(text_prompt) # Append text string

        if not gemini_parts:
             print("ERROR: Cannot generate content with no parts (logic error?).")
             return jsonify({"error": "Internal error: No content parts generated"}), 500

        # --- Call Gemini API ---
        print(f"Calling Gemini generate_content with {len(gemini_parts)} parts...")

        # Use 'types' for config objects
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        ]
        generation_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
        )

        response = model.generate_content(
            contents=gemini_parts,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        print("Gemini generate_content response received.")

        # --- Process Response ---
        reply_text = ""
        error_msg = None
        try:
            if response.candidates:
                 candidate = response.candidates[0]
                 if candidate.content and candidate.content.parts:
                     reply_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                     print(f"Successfully extracted reply text (len={len(reply_text)}).")
                 else:
                     finish_reason_name = candidate.finish_reason.name if candidate.finish_reason else 'UNKNOWN'
                     print(f"WARNING: Gemini candidate missing content/parts. Finish Reason: {finish_reason_name}")
                     error_msg = f"No response content generated. Reason: {finish_reason_name}"
                     if finish_reason_name == 'SAFETY' and candidate.safety_ratings:
                          print("Safety Ratings:", candidate.safety_ratings)
                          error_msg += " (Blocked due to safety settings)"
            else:
                 print("WARNING: Gemini response missing candidates.")
                 error_msg = "No response generated from model."
                 if response.prompt_feedback and response.prompt_feedback.block_reason:
                      block_reason_name = response.prompt_feedback.block_reason.name
                      print(f"Prompt blocked. Reason: {block_reason_name}")
                      error_msg = f"Request blocked: {block_reason_name}"
                      if response.prompt_feedback.safety_ratings:
                           print("Prompt Feedback Safety:", response.prompt_feedback.safety_ratings)

        except AttributeError as attr_err:
            print(f"ERROR: Attribute error parsing Gemini response: {attr_err}")
            traceback.print_exc()
            error_msg = "Error parsing the structure of the model's response."
        except Exception as resp_err:
             print(f"ERROR: Failed to process Gemini response: {resp_err}")
             traceback.print_exc()
             error_msg = "Error processing the model's response."

        # --- Return Response to Frontend ---
        if error_msg:
             print(f"Returning error to frontend: {error_msg}")
             return jsonify({"error": error_msg}), 500
        else:
             print(f"Returning success reply to frontend (len={len(reply_text)}).")
             return jsonify({"reply": reply_text})

    except Exception as e:
        print(f"ERROR: An unexpected error occurred in /chat handler: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred on the backend."}), 500

    finally:
        # --- Clean up temporary file ---
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"Temporary file cleaned up: {temp_file_path}")
            except Exception as clean_err:
                print(f"WARNING: Failed to clean up temporary file {temp_file_path}: {clean_err}")

        # --- Optional: Delete the file from Gemini ---
        # if uploaded_gemini_file_info:
        #     try:
        #         # ... (delete logic) ...
        #     except Exception as del_err:
        #         # ... (delete error logging) ...

        print("-" * 20) # End log for this request

# --- Main Execution Guard ---
if __name__ == '__main__':
    # ... (optional local testing setup) ...
    if model is None:
         print("Cannot start Flask server locally: Gemini client failed to initialize (Check API Key).")
    else:
         print("Starting Flask development server locally on http://localhost:5000 ...")
         app.run(host='0.0.0.0', port=5000, debug=True)
