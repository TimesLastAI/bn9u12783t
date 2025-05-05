import os
import google.generativeai as genai
# types is not needed for config inline or simplified parts
from flask import Flask, request, jsonify, json # Added json
from flask_cors import CORS
import werkzeug
import time
import traceback

# --- Configuration ---
# !! SECURITY WARNING: Use environment variables for API Key !!
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo") # Replace or use env var
if GEMINI_API_KEY == "YOUR_API_KEY_HERE":
    print("\nWARNING: Using placeholder API Key. SET the GEMINI_API_KEY environment variable!\n")

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER): os.makedirs(UPLOAD_FOLDER)

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Restrict CORS in production if possible
CORS(app, resources={r"/chat": {"origins": "*"}}) # Allows all origins for /chat for now
print("CORS configured for /chat with origins: *")

# --- Gemini Client Initialization ---
model = None
safety_settings_none = [ # Define safety settings to be none
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_API_KEY_HERE":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Use a model that supports system instructions and history well
        model_name = 'gemini-1.5-flash-latest' # Or 'gemini-1.5-pro-latest'
        # Add system instruction if needed
        # system_instruction = "You are a helpful assistant."
        model = genai.GenerativeModel(
            model_name,
            # system_instruction=system_instruction # Uncomment if using system instruction
            safety_settings=safety_settings_none # Apply no safety settings
            )
        print(f"Gemini client initialized with model: {model_name}")
    except Exception as e:
        print(f"ERROR: Failed to init Gemini client: {e}")
        traceback.print_exc()
else:
    print("ERROR: GEMINI_API_KEY missing or placeholder.")

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

    # --- Extract Data from Form ---
    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')
    history_json = request.form.get('history', '[]') # Get history string
    conversation_id = request.form.get('conversation_id', '') # Get conv ID

    print(f"Conversation ID: {conversation_id}")
    print(f"Prompt: '{text_prompt}'")
    print(f"File: {'Yes - ' + uploaded_file_obj.filename if uploaded_file_obj and uploaded_file_obj.filename else 'No'}")

    # --- Parse History ---
    try:
        # Load history from JSON string sent by frontend
        # Ensure history alternates user/model roles correctly if needed by the model
        history = json.loads(history_json)
        print(f"Received History ({len(history)} messages): {history_json[:200]}...") # Log snippet
    except json.JSONDecodeError:
        print("ERROR: Could not decode history JSON.")
        return jsonify({"error": "Invalid history format received."}), 400
    except Exception as e:
        print(f"ERROR parsing history: {e}")
        return jsonify({"error": "Failed to process history."}), 400


    if not text_prompt and not uploaded_file_obj:
        print("ERROR: Request rejected - No prompt or file provided.")
        return jsonify({"error": "No prompt or file provided"}), 400

    # --- Prepare Content for Gemini ---
    # Gemini expects a list of contents, starting potentially with history
    # The new user message (prompt + file) should be the last item.
    current_user_parts = []
    uploaded_gemini_file_info = None
    temp_file_path = None

    try:
        # --- Handle File Upload (if present) ---
        if uploaded_file_obj and uploaded_file_obj.filename:
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            # Consider unique filenames if storing long-term, or based on conv_id
            unique_filename = f"{conversation_id or 'new'}_{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            try:
                uploaded_file_obj.save(temp_file_path)
                print(f"File saved temporarily to {temp_file_path}")
                print("Uploading file to Gemini...")
                # Display name can be useful for the model
                uploaded_gemini_file_info = genai.upload_file(
                    path=temp_file_path,
                    display_name=filename
                    )
                print(f"File uploaded to Gemini. URI: {uploaded_gemini_file_info.uri}")
                current_user_parts.append(uploaded_gemini_file_info) # Add file part first
            except Exception as upload_err:
                 print(f"ERROR Uploading file to Gemini: {upload_err}"); traceback.print_exc()
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path); print("Cleaned temp file after upload error.")
                     except Exception as clean_err: print(f"WARN: Cleanup failed: {clean_err}")
                 return jsonify({"error": f"File upload failed: {upload_err}"}), 500
            finally:
                 # Clean up temp file immediately after potential upload
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path); print("Cleaned temp file.")
                     except Exception as clean_err: print(f"WARN: Cleanup failed: {clean_err}")
                     temp_file_path = None # Ensure path is cleared


        # --- Handle Text Prompt ---
        if text_prompt:
            current_user_parts.append({"text": text_prompt}) # Add text part

        # --- Construct final contents list ---
        # Combine history and the new user message parts
        gemini_contents = history + [{"role": "user", "parts": current_user_parts}]

        # --- Validate Contents ---
        if not current_user_parts:
             print("ERROR: No content parts generated for the current user message.")
             return jsonify({"error": "Internal error: Could not prepare user message content"}), 500
        if not gemini_contents:
             print("ERROR: No contents to send to Gemini.")
             return jsonify({"error": "Internal error: No content to send"}), 500


        # --- Call Gemini API ---
        print(f"Calling Gemini with {len(gemini_contents)} total content blocks...")

        # Define generation config (can be customized)
        generation_config = genai.types.GenerationConfig(
            # temperature=0.7, # Example: Adjust creativity
            # max_output_tokens=2048, # Example: Limit response length
            response_mime_type="text/plain" # Ensure text response
        )

        # Start the chat session using the history
        # Note: For multi-turn, using start_chat might be slightly cleaner,
        # but sending the full contents list also works fine.
        # chat_session = model.start_chat(history=history)
        # response = chat_session.send_message(
        #     content={"role": "user", "parts": current_user_parts},
        #     generation_config=generation_config,
        #     # safety_settings are set on the model itself now
        # )

        # Send the whole list (history + new message)
        response = model.generate_content(
            contents=gemini_contents,
            generation_config=generation_config,
            # safety_settings are set on the model itself now
        )

        print("Gemini response received.")

        # --- Process Response ---
        reply_text = ""
        error_msg = None
        try:
             # Attempt to get text directly
             reply_text = response.text
             print(f"Extracted reply via .text (len={len(reply_text)} chars).")
        except ValueError as ve:
            # This often indicates blocked content or other issues before text generation
            print(f"WARN: ValueError accessing response.text: {ve}")
            print(f"Prompt Feedback: {response.prompt_feedback}")
            # Check candidates for more info, especially safety ratings if blocked
            if response.candidates:
                 candidate = response.candidates[0]
                 print(f"Candidate Finish Reason: {candidate.finish_reason.name if candidate.finish_reason else 'N/A'}")
                 print(f"Candidate Safety Ratings: {candidate.safety_ratings}")
                 # Construct a more informative error message
                 reason = candidate.finish_reason.name if candidate.finish_reason else "Unknown Reason"
                 if reason == 'SAFETY':
                      error_msg = f"Response blocked due to safety filters ({reason})."
                 elif reason == 'STOP': # This is normal completion, but text failed? Odd.
                      error_msg = "Model stopped, but failed to get text."
                 else:
                      error_msg = f"Response generation stopped ({reason})."
            else:
                 # Check prompt feedback if no candidates
                 block_reason = response.prompt_feedback.block_reason.name if response.prompt_feedback.block_reason else "Unknown"
                 error_msg = f"Request blocked (Reason: {block_reason}). No candidates generated."

        except Exception as resp_err:
             print(f"ERROR: Failed processing Gemini response: {resp_err}")
             traceback.print_exc()
             error_msg = "Error processing model response."


        # --- Return Response to Frontend ---
        if error_msg:
             print(f"Returning error to frontend: {error_msg}")
             return jsonify({"error": error_msg}), 500
        else:
             print(f"Returning success reply to frontend (len={len(reply_text)} chars).")
             # Optionally log the reply snippet
             # print(f"Reply snippet: {reply_text[:100]}...")
             return jsonify({"reply": reply_text})

    except Exception as e:
        print(f"ERROR in /chat handler: {e}"); traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

    finally:
        # Ensure temp file is cleaned up if path exists (should have been cleaned earlier)
        if temp_file_path and os.path.exists(temp_file_path):
            try: os.remove(temp_file_path); print("Final cleanup check: Removed temp file.")
            except Exception as clean_err: print(f"WARN: Final cleanup failed: {clean_err}")
        print("-" * 20)


# --- Main Execution Guard ---
if __name__ == '__main__':
    if model is None:
         print("\nERROR: Cannot start Flask server - Gemini client failed to initialize (Check API Key).\n")
    else:
         print("\nStarting Flask development server...\n")
         # Use host='0.0.0.0' to make it accessible on your network
         # Use debug=True only for development, False for production
         app.run(host='0.0.0.0', port=5000, debug=True)
