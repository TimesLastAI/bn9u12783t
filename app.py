import os
import google.generativeai as genai
# types is not needed for config inline or simplified parts
from flask import Flask, request, jsonify
from flask_cors import CORS
import werkzeug
import time
import traceback

# --- Configuration ---
# !! SECURITY WARNING: Use environment variables for API Key !!
GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" # Replace with your key or use os.environ.get
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, resources={r"/chat": {"origins": "*"}}) # Allow all origins for /chat
print("CORS configured for /chat with origins: *")

# --- Gemini Client Initialization ---
model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = 'gemini-1.5-pro-latest' # Or 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel(model_name)
        print(f"Gemini client initialized with model: {model_name}")
    except Exception as e:
        print(f"ERROR: Failed to init Gemini client: {e}")
        traceback.print_exc()
else:
    print("ERROR: GEMINI_API_KEY missing.")

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
    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    print(f"Prompt: '{text_prompt}', File: {'Yes ' + uploaded_file_obj.filename if uploaded_file_obj and uploaded_file_obj.filename else 'No'}")

    if not text_prompt and not uploaded_file_obj:
        print("ERROR: Request rejected - No prompt or file provided.")
        return jsonify({"error": "No prompt or file provided"}), 400

    gemini_parts = []
    uploaded_gemini_file_info = None
    temp_file_path = None

    try:
        # --- Handle File Upload ---
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            unique_filename = f"{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            try:
                uploaded_file_obj.save(temp_file_path)
                print(f"File saved to {temp_file_path}")
                print("Uploading to Gemini...")
                uploaded_gemini_file_info = genai.upload_file(path=temp_file_path)
                print(f"Uploaded. URI: {uploaded_gemini_file_info.uri}")
                gemini_parts.append(uploaded_gemini_file_info)
            except Exception as upload_err:
                 print(f"ERROR Uploading: {upload_err}"); traceback.print_exc()
                 if temp_file_path and os.path.exists(temp_file_path): os.remove(temp_file_path)
                 return jsonify({"error": f"Upload failed: {upload_err}"}), 500

        # --- Handle Text Prompt ---
        if text_prompt:
            gemini_parts.append(text_prompt)

        if not gemini_parts:
             return jsonify({"error": "No content parts"}), 500

        # --- Call Gemini API ---
        print(f"Calling Gemini with {len(gemini_parts)} parts (NO safety settings)...")

        # *** REMOVED SAFETY SETTINGS ***
        # *** Define generation config inline ***
        generation_config_dict = {
            "response_mime_type": "text/plain",
            # "temperature": 0.7, # Optional
        }

        # Make the API call WITHOUT safety_settings
        response = model.generate_content(
            contents=gemini_parts,
            generation_config=generation_config_dict
            # safety_settings parameter is omitted
        )
        print("Gemini response received.")

        # --- Process Response ---
        reply_text = ""
        error_msg = None
        try:
             # Attempt to get text directly first
             reply_text = response.text
             print(f"Extracted reply via .text (len={len(reply_text)}).")
        except AttributeError:
             # Fallback if .text doesn't exist or response blocked before text generation
             print(f"WARN: response.text attribute not found. Checking candidates/parts.")
             try:
                  if response.candidates:
                       candidate = response.candidates[0]
                       if candidate.content and candidate.content.parts:
                            reply_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                            print(f"Extracted reply via manual part join (len={len(reply_text)}).")
                       else: # Candidate exists but no content/parts
                            finish_reason_name = candidate.finish_reason.name if candidate.finish_reason else 'UNKNOWN'
                            print(f"WARN: Candidate missing content/parts. Finish Reason: {finish_reason_name}")
                            # Check safety ratings ONLY if reason is SAFETY, otherwise just state finish reason
                            if finish_reason_name == 'SAFETY' and candidate.safety_ratings:
                                 print("Safety Ratings:", candidate.safety_ratings)
                                 # Even though settings weren't sent, the API might still block based on defaults or inherent content
                                 error_msg = f"Blocked by API safety filters (Reason: {finish_reason_name})"
                            else:
                                error_msg = f"No response content. Finish Reason: {finish_reason_name}"
                  else: # No candidates at all
                       print("WARNING: Gemini response missing candidates.")
                       error_msg = "No response generated from model."
                       if response.prompt_feedback and response.prompt_feedback.block_reason:
                            block_reason_name = response.prompt_feedback.block_reason.name
                            print(f"Prompt blocked. Reason: {block_reason_name}")
                            error_msg = f"Request blocked: {block_reason_name}"
             except Exception as parse_err:
                  print(f"ERROR: Failed fallback response parsing: {parse_err}")
                  if not error_msg: error_msg = "Error parsing model response structure."

        except Exception as resp_err:
             print(f"ERROR: Failed processing Gemini response: {resp_err}")
             traceback.print_exc()
             if not error_msg: error_msg = "Error processing model response."

        # --- Return Response to Frontend ---
        if error_msg:
             print(f"Returning error to frontend: {error_msg}")
             return jsonify({"error": error_msg}), 500
        else:
             print(f"Returning success reply to frontend (len={len(reply_text)}).")
             return jsonify({"reply": reply_text})

    except Exception as e:
        print(f"ERROR in /chat handler: {e}"); traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path); print("Cleaned temp file.")
            except Exception as clean_err: print(f"WARN: Cleanup failed: {clean_err}")
        print("-" * 20)

# --- Main Execution Guard ---
if __name__ == '__main__':
    if model is None:
         print("Cannot start Flask server locally: Gemini client failed to initialize.")
    else:
         print("Starting Flask development server locally on http://localhost:5000 ...")
         app.run(host='0.0.0.0', port=5000, debug=True)
