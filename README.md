# PollyTTS - Amazon Polly Text-to-Speech Web Application

This is a web application that uses Amazon's Polly service to convert text to speech. It features a React frontend and a Flask backend.

## Features

- Convert text to speech using Amazon Polly
- Support for multiple languages and voices
- Upload and convert text files
- Download generated audio files
- Simple and intuitive user interface

## Prerequisites

- Python 3.8 or higher
- Node.js 14.0 or higher
- npm 6.0 or higher
- AWS account with access to Amazon Polly

## Setup

### 1. Configure AWS Credentials

Edit the `config/config.ini` file and add your AWS credentials:

```ini
[AWS]
aws_access_key_id = YOUR_ACCESS_KEY_ID
aws_secret_access_key = YOUR_SECRET_ACCESS_KEY
region_name = us-east-1
```

### 2. Set up the Backend

```bash
cd backend
pip install -r requirements.txt
```

### 3. Set up the Frontend

```bash
cd frontend
npm install
```

## Running the Application

### 1. Start the Backend Server

```bash
cd backend
python app.py
```

The Flask server will run at http://localhost:5000

### 2. Start the Frontend Development Server

```bash
cd frontend
npm start
```

The React development server will run at http://localhost:3000

### 3. Build for Production

To create an optimized production build of the frontend:

```bash
cd frontend
npm run build
```

After building, you can serve the frontend directly from the Flask application by accessing http://localhost:5000

## Usage

1. Open the web application in your browser
2. Enter text directly or upload a text file
3. Select a voice and language
4. Click "Convert to Speech" to generate audio
5. Play the audio in the browser or download it

## Customization

You can modify the `config/config.ini` file to change various settings:

- Default voices and languages
- Audio output format
- Maximum text length
- Server ports and settings

## Troubleshooting

- If you encounter AWS credential errors, ensure that your access key and secret key are correctly set in the config.ini file
- If the Polly API returns errors, check your AWS account has the necessary permissions for Amazon Polly
- For React rendering issues, clear your browser cache or try a different browser

## License

This project is licensed under the MIT License - see the LICENSE file for details.