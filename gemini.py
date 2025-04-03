# --- gemini.py (Corrected Indentation) ---

from flask import Flask, request, jsonify # jsonify is needed for the new root route
from flask_cors import CORS
import google.generativeai as genai
import os
from dotenv import load_dotenv
import re
import traceback # Import traceback for detailed error logging

# Load environment variables from .env file (primarily for local development)
load_dotenv()

app = Flask(__name__)
# Allow Cross-Origin requests - refine origins for production security
# For now, allowing all origins for simplicity during deployment debugging
CORS(app)

# Get API Key from Environment Variable (Set this in Render's Environment Variables)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    # This will stop the app from starting if the key isn't set in Render
    raise ValueError("FATAL ERROR: GOOGLE_API_KEY environment variable not set.")

# Configure the Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize the Gemini Model
# Consider making the model name an environment variable too
try:
    # Using a known stable model, adjust if needed
    model = genai.GenerativeModel('models/gemini-1.5-flash') # Switched to flash for potential speed/cost benefit
    print("Successfully initialized GenerativeModel.")
except Exception as e:
    print(f"FATAL ERROR: Error initializing GenerativeModel: {e}")
    # Raise the error to prevent the app from starting incorrectly
    raise e

def format_chatbot_response(text):
    """Formats the chatbot's text response with basic HTML tags."""
    try:
        # Simple line break replacement
        text = text.replace('\n', '<br>')

        # Basic bold formatting for **text**
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)

        # Basic handling for numbered or bulleted lists (simple approach)
        text = re.sub(r'^\s*[\*|-]\s+(.*)', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+(.*)', r'<li>\1</li>', text, flags=re.MULTILINE)

        # Wrap list items in <ul> or <ol> - This is a simplistic guess
        is_list = '<li>' in text
        if is_list:
            # Determine if it looks like an ordered list
            is_ordered = re.search(r'<li>.*\d+\.', text) # Check if list items contain digits followed by a dot
            list_items_content = ""
            # Extract content between <li> tags to reconstruct the list
            items = re.findall(r'<li>(.*?)</li>', text, re.DOTALL)
            for item in items:
                 # Remove any lingering <br> tags inside list items
                cleaned_item = item.strip().replace('<br>', ' ')
                if cleaned_item: # Add item only if it's not empty after cleaning
                    list_items_content += f'<li>{cleaned_item}</li>'

            if list_items_content: # Only wrap if we actually have list items
                if is_ordered:
                    text = f'<ol>{list_items_content}</ol>'
                else:
                    text = f'<ul>{list_items_content}</ul>'
            else:
                is_list = False # Treat as non-list if no valid items found


        # Wrap the whole response in a paragraph tag ONLY if it wasn't identified as a list
        if not is_list:
            text = f'<p>{text}</p>'
            # Clean up <br> at the very start/end of paragraphs
            text = text.replace('<p><br>', '<p>').replace('<br></p>', '</p>')


        # Final cleanup for stray <br> tags that might remain
        text = text.replace('<br><br>', '<br>') # Replace double breaks with single

        return text

    except Exception as e:
        print(f"ERROR during formatting: {e}")
        # Return the original text if formatting fails
        return f"<p><i>Error formatting response.</i><br>{text.replace('<','<').replace('>','>')}</p>"


# --- Root Route for Health Checks and Basic Info ---
@app.route('/')
def home():
    """Provides a simple response for the root URL."""
    print("Root path '/' accessed.") # Log access for debugging
    return jsonify({
        "status": "OK",
        "message": "Adabot Gemini API is running successfully."
        }), 200

# --- Chat Route ---
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

        # Check if 'message' key exists and is a non-empty string
        user_message = data.get('message') # Use .get() for safer access
        if not user_message or not isinstance(user_message, str) or not user_message.strip():
             print("Error: 'message' key missing, not a string, or empty")
             return jsonify({"error": "'message' must be a non-empty string"}), 400 # Bad Request

        print(f"Generating content for message starting with: '{user_message[:50]}...'")
        # Generate content using the Gemini model
        response = model.generate_content(user_message)
        print("Received response from Gemini API.")

        # Check if response has text (might be blocked or empty)
        if not hasattr(response, 'text') or not response.text:
             print("Warning: Gemini response was empty or missing text.")
             # Check for blocking reason if possible
             try:
                  blocking_reason = response.prompt_feedback.block_reason.name
                  print(f"Prompt Blocked: {blocking_reason}")
                  return jsonify({"response": f"<i>Request blocked due to: {blocking_reason}</i>"}), 200 # Return info, not an error
             except Exception:
                  # Handle cases where feedback might not be available as expected
                  return jsonify({"response": "<i>Received an empty response from AI.</i>"}), 200


        # Format the response text with HTML
        formatted_response = format_chatbot_response(response.text)
        # print(f"Formatted response: {formatted_response}") # Log formatted response (can be long)

        # Return the formatted response as JSON
        return jsonify({"response": formatted_response})

    # Handle specific Gemini exceptions if needed (like BlockedPromptException)
    except genai.types.generation_types.BlockedPromptException as bpe:
        print(f"Blocked Prompt Error: {bpe}")
        # It's often better to inform the user rather than return a server error
        return jsonify({"response": f"<i>Your request was blocked due to safety concerns ({bpe}). Please rephrase.</i>"}), 200 # OK, but with info
    except Exception as e:
        # Log the full error for server-side debugging
        print(f"ERROR in /chat endpoint: {type(e).__name__} - {e}")
        traceback.print_exc() # Print the full traceback to the logs
        # Return a generic error message to the client
        return jsonify({"error": "An internal server error occurred while processing your request."}), 500 # Internal Server Error

# --- Local Development Runner ---
# This block is ONLY executed when you run the script directly (python gemini.py)
# It is IGNORED by Gunicorn on Render.
if __name__ == '__main__':
    print("Starting Flask development server (for local testing only)...")
    # host='0.0.0.0' allows connections from other devices on your network
    # debug=True enables auto-reloading and detailed errors (disable in production)
    # Use port 5000 or another available port
    app.run(host='0.0.0.0', port=5000, debug=True)