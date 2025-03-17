import os
import configparser
import uuid
import logging
import traceback
import re
import json
import urllib.parse
from flask import Flask, request, jsonify, send_from_directory, send_file
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

# File mapping database (mapping between stored files and download filenames)
file_mapping_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_mapping.json')

# Create directories if they don't exist
os.makedirs(upload_folder, exist_ok=True)
os.makedirs(output_folder, exist_ok=True)

# Initialize file mapping if it doesn't exist
if not os.path.exists(file_mapping_path):
    with open(file_mapping_path, 'w') as f:
        json.dump({}, f)

def get_file_mapping():
    """Read the file mapping from disk"""
    try:
        with open(file_mapping_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_file_mapping(mapping):
    """Save the file mapping to disk"""
    with open(file_mapping_path, 'w') as f:
        json.dump(mapping, f)

def add_file_mapping(stored_filename, display_filename):
    """Add a new entry to the file mapping"""
    mapping = get_file_mapping()
    mapping[stored_filename] = display_filename
    save_file_mapping(mapping)

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

# Function to split text by separator and extract file names
def split_text_by_separator(text):
    parts = []
    current_text = ""
    current_name = None
    
    # Split the text by newlines to process line by line
    lines = text.split('\n')
    
    for line in lines:
        # Check if this is a separator line
        if line.strip().startswith('----------'):
            # If we've already been collecting text, save it as a part
            if current_name is not None and current_text:
                parts.append({
                    'text': current_text.strip(),
                    'name': current_name
                })
                current_text = ""
            
            # Extract name from the separator line
            separator_match = re.match(r'^----------\s*(.*?)$', line.strip())
            if separator_match:
                name_part = separator_match.group(1).strip()
                current_name = name_part if name_part else f"part_{len(parts) + 1}"
            else:
                current_name = f"part_{len(parts) + 1}"
        else:
            # If we've encountered a separator, add to current text
            if current_name is not None:
                current_text += line + "\n"
            # If text appears before any separator, create a default part
            elif line.strip():
                current_name = "intro"
                current_text = line + "\n"
    
    # Don't forget to add the last part
    if current_name is not None and current_text:
        parts.append({
            'text': current_text.strip(),
            'name': current_name
        })
    
    # If no valid parts were found, just use the original text
    if not parts and text.strip():
        parts = [{
            'text': text.strip(),
            'name': 'complete_text'
        }]
    
    return parts

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

@app.route('/api/synthesize', methods=['POST'])
def synthesize_speech():
    """Convert text to speech using Amazon Polly"""
    try:
        logger.info("Received request to synthesize speech")
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
            
        text = data['text']
        voice_id = data.get('voiceId', voice_id_english)
        language_code = data.get('languageCode', 'en-US')
        
        # Check if the text has separators
        if '----------' in text: 
            text_parts = split_text_by_separator(text)
            logger.info(f"Splitting text into {len(text_parts)} parts")
            logger.debug(f"Text parts: {text_parts}")
            results = []
            errors = []
            
            for part in text_parts:
                try:
                    if len(part['text']) > max_text_length:
                        errors.append({
                            'name': part['name'],
                            'error': f"Text exceeds maximum length of {max_text_length} characters"
                        })
                        continue
                    
                    # Generate a unique internal filename
                    unique_id = str(uuid.uuid4())
                    internal_filename = f"{unique_id}.{output_format}"
                    output_path = os.path.join(output_folder, internal_filename)
                    
                    # Generate a clean display filename for download
                    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', part['name'])
                    display_filename = f"{clean_name}.{output_format}"
                    
                    # Call Amazon Polly to synthesize speech
                    polly_response = polly_client.synthesize_speech(
                        Text=part['text'],
                        VoiceId=voice_id,
                        LanguageCode=language_code,
                        OutputFormat=output_format
                    )
                    
                    # Save the audio to a file
                    if "AudioStream" in polly_response:
                        with open(output_path, 'wb') as file:
                            file.write(polly_response['AudioStream'].read())
                    
                    # Save mapping between internal and display filenames
                    add_file_mapping(internal_filename, display_filename)
                    
                    results.append({
                        'name': part['name'],
                        'filename': display_filename,
                        'url': f'/api/audio/{internal_filename}',
                        'downloadUrl': f'/api/download/{internal_filename}'
                    })
                except Exception as e:
                    logger.error(f"Error synthesizing part {part['name']}: {str(e)}")
                    errors.append({
                        'name': part['name'],
                        'error': str(e)
                    })
            
            return jsonify({
                'success': True,
                'results': results,
                'errors': errors,
                'multipart': True
            })
        else:
            # Original single text processing
            if len(text) > max_text_length:
                return jsonify({'error': f'Text exceeds maximum length of {max_text_length} characters'}), 400
            
            # Generate a unique internal filename
            unique_id = str(uuid.uuid4())
            internal_filename = f"{unique_id}.{output_format}"
            output_path = os.path.join(output_folder, internal_filename)
            
            # Generate a clean display filename for download
            display_filename = f"audio.{output_format}"
            
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
            
            # Save mapping between internal and display filenames
            add_file_mapping(internal_filename, display_filename)
                    
            return jsonify({
                'success': True,
                'filename': display_filename,
                'url': f'/api/audio/{internal_filename}',
                'downloadUrl': f'/api/download/{internal_filename}'
            })
        
    except Exception as e:
        logger.error(f"Error synthesizing speech: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/audio/<filename>', methods=['GET'])
def get_audio(filename):
    """Serve the generated audio file for playback (not download)"""
    return send_from_directory(os.path.abspath(output_folder), filename)

@app.route('/api/download/<path:filename>', methods=['GET'])
def download_audio(filename):
    """Download the audio file with the correct filename"""
    try:
        logger.info(f"Download request for file: {filename}")
        
        # Get the mapping to find the display filename
        mapping = get_file_mapping()
        
        # Remove any file extension for lookup purposes
        base_filename = filename.split('.')[0] if '.' in filename else filename
        
        # Look for the file with extension in the output directory
        stored_filename = None
        display_filename = None
        
        # First try exact match
        if filename in mapping:
            stored_filename = filename
            display_filename = mapping[filename]
        else:
            # Try to find a match based on the basename (without extension)
            for stored_name, display_name in mapping.items():
                stored_base = stored_name.split('.')[0] if '.' in stored_name else stored_name
                if stored_base == base_filename:
                    stored_filename = stored_name
                    display_filename = display_name
                    break
        
        if not stored_filename:
            # If we still don't have a match, check if the file exists with .mp3 extension
            if os.path.exists(os.path.join(output_folder, f"{base_filename}.{output_format}")):
                stored_filename = f"{base_filename}.{output_format}"
                display_filename = stored_filename  # Use the same name if no mapping found
        
        if not stored_filename:
            logger.error(f"No matching file found for: {filename}")
            return jsonify({'error': 'File not found'}), 404
        
        # Full path to the stored file
        file_path = os.path.join(os.path.abspath(output_folder), stored_filename)
        
        if not os.path.exists(file_path):
            logger.error(f"File path doesn't exist: {file_path}")
            return jsonify({'error': 'File not found'}), 404
        
        logger.info(f"Sending file {stored_filename} as {display_filename}")
        
        # Send the file with the display filename for download
        return send_file(
            file_path,
            mimetype=f'audio/{output_format}',
            as_attachment=True,
            download_name=display_filename
        )
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f"File not found or error downloading: {str(e)}"}), 404

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload a text file and convert it to speech"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    results = []
    errors = []
    
    voice_id = request.form.get('voiceId', voice_id_english)
    language_code = request.form.get('languageCode', 'en-US')
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Read text from the file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # Check if file contains separators
                if '----------' in text:
                    text_parts = split_text_by_separator(text)
                    file_results = []
                    
                    for part in text_parts:
                        try:
                            # Generate a unique internal filename
                            unique_id = str(uuid.uuid4())
                            internal_filename = f"{unique_id}.{output_format}"
                            output_path = os.path.join(output_folder, internal_filename)
                            
                            # Generate a clean display filename for download
                            base_name = os.path.splitext(filename)[0]
                            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', part['name'])
                            display_filename = f"{base_name}_{clean_name}.{output_format}"
                            
                            # Call Amazon Polly to synthesize speech
                            response = polly_client.synthesize_speech(
                                Text=part['text'],
                                VoiceId=voice_id,
                                LanguageCode=language_code,
                                OutputFormat=output_format
                            )
                            
                            # Save the audio to a file
                            if "AudioStream" in response:
                                with open(output_path, 'wb') as audio_file:
                                    audio_file.write(response['AudioStream'].read())
                                    
                            # Save mapping between internal and display filenames
                            add_file_mapping(internal_filename, display_filename)
                            
                            file_results.append({
                                'partName': part['name'],
                                'audioFilename': display_filename,
                                'url': f'/api/audio/{internal_filename}',
                                'downloadUrl': f'/api/download/{internal_filename}'
                            })
                        except Exception as e:
                            logger.error(f"Error converting part {part['name']} of file {filename} to speech: {str(e)}")
                            errors.append({
                                'filename': filename,
                                'partName': part['name'],
                                'error': str(e)
                            })
                    
                    if file_results:
                        results.append({
                            'originalFilename': filename,
                            'parts': file_results,
                            'hasParts': True
                        })
                else:
                    # Regular file processing (one file -> one audio)
                    # Generate a unique internal filename
                    unique_id = str(uuid.uuid4())
                    internal_filename = f"{unique_id}.{output_format}"
                    output_path = os.path.join(output_folder, internal_filename)
                    
                    # Generate a clean display filename for download
                    base_name = os.path.splitext(filename)[0]
                    display_filename = f"{base_name}.{output_format}"
                    
                    # Call Amazon Polly to synthesize speech
                    response = polly_client.synthesize_speech(
                        Text=text,
                        VoiceId=voice_id,
                        LanguageCode=language_code,
                        OutputFormat=output_format
                    )
                    
                    # Save the audio to a file
                    if "AudioStream" in response:
                        with open(output_path, 'wb') as audio_file:
                            audio_file.write(response['AudioStream'].read())
                    
                    # Save mapping between internal and display filenames
                    add_file_mapping(internal_filename, display_filename)
                            
                    results.append({
                        'originalFilename': filename,
                        'audioFilename': display_filename,
                        'url': f'/api/audio/{internal_filename}',
                        'downloadUrl': f'/api/download/{internal_filename}',
                        'hasParts': False
                    })
            except Exception as e:
                logger.error(f"Error converting file {filename} to speech: {str(e)}")
                logger.error(traceback.format_exc())
                errors.append({
                    'filename': filename,
                    'error': str(e)
                })
        else:
            errors.append({
                'filename': file.filename,
                'error': 'File type not allowed'
            })
    
    if not results and errors:
        return jsonify({'error': 'All files failed to process', 'details': errors}), 500
        
    return jsonify({
        'success': True,
        'results': results,
        'errors': errors
    })

