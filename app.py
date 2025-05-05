import os
import google.generativeai as genai
from google.generativeai import types
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS # Import CORS
import werkzeug # To get filename securely
import time # For unique filenames

# --- Configuration ---
# Load API key from environment variable (set this in PythonAnywhere)
GEMINI_API_KEY = "AIzaSyBSlU9iv1ZISIcQy6WHUOL3v076-u2sLOo"
UPLOAD_FOLDER = 'uploads' # Create this folder in your PythonAnywhere file storage
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Flask App Setup ---
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app) # Enable CORS for all routes, allowing your frontend origin

# --- Gemini Client Initialization ---
# Check if API key is available
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable not set.")
    # Optionally, raise an exception or handle this case appropriately
    # For now, the client init will fail later if key is missing

try:
    genai.configure(api_key=GEMINI_API_KEY)
    # Initialize the Gemini client (using the configured API key)
    # model = genai.GenerativeModel('gemini-1.5-flash-latest') # Or use the pro model if needed
    model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17') # Using pro as it's often better with vision
except Exception as e:
    print(f"ERROR: Failed to configure or initialize Gemini client: {e}")
    model = None # Indicate that the model is not available

# --- Routes ---

@app.route('/')
def index():
    # Serve the main HTML file
    # Ensure index.html is in the root or a 'templates' folder
    # For simplicity here, assuming it's served by another means (like GitHub Pages)
    # If hosting frontend and backend together, you'd use:
    # return send_from_directory('.', 'index.html')
    # But since index.html is separate (GitHub Pages), this root isn't strictly needed for the API
    return "Backend is running. Use the /chat endpoint.", 200


@app.route('/chat', methods=['POST'])
def chat_handler():
    if model is None or not GEMINI_API_KEY:
         return jsonify({"error": "Backend Gemini client not configured. Check API Key."}), 500

    print("Received request on /chat") # Log entry

    # Get data from the form POST request
    text_prompt = request.form.get('prompt', '')
    uploaded_file = request.files.get('file')

    print(f"Prompt: '{text_prompt}'")
    print(f"File received: {'Yes' if uploaded_file else 'No'}")

    if not text_prompt and not uploaded_file:
        return jsonify({"error": "No prompt or file provided"}), 400

    # --- Prepare parts for Gemini ---
    gemini_parts = []
    uploaded_file_info = None
    temp_file_path = None # To keep track of the temporary file

    try:
        # --- Handle File Upload (if provided) ---
        if uploaded_file:
            if uploaded_file.filename == '':
                 return jsonify({"error": "Received file object but filename is empty"}), 400

            # Secure filename and create a unique path
            filename = werkzeug.utils.secure_filename(uploaded_file.filename)
            unique_filename = f"{int(time.time())}_{filename}"
            temp_file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            try:
                uploaded_file.save(temp_file_path)
                print(f"File saved temporarily to: {temp_file_path}")

                # Upload to Gemini using the SDK
                print("Uploading file to Gemini...")
                # Timeout can be adjusted if needed
                file_upload_response = genai.upload_file(path=temp_file_path)
                uploaded_file_info = file_upload_response # Keep the response object
                print(f"Gemini file upload successful. URI: {uploaded_file_info.uri}")

                # Add file part for the generate_content call
                gemini_parts.append(types.Part.from_uri(
                    file_uri=uploaded_file_info.uri,
                    mime_type=uploaded_file_info.mime_type, # Use mime_type from upload response
                ))

            except Exception as upload_err:
                 print(f"ERROR: Gemini file upload failed: {upload_err}")
                 # Consider deleting the temporary file even on error
                 if temp_file_path and os.path.exists(temp_file_path):
                     os.remove(temp_file_path)
                 return jsonify({"error": f"Failed to upload file to Gemini: {upload_err}"}), 500

        # --- Handle Text Prompt (if provided) ---
        if text_prompt:
            gemini_parts.append(types.Part.from_text(text=text_prompt))

        if not gemini_parts:
             # Should not happen if checks above are correct, but as a safeguard
             return jsonify({"error": "Cannot generate content with no parts"}), 400

        # --- Call Gemini API ---
        print(f"Calling Gemini generate_content with {len(gemini_parts)} parts...")
        # Simple generation, not using history from the example for now
        # To use history, you'd need to pass the conversation history from the frontend
        # and construct the 'contents' list accordingly.
        contents_for_gemini = [types.Content(role="user", parts=gemini_parts)]

        # Set safety settings (adjust as needed) - BLOCK_NONE is generally not recommended for production
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        ]

        generation_config = types.GenerateContentConfig(
            # temperature=0.7, # Adjust generation parameters if desired
            # top_p=0.9,
            # top_k=40,
            response_mime_type="text/plain", # Request plain text response
        )

        response = model.generate_content(
            contents=contents_for_gemini,
            generation_config=generation_config,
            safety_settings=safety_settings
            )

        print("Gemini response received.")

        # --- Process Response ---
        # Handle potential blocks or empty responses
        if not response.candidates:
             print("WARNING: Gemini response missing candidates. Prompt Feedback:", response.prompt_feedback)
             error_msg = "No response generated."
             if response.prompt_feedback and response.prompt_feedback.block_reason:
                 error_msg = f"Blocked: {response.prompt_feedback.block_reason.name}"
             return jsonify({"error": error_msg}), 500

        # Assuming the first candidate is the one we want
        candidate = response.candidates[0]

        if not candidate.content or not candidate.content.parts:
            print("WARNING: Gemini candidate missing content/parts. Finish Reason:", candidate.finish_reason)
            error_msg = f"No text generated. Reason: {candidate.finish_reason.name}"
            # You might want to check safety ratings here too
            # if candidate.safety_ratings: ...
            return jsonify({"error": error_msg}), 500

        # Extract text from the parts
        reply_text = "".join(part.text for part in candidate.content.parts if hasattr(part, 'text'))

        print(f"Generated Reply: '{reply_text[:100]}...'") # Log snippet

        # --- Return Success Response ---
        return jsonify({"reply": reply_text})

    except Exception as e:
        print(f"ERROR: An unexpected error occurred in /chat: {e}")
        import traceback
        traceback.print_exc() # Print full traceback to server logs
        return jsonify({"error": f"An internal server error occurred: {e}"}), 500

    finally:
         # --- Clean up temporary file ---
         if temp_file_path and os.path.exists(temp_file_path):
             try:
                 os.remove(temp_file_path)
                 print(f"Temporary file cleaned up: {temp_file_path}")
             except Exception as clean_err:
                 print(f"ERROR: Failed to clean up temporary file {temp_file_path}: {clean_err}")
         # --- Optionally delete the file from Gemini ---
         # Requires keeping uploaded_file_info
         # if uploaded_file_info:
         #     try:
         #         print(f"Attempting to delete Gemini file: {uploaded_file_info.name}")
         #         genai.delete_file(name=uploaded_file_info.name) # Use name (e.g., files/abc-123)
         #     except Exception as del_err:
         #         print(f"ERROR: Failed to delete Gemini file {uploaded_file_info.name}: {del_err}")


# --- Main Execution ---
if __name__ == '__main__':
    # This is used for local development testing
    # On PythonAnywhere, Gunicorn/uWSGI runs the app
    # Consider using python-dotenv locally:
    # from dotenv import load_dotenv
    # load_dotenv()
    # if not os.environ.get("GEMINI_API_KEY"):
    #     print("Please set the GEMINI_API_KEY environment variable (e.g., in a .env file)")
    # else:
    app.run(debug=True, port=5000) # Runs on http://localhost:5000