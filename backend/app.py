import os
import configparser
import uuid
import logging
import traceback
import urllib.parse
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import boto3
from werkzeug.utils import secure_filename

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Read configuration
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', 'config.ini'))

app = Flask(__name__, static_folder='../frontend/build')
CORS(app)  # Enable CORS for all routes

# Configure AWS credentials from config file
aws_access_key_id = config.get('AWS', 'aws_access_key_id').strip()
aws_secret_access_key = config.get('AWS', 'aws_secret_access_key').strip()
region_name = config.get('AWS', 'region_name').strip()

# Log credential information (don't include secrets in production)
logger.debug(f"AWS Region: {region_name}")
logger.debug(f"Access Key ID length: {len(aws_access_key_id)}")

# Polly configuration
output_format = config.get('POLLY', 'output_format')
voice_id_english = config.get('POLLY', 'voice_id_english')
voice_id_chinese = config.get('POLLY', 'voice_id_chinese')

# App configuration
upload_folder = config.get('APP', 'upload_folder')
output_folder = config.get('APP', 'output_folder')
allowed_extensions = config.get('APP', 'allowed_extensions').split(',')
max_text_length = int(config.get('APP', 'max_text_length'))

# Create directories if they don't exist
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(output_folder, exist_ok=True)

# Initialize Polly client with better error handling
try:
    # Initialize Polly client
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name
    )
    polly_client = session.client('polly')
    logger.info("AWS Polly client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing AWS Polly client: {str(e)}")
    logger.error(traceback.format_exc())
    # Continue execution - we'll handle errors in the endpoints

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/api/voices', methods=['GET'])
def get_voices(): 
    """Get list of available voices from Amazon Polly"""
    try:
        logger.info("Fetching voices from Amazon Polly")
        response = polly_client.describe_voices()
        voices = [
            {
                'id': voice['Id'],
                'name': voice['Name'],
                'language': voice['LanguageCode'],
                'gender': voice['Gender']
            }
            for voice in response['Voices']
        ]
        logger.info(f"Successfully retrieved {len(voices)} voices")
        return jsonify({'voices': voices})
    except Exception as e:
        logger.error(f"Error retrieving voices: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'error': str(e),
            'message': 'Failed to retrieve voices. Check AWS credentials.',
            'traceback': traceback.format_exc()
        }), 500

# Rest of the application code remains the same
@app.route('/api/synthesize', methods=['POST'])
def synthesize_speech():
    """Convert text to speech using Amazon Polly"""
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
            
        text = data['text']
        voice_id = data.get('voiceId', voice_id_english)
        language_code = data.get('languageCode', 'en-US')
        
        if len(text) > max_text_length:
            return jsonify({'error': f'Text exceeds maximum length of {max_text_length} characters'}), 400
        
        # Generate a unique filename
        filename = f"{uuid.uuid4()}.{output_format}"
        output_path = os.path.join(output_folder, filename)
        
        # Call Amazon Polly to synthesize speech
        response = polly_client.synthesize_speech(
            Text=text,
            VoiceId=voice_id,
            LanguageCode=language_code,
            OutputFormat=output_format
        )
        
        # Save the audio to a file
        if "AudioStream" in response:
            with open(output_path, 'wb') as file:
                file.write(response['AudioStream'].read())
                
        return jsonify({
            'success': True,
            'filename': filename,
            'url': f'/api/audio/{filename}'
        })
        
    except Exception as e:
        logger.error(f"Error synthesizing speech: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """Serve the generated audio file"""
    return send_from_directory(os.path.abspath(output_folder), filename)
    
@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a text file and convert it to speech"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Read text from the file
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            
        # Get other parameters from form data
        voice_id = request.form.get('voiceId', voice_id_english)
        language_code = request.form.get('languageCode', 'en-US')
        
        # Generate a unique filename for the audio
        audio_filename = f"{uuid.uuid4()}.{output_format}"
        output_path = os.path.join(output_folder, audio_filename)
        
        # Call Amazon Polly to synthesize speech
        try:
            response = polly_client.synthesize_speech(
                Text=text,
                VoiceId=voice_id,
                LanguageCode=language_code,
                OutputFormat=output_format
            )
            
            # Save the audio to a file
            if "AudioStream" in response:
                with open(output_path, 'wb') as file:
                    file.write(response['AudioStream'].read())
                    
            return jsonify({
                'success': True,
                'filename': audio_filename,
                'url': f'/api/audio/{audio_filename}'
            })
        except Exception as e:
            logger.error(f"Error converting file to speech: {str(e)}")
            logger.error(traceback.format_exc())
            return jsonify({'error': str(e)}), 500
            
    return jsonify({'error': 'File type not allowed'}), 400

# Serve React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# Handle 404 for missing static files (like favicon, etc.)
@app.errorhandler(404)
def not_found(e):
    # If requesting a common static file like favicon.ico, just return empty response
    common_static_files = ['favicon.ico', 'logo192.png', 'logo512.png']
    path = request.path.lstrip('/')
    if path in common_static_files:
        return '', 204
    return jsonify(error=str(e)), 404

if __name__ == '__main__':
    host = config.get('FLASK', 'host')
    port = config.getint('FLASK', 'port')
    debug = config.getboolean('FLASK', 'debug')
    app.run(host=host, port=port, debug=debug)