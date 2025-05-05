import os
import google.generativeai as genai
# import google.generativeai.types as types # <-- No longer needed for config
from flask import Flask, request, jsonify, json
from flask_cors import CORS
import werkzeug
import time
import traceback

# --- Configuration ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAVwcIqPRKr6b4jiL43hSCvuaFt_A92stQ") # Replace or use env var
if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
    print("\n---> WARNING: Using placeholder API Key. <---")
    print("---> SET the GEMINI_API_KEY environment variable or replace the placeholder in app.py! <---\n")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}})
print("CORS configured for /chat with origins: *")

# --- Gemini Client Initialization ---
model = None
# Default safety settings (can be overridden per request if needed, but often set here)
safety_settings_none = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# --- System Prompt (Make sure it's cleaned of problematic content) ---
system_instruction = """you are a helpful assistant"""


# --- Initialize Gemini Model (WITHOUT system_instruction) ---
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_API_KEY_HERE":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = 'gemini-2.5-flash-preview-04-17'
        print(f"Initializing Gemini model: {model_name} (System Prompt will be injected per request).")

        model = genai.GenerativeModel(
            model_name,
            # No system_instruction here
            safety_settings=safety_settings_none # Set default safety for the model instance
            )
        print(f"Gemini client initialized successfully.")
    except Exception as e:
        print(f"ERROR: Failed to init Gemini client: {e}")
        traceback.print_exc()
        model = None
else:
    print("ERROR: GEMINI_API_KEY missing or invalid.")
    model = None

# --- Routes ---
@app.route('/')
def root():
    print("Root route '/' accessed.")
    return jsonify({"status": "Backend running", "gemini_configured": model is not None}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    if model is None:
        print("ERROR: /chat called but Gemini model is not available.")
        return jsonify({"error": "Backend Gemini client not configured."}), 500

    print("-" * 20); print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # --- Extract Data ---
    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    history_json = request.form.get('history', '[]')
    conversation_id = request.form.get('conversation_id', '')

    print(f"Conversation ID: {conversation_id}")
    print(f"Prompt: '{text_prompt[:100]}...'")
    print(f"File: {'Yes - ' + uploaded_file_obj.filename if uploaded_file_obj and uploaded_file_obj.filename else 'No'}")

    # --- Parse History ---
    try:
        history = json.loads(history_json)
        print(f"Received History ({len(history)} messages): {history_json[:200]}...")
    except Exception as e:
        print(f"ERROR parsing history JSON: {e}")
        return jsonify({"error": "Invalid or malformed history received."}), 400

    if not text_prompt and not uploaded_file_obj:
        print("ERROR: Request rejected - No prompt or file provided.")
        return jsonify({"error": "No prompt or file provided"}), 400

    # --- Prepare Content ---
    current_user_parts = []
    uploaded_gemini_file_info = None
    temp_file_path = None

    try:
        # --- Handle File Upload ---
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            unique_filename = f"{conversation_id or 'new'}_{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            try:
                uploaded_file_obj.save(temp_file_path)
                print(f"File saved locally: {temp_file_path}")
                print("Uploading file to Gemini API...")
                uploaded_gemini_file_info = genai.upload_file(
                    path=temp_file_path, display_name=filename
                )
                print(f"File uploaded to Gemini. URI: {uploaded_gemini_file_info.uri}")
                current_user_parts.append(uploaded_gemini_file_info)
            except Exception as upload_err:
                 print(f"ERROR Uploading file: {upload_err}"); traceback.print_exc()
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path); print("Cleaned temp file after upload error.")
                     except Exception as clean_err: print(f"WARN: Cleanup failed: {clean_err}")
                 return jsonify({"error": f"File upload failed: {upload_err}"}), 500
            finally:
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path); print("Cleaned up temp file.")
                     except Exception as clean_err: print(f"WARN: Cleanup failed: {clean_err}")
                     temp_file_path = None

        # --- Handle Text Prompt ---
        if text_prompt:
            current_user_parts.append({"text": text_prompt})

        # --- Construct final contents list with INJECTED prompt ---
        prompt_injection_contents = [
            {"role": "user", "parts": [{"text": system_instruction}]},
            {"role": "model", "parts": [{"text": "Understood."}]}
        ]
        gemini_contents = prompt_injection_contents + history + [{"role": "user", "parts": current_user_parts}]

        if not current_user_parts:
             print("ERROR: No parts for the current user message.")
             return jsonify({"error": "Internal error: No user message content"}), 500

        # --- Define Generation Config as a DICTIONARY ---
        generation_config_dict = {
            "response_mime_type": "text/plain",
            # Add other config like temperature here if needed:
            # "temperature": 0.7,
            # "max_output_tokens": 1024,
        }

        # --- Define Safety Settings as a LIST of DICTIONARIES for this request ---
        safety_settings_list = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        print(f"Calling Gemini with {len(gemini_contents)} content blocks (including injected prompt)...")

        # --- Call Gemini API ---
        response = model.generate_content(
            contents=gemini_contents,
            generation_config=generation_config_dict, # Pass dictionary
            safety_settings=safety_settings_list    # Pass list of dictionaries
        )

        print("Gemini response received.")

        # --- Process Response (Keep existing logic) ---
        reply_text = ""
        error_msg = None
        try:
            reply_text = response.text
            print(f"Extracted reply via .text (len={len(reply_text)} chars).")
        except ValueError as ve:
            print(f"WARN: ValueError accessing response.text: {ve}")
            print(f"Prompt Feedback: {response.prompt_feedback}")
            if response.candidates:
                 candidate = response.candidates[0]
                 reason = candidate.finish_reason.name if candidate.finish_reason else "Unknown"
                 print(f"Candidate Finish Reason: {reason}")
                 print(f"Candidate Safety Ratings: {candidate.safety_ratings}")
                 if reason == 'SAFETY': error_msg = f"Response blocked by safety filters ({reason})."
                 else: error_msg = f"Response generation stopped ({reason})."
            else:
                 block_reason = response.prompt_feedback.block_reason.name if response.prompt_feedback.block_reason else "Unknown"
                 error_msg = f"Request blocked (Reason: {block_reason}). No candidates."
            print(f"Constructed Error Message: {error_msg}")
        except Exception as resp_err:
             print(f"ERROR: Unexpected error processing Gemini response: {resp_err}")
             traceback.print_exc()
             error_msg = "Error processing model response."

        # --- Return Response to Frontend ---
        if error_msg:
             print(f"Returning error to frontend: {error_msg}")
             return jsonify({"error": error_msg}), 500
        else:
             print(f"Returning success reply to frontend (len={len(reply_text)} chars).")
             return jsonify({"reply": reply_text})

    except Exception as e:
        print(f"ERROR in /chat handler: {e}"); traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

# --- Main Execution Guard ---
if __name__ == '__main__':
    if model is None:
         print("\nERROR: Cannot start Flask server - Gemini client failed to initialize.\n")
    else:
         print("\nStarting Flask development server on http://0.0.0.0:5000 ...\n")
         app.run(host='0.0.0.0', port=5000, debug=True)
