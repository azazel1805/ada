# --- gemini.py ---

import os
import re
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file (especially for local testing)
load_dotenv()

# Initialize Flask App
# Flask will automatically look for HTML files in a 'templates' folder
app = Flask(__name__)

# Enable CORS (Cross-Origin Resource Sharing) for all routes
# Allows your frontend (even if testing locally) to call the API
CORS(app)

# --- Configuration ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Validate API Key ---
if not GOOGLE_API_KEY:
    # Critical error if the key is missing - App shouldn't start.
    # Make sure this is set in Render's Environment Variables!
    raise ValueError("FATAL ERROR: GOOGLE_API_KEY environment variable not set.")

# --- Initialize Gemini ---
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    # Using gemini-1.5-flash as a default, change if needed
    model = genai.GenerativeModel('models/gemini-1.5-flash')
    print("Successfully initialized GenerativeModel.")
except Exception as e:
    print(f"FATAL ERROR: Could not initialize GenerativeModel: {e}")
    # Stop the app if model fails to initialize
    raise e

# --- Simple HTML Formatting Helper ---
def format_response_html(text):
    """Basic formatting for the response."""
    try:
        # Replace newlines with <br>
        text = text.replace('\n', '<br>')
        # Make **text** bold
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        # Minimal handling for bullet points (add more rules if needed)
        text = re.sub(r'^\s*[\*|-]\s+(.*)', r'<li>\1</li>', text, flags=re.MULTILINE)
        if '<li>' in text:
            text = f'<ul>{text}</ul>'.replace('<br></li>','</li>').replace('</li><br>','</li>')

        # Wrap in paragraph if no list was made
        if not text.strip().startswith('<ul>'):
           text = f'<p>{text}</p>'

        return text
    except Exception as e:
        print(f"Error during text formatting: {e}")
        # Return original text safely escaped if formatting fails
        return f"<p>{text.replace('<','<').replace('>','>')}</p>"

# --- Routes ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    print("Root route '/' accessed. Serving index.html.")
    try:
        # Assumes 'index.html' is in the 'templates' folder
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering template 'index.html': {e}")
        return "Error loading page.", 500

@app.route('/chat', methods=['POST'])
def chat():
    """Handles POST requests to the /chat API endpoint."""
    print("'/chat' endpoint accessed.")
    try:
        # Check if request is JSON
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 415

        data = request.get_json()
        user_message = data.get('message')

        # Validate input
        if not user_message or not isinstance(user_message, str) or not user_message.strip():
            return jsonify({"error": "'message' must be a non-empty string"}), 400

        print(f"Received message: '{user_message[:100]}...'") # Log safely

        # Call Gemini API
        response = model.generate_content(user_message)
        print("Gemini response received.")

        # Check for empty or blocked response before accessing .text
        if not hasattr(response, 'text') or not response.text:
            try: # Try to get blocking reason
                reason = response.prompt_feedback.block_reason.name
                print(f"Response blocked: {reason}")
                return jsonify({"response": f"<i>Blocked: {reason}</i>"})
            except Exception: # Fallback if no reason available
                print("Response was empty or missing text attribute.")
                return jsonify({"response": "<i>Received empty response from AI.</i>"})

        # Format and return response
        formatted_html = format_response_html(response.text)
        return jsonify({"response": formatted_html})

    # Handle specific known exceptions if desired
    except Exception as e:
        print(f"ERROR processing /chat request: {type(e).__name__} - {e}")
        traceback.print_exc() # Print full traceback to server logs
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Run Flask App (for local testing, ignored by Gunicorn) ---
if __name__ == '__main__':
    print("Starting Flask development server...")
    # host='0.0.0.0' makes it accessible on your network
    # debug=True enables auto-reload and better error pages locally
    app.run(host='0.0.0.0', port=5000, debug=True)