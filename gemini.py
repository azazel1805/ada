from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

genai.configure(api_key=GOOGLE_API_KEY)

model = genai.GenerativeModel('models/gemini-1.5-pro-latest') # Or select models/gemini-2.0

def format_chatbot_response(text):
    """Formats the chatbot's text response with HTML tags for better structure."""

    # Replace line breaks with <br> tags
    text = text.replace("\n", "<br>")

    # Handle lists more robustly
    def replace_list_items(match):
        items = match.group(1).split("<br>")
        list_items = "".join(f"<li>{item.strip()}</li>" for item in items if item.strip())
        return f"<ul>{list_items}</ul>"

    text = re.sub(r"((?:<li>.*<\/li><br>)+)", replace_list_items, text)

    # Enclose the text with <p> tags
    text = f"<p>{text}</p>"

    return text

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({"error": "Missing 'message' in request body"}), 400

        user_message = data['message']

        response = model.generate_content(user_message)

        # Format the chatbot's response with HTML
        formatted_response = format_chatbot_response(response.text)

        return jsonify({"response": formatted_response})

    except Exception as e:
        print(f"Error processing chat request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)