@app.route('/api/upload-multiple', methods=['POST'])
def upload_multiple_files():
    """Upload multiple text files and convert them to speech"""
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files part'}), 400
    
    files = request.files.getlist('files[]')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected files'}), 400
    
    results = []
    errors = []
    
    voice_id = request.form.get('voiceId', voice_id_english)
    language_code = request.form.get('languageCode', 'en-US')
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            
            # Read text from the file
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                
                # Generate a unique internal filename
                unique_id = str(uuid.uuid4())
                internal_filename = f"{unique_id}.{output_format}"
                output_path = os.path.join(output_folder, internal_filename)
                
                # Generate a clean display filename for download
                base_name = os.path.splitext(filename)[0]
                display_filename = f"{base_name}.{output_format}"
                
                # Call Amazon Polly to synthesize speech
                response = polly_client.synthesize_speech(
                    Text=text,
                    VoiceId=voice_id,
                    LanguageCode=language_code,
                    OutputFormat=output_format
                )
                
                # Save the audio to a file
                if "AudioStream" in response:
                    with open(output_path, 'wb') as audio_file:
                        audio_file.write(response['AudioStream'].read())
                
                # Save mapping between internal and display filenames
                add_file_mapping(internal_filename, display_filename)
                        
                results.append({
                    'originalFilename': filename,
                    'audioFilename': display_filename,
                    'url': f'/api/audio/{internal_filename}',
                    'downloadUrl': f'/api/download/{internal_filename}'
                })
            except Exception as e:
                logger.error(f"Error converting file {filename} to speech: {str(e)}")
                logger.error(traceback.format_exc())
                errors.append({
                    'filename': filename,
                    'error': str(e)
                })
        else:
            errors.append({
                'filename': file.filename,
                'error': 'File type not allowed'
            })
    
    if not results and errors:
        return jsonify({'error': 'All files failed to process', 'details': errors}), 500
        
    return jsonify({
        'success': True,
        'results': results,
        'errors': errors
    })

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