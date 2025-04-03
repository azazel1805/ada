# --- gemini.py (Modified with Root Route) ---

from flask import Flask, request, jsonify # jsonify is needed for the new root route
from flask_cors import CORS
import google.generativeai as genai
import os
from dotenv import load_dotenv
import re

# Load environment variables from .env file (primarily for local development)
load_dotenv()

app = Flask(__name__)
# Allow Cross-Origin requests - adjust origins for production if needed
CORS(app) # Allows all origins by default, refine for security later if needed

# Get API Key from Environment Variable (Set this in Render's Environment Variables)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    # This will stop the app from starting if the key isn't set in Render
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

# Configure the Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize the Gemini Model
# Consider making the model name an environment variable too if you might change it often
try:
    model = genai.GenerativeModel('models/gemini-1.5-pro-latest')
except Exception as e:
    print(f"Error initializing GenerativeModel: {e}")
    # Handle model initialization error appropriately, maybe raise it again
    # For now, we'll let it potentially crash if the model name is wrong or API key is invalid
    raise e

def format_chatbot_response(text):
    """Formats the chatbot's text response with basic HTML tags."""
    # Be cautious with replacing characters if the AI might intentionally use them
    # Simple line break replacement
    text = text.replace('\n', '<br>')

    # Basic bold formatting for **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

    # Basic handling for numbered or bulleted lists (simple approach)
    # This might need refinement based on actual Gemini output format
    text = re.sub(r'^\s*[\*|-]\s+(.*)', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+(.*)', r'<li>\1</li>', text, flags=re.MULTILINE)

    # Wrap list items in <ul> or <ol> - This is a simplistic guess
    if '<li>' in text:
         # If digits were used for numbering, assume ordered list
        if re.search(r'<li>.*\d+\.', text):
             text = f'<ol>{text}</ol>'
        else: # Otherwise, assume unordered list
             text = f'<ul>{text}</ul>'
         # Clean up extra <br> tags possibly left inside list wrappers
         text = text.replace('<br></li>', '</li>')
         text = text.replace('</li><br>', '</li>')


    # Wrap the whole response in a paragraph tag if it doesn't seem to be a list
    if not text.strip().startswith(('<ul', '<ol')):
        text = f'<p>{text}</p>'

    # Clean up potentially misplaced tags at the very start/end after wrapping
    text = text.replace('<p><br>', '<p>').replace('<br></p>', '</p>')
    text = text.replace('<ul><br>', '<ul>').replace('<br></ul>', '</ul>')
    text = text.replace('<ol><br>', '<ol>').replace('<br></ol>', '</ol>')


    return text

# --- NEW: Root Route for Health Checks and Basic Info ---
@app.route('/')
def home():
    """Provides a simple response for the root URL."""
    print("Root path '/' accessed.") # Log access for debugging
    return jsonify({
        "status": "OK",
        "message": "Adabot Gemini API is running successfully."
        }), 200

# --- Existing Chat Route ---
@app.route('/chat', methods=['POST'])
def chat():
    """Handles chat requests from the frontend."""
    print("'/chat' endpoint accessed.") # Log access
    try:
        # Ensure request body is JSON
        if not request.is_json:
            print("Error: Request content type is not application/json")
            return jsonify({"error": "Request must be JSON"}), 415 # Unsupported Media Type

        data = request.get_json()
        print(f"Received data: {data}") # Log received data

        # Check if 'message' key exists in the JSON data
        if not data or 'message' not in data:
            print("Error: Missing 'message' in request body")
            return jsonify({"error": "Missing 'message' in request body"}), 400 # Bad Request

        user_message = data['message']
        if not isinstance(user_message, str) or not user_message.strip():
             print("Error: 'message' must be a non-empty string")
             return jsonify({"error": "'message' must be a non-empty string"}), 400 # Bad Request

        print(f"Generating content for message: '{user_message}'")
        # Generate content using the Gemini model
        # Consider adding safety settings or other generation configurations if needed
        response = model.generate_content(user_message)
        print("Received response from Gemini API.")

        # Log the raw response text before formatting (for debugging)
        # print(f"Raw Gemini response: {response.text}") # Careful logging potentially sensitive data

        # Format the response text with HTML
        formatted_response = format_chatbot_response(response.text)
        print(f"Formatted response: {formatted_response}") # Log formatted response

        # Return the formatted response as JSON
        return jsonify({"response": formatted_response})

    except genai.types.generation_types.BlockedPromptException as bpe:
        print(f"Blocked Prompt Error: {bpe}")
        return jsonify({"error": "Request blocked due to safety concerns."}), 400 # Bad Request (from user input)
    except Exception as e:
        # Log the full error for server-side debugging
        # Use traceback for more details: import traceback; traceback.print_exc()
        print(f"ERROR in /chat endpoint: {type(e).__name__} - {e}")
        # Return a generic error message to the client
        return jsonify({"error": "An internal server error occurred."}), 500 # Internal Server Error

# --- Local Development Runner ---
# This block is ONLY executed when you run the script directly
# like `python gemini.py`. It's IGNORED by Gunicorn on Render.
if __name__ == '__main__':
    # Runs the Flask development server (not suitable for production)
    # Debug=True provides automatic reloading and detailed errors (disable in production)
    print("Starting Flask development server...")
    # Consider using host='0.0.0.0' if you need to access it from other devices on your local network
    app.run(debug=True, port=5000)