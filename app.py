import os
# Ensure google.generativeai is installed via requirements.txt
import google.generativeai as genai
# types is not needed for the simplified part creation
# from google.generativeai import types
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS # Import CORS
import werkzeug # To get filename securely
import time # For unique filenames
import traceback # For detailed error logging

# --- Configuration ---
# !! SECURITY WARNING: Hardcoding API keys is not recommended. Use environment variables in production. !!
GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo" # Your hardcoded key
UPLOAD_FOLDER = 'uploads' # Temporary storage folder within the container

# Create upload folder if it doesn't exist at runtime
if not os.path.exists(UPLOAD_FOLDER):
    try:
        os.makedirs(UPLOAD_FOLDER)
        print(f"Created upload folder: {UPLOAD_FOLDER}")
    except OSError as e:
        print(f"ERROR: Could not create upload folder {UPLOAD_FOLDER}: {e}")

# --- Flask App Setup ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- CORS Configuration ---
# Allow requests specifically to the /chat endpoint from ANY origin (*).
CORS(app, resources={r"/chat": {"origins": "*"}})
print("CORS configured for /chat with origins: *")

# --- Gemini Client Initialization ---
model = None # Initialize model to None
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY is missing in the code. Backend cannot function.")
else:
    try:
        print("Configuring Gemini client...")
        genai.configure(api_key=GEMINI_API_KEY)
        # Select your desired model (e.g., 1.5 Pro or 1.5 Flash)
        model_name = 'gemini-1.5-pro-latest' # Or 'gemini-1.5-flash-latest'
        model = genai.GenerativeModel(model_name)
        print(f"Gemini client initialized with model: {model_name}")
    except Exception as e:
        print(f"ERROR: Failed to configure or initialize Gemini client: {e}")
        traceback.print_exc() # Print full traceback for debugging

# --- Routes ---

@app.route('/')
def root():
    # Simple endpoint to check if the backend is running
    # Useful for verifying deployment without making a POST request
    print("Root route '/' accessed.")
    return jsonify({"status": "Backend is running", "gemini_configured": model is not None}), 200

