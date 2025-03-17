from flask import jsonify, current_app
import traceback

// ...existing code...

@app.route('/api/voices', methods=['GET'])
def get_voices():
    try:
        # Your existing code to get voices
        voices = polly_client.describe_voices()
        # Return the voices list
        return jsonify(voices)
    except Exception as e:
        # Print full traceback to console
        traceback.print_exc()
        current_app.logger.error(f"Error retrieving voices: {str(e)}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500