@app.route('/chat', methods=['POST'])
def chat_handler():
    # Check if Gemini client is ready before processing
    if model is None:
         print("ERROR: /chat endpoint called but Gemini model is not available.")
         # Return a server error status code
         return jsonify({"error": "Backend Gemini client not configured. Check API Key/Server Logs."}), 500

    # Log request details
    print("-" * 20)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Received POST request on /chat from: {request.remote_addr}")

    # Get data from the form POST request (safer defaults)
    text_prompt = request.form.get('prompt', '')
    uploaded_file_obj = request.files.get('file')

    print(f"Form Data - Prompt: '{text_prompt}'")
    print(f"File Received: {'Yes, filename: ' + uploaded_file_obj.filename if uploaded_file_obj and uploaded_file_obj.filename else 'No'}")

    # Basic validation: ensure at least one input is present
    if not text_prompt and not uploaded_file_obj:
        print("ERROR: Request rejected - No prompt or file provided.")
        return jsonify({"error": "No prompt or file provided"}), 400 # Bad request

    # --- Prepare parts for Gemini ---
    gemini_parts = [] # List to hold text and file objects for the API call
    uploaded_gemini_file_info = None # Store Gemini file object reference
    temp_file_path = None # Store path of file saved temporarily on server

    try:
        # --- Handle File Upload (if provided) ---
        if uploaded_file_obj and uploaded_file_obj.filename:
            # Secure the filename provided by the user
            filename = werkzeug.utils.secure_filename(uploaded_file_obj.filename)
            # Create a unique filename to avoid collisions
            unique_filename = f"{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            try:
                # Save the file temporarily to the server's ephemeral filesystem
                print(f"Attempting to save uploaded file temporarily to: {temp_file_path}")
                uploaded_file_obj.save(temp_file_path)
                print(f"File saved successfully. Size: {os.path.getsize(temp_file_path)} bytes")

                # Upload the temporarily saved file to the Gemini API
                print("Uploading file to Gemini API...")
                uploaded_gemini_file_info = genai.upload_file(path=temp_file_path)
                print(f"Gemini file upload successful. URI: {uploaded_gemini_file_info.uri}, MIME Type: {uploaded_gemini_file_info.mime_type}")

                # Add the Gemini file object to the parts list
                gemini_parts.append(uploaded_gemini_file_info)

            except Exception as upload_err:
                 # Log detailed error during file processing/upload
                 print(f"ERROR: Gemini file upload or saving failed: {upload_err}")
                 traceback.print_exc()
                 # Attempt cleanup before returning error
                 if temp_file_path and os.path.exists(temp_file_path):
                     try: os.remove(temp_file_path)
                     except Exception: pass # Ignore cleanup error if main error occurred
                 return jsonify({"error": f"Failed processing uploaded file: {upload_err}"}), 500 # Internal server error

        # --- Handle Text Prompt (if provided) ---
        if text_prompt:
            # Add the text prompt directly to the parts list
            gemini_parts.append(text_prompt)

        # Final check if parts list is somehow empty (shouldn't happen with prior checks)
        if not gemini_parts:
             print("ERROR: Cannot generate content with no parts (logic error?).")
             return jsonify({"error": "Internal error: No content parts generated"}), 500

        # --- Call Gemini API ---
        print(f"Calling Gemini generate_content with {len(gemini_parts)} parts...")

        # Configuration for the generation call
        safety_settings=[
            # Adjust thresholds as needed (BLOCK_MEDIUM_AND_ABOVE is generally recommended)
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        ]
        generation_config = types.GenerateContentConfig(
            response_mime_type="text/plain", # Ensure text response
        )

        # Make the API call using the initialized model
        response = model.generate_content(
            contents=gemini_parts, # Pass the list of parts directly
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        print("Gemini generate_content response received.")

        # --- Process Response ---
        reply_text = ""
        error_msg = None

        try:
            # Check if the response contains candidates
            if response.candidates:
                 candidate = response.candidates[0] # Get the first candidate
                 # Check if the candidate has content and parts
                 if candidate.content and candidate.content.parts:
                     # Join text from all parts in the response
                     reply_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))
                     print(f"Successfully extracted reply text (len={len(reply_text)}).")
                 else:
                     # Handle cases where content/parts are missing (e.g., blocked)
                     finish_reason_name = candidate.finish_reason.name if candidate.finish_reason else 'UNKNOWN'
                     print(f"WARNING: Gemini candidate missing content/parts. Finish Reason: {finish_reason_name}")
                     error_msg = f"No response content generated. Reason: {finish_reason_name}"
                     if finish_reason_name == 'SAFETY' and candidate.safety_ratings:
                          print("Safety Ratings:", candidate.safety_ratings)
                          error_msg += " (Blocked due to safety settings)"
            else:
                 # Handle cases where the entire 'candidates' list is missing (e.g., prompt blocked)
                 print("WARNING: Gemini response missing candidates.")
                 error_msg = "No response generated from model."
                 if response.prompt_feedback and response.prompt_feedback.block_reason:
                      block_reason_name = response.prompt_feedback.block_reason.name
                      print(f"Prompt blocked. Reason: {block_reason_name}")
                      error_msg = f"Request blocked: {block_reason_name}"
                      if response.prompt_feedback.safety_ratings:
                           print("Prompt Feedback Safety:", response.prompt_feedback.safety_ratings)

        except AttributeError as attr_err:
            # Catch potential errors accessing attributes on the response object
            print(f"ERROR: Attribute error parsing Gemini response: {attr_err}")
            traceback.print_exc()
            error_msg = "Error parsing the structure of the model's response."
        except Exception as resp_err:
             # Catch any other errors during response processing
             print(f"ERROR: Failed to process Gemini response: {resp_err}")
             traceback.print_exc()
             error_msg = "Error processing the model's response."

        # --- Return Response to Frontend ---
        if error_msg:
             print(f"Returning error to frontend: {error_msg}")
             return jsonify({"error": error_msg}), 500 # Use 500 for server/API side issues
        else:
             print(f"Returning success reply to frontend (len={len(reply_text)}).")
             return jsonify({"reply": reply_text})

    except Exception as e:
        # Catch-all for any unexpected errors during the request handling logic
        print(f"ERROR: An unexpected error occurred in /chat handler: {e}")
        traceback.print_exc()
        # Return a generic server error to the frontend
        return jsonify({"error": "An internal server error occurred on the backend."}), 500

    finally:
        # --- Clean up temporary file ---
        # This block executes whether the try block succeeded or failed
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"Temporary file cleaned up: {temp_file_path}")
            except Exception as clean_err:
                # Log cleanup error but don't prevent response
                print(f"WARNING: Failed to clean up temporary file {temp_file_path}: {clean_err}")

        # --- Optional: Delete the file from Gemini ---
        # Uncomment if you want files deleted from Google's storage after use
        # if uploaded_gemini_file_info:
        #     try:
        #         print(f"Attempting to delete Gemini file: {uploaded_gemini_file_info.name}")
        #         genai.delete_file(name=uploaded_gemini_file_info.name)
        #         print(f"Successfully deleted Gemini file: {uploaded_gemini_file_info.name}")
        #     except Exception as del_err:
        #         print(f"ERROR: Failed to delete Gemini file {uploaded_gemini_file_info.name}: {del_err}")

        # This print statement MUST be indented correctly under finally:
        print("-" * 20) # End log for this request

# --- Main Execution Guard ---
# This section is ignored by Gunicorn/PythonAnywhere but useful for local testing
if __name__ == '__main__':
    # (Optional) Load .env file for local development
    # try:
    #     from dotenv import load_dotenv
    #     load_dotenv()
    #     print("Loaded environment variables from .env file (if present).")
    #     # Re-check API key if potentially loaded from .env
    #     if not GEMINI_API_KEY: GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    #     # Re-initialize client if needed
    # except ImportError:
    #     print("dotenv not installed, skipping .env load.")

    if model is None:
         print("Cannot start Flask server locally: Gemini client failed to initialize (Check API Key).")
    else:
         print("Starting Flask development server locally on http://localhost:5000 ...")
         # debug=True enables auto-reload and verbose error pages during local dev
         app.run(host='0.0.0.0', port=5000, debug=True)
