import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Container, Row, Col, Form, Button, Alert, Spinner } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';

function App() {
  const [text, setText] = useState('');
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [file, setFile] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');

  // Fetch list of voices from Amazon Polly when component loads
  useEffect(() => {
    const fetchVoices = async () => {
      try {
        const response = await axios.get('/api/voices');
        setVoices(response.data.voices);
        
        // Set a default voice (you can choose based on your preference)
        const defaultVoice = response.data.voices.find(voice => voice.id === 'Joanna') || response.data.voices[0];
        if (defaultVoice) {
          setSelectedVoice(defaultVoice.id);
        }
      } catch (err) {
        console.error('Error fetching voices:', err);
        setError('Failed to load available voices. Please try again later.');
      }
    };

    fetchVoices();
  }, []);

  // Group voices by language
  const voicesByLanguage = voices.reduce((acc, voice) => {
    const langCode = voice.language;
    if (!acc[langCode]) {
      acc[langCode] = [];
    }
    acc[langCode].push(voice);
    return acc;
  }, {});

  const handleTextChange = (e) => {
    setText(e.target.value);
  };

  const handleVoiceChange = (e) => {
    setSelectedVoice(e.target.value);
  };

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    
    if (!text.trim()) {
      setError('Please enter some text to convert to speech.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccessMessage('');
    setAudioUrl(null);

    try {
      const selectedVoiceObj = voices.find(voice => voice.id === selectedVoice);
      
      const response = await axios.post('/api/synthesize', {
        text: text,
        voiceId: selectedVoice,
        languageCode: selectedVoiceObj ? selectedVoiceObj.language : 'en-US'
      });

      setSuccessMessage('Audio generated successfully!');
      setAudioUrl(response.data.url);
    } catch (err) {
      console.error('Error generating speech:', err);
      setError(err.response?.data?.error || 'Failed to generate speech. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSubmit = async (e) => {
    e.preventDefault();

    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccessMessage('');
    setAudioUrl(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('voiceId', selectedVoice);
      
      const selectedVoiceObj = voices.find(voice => voice.id === selectedVoice);
      if (selectedVoiceObj) {
        formData.append('languageCode', selectedVoiceObj.language);
      }

      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      setSuccessMessage('Audio generated successfully from file!');
      setAudioUrl(response.data.url);
    } catch (err) {
      console.error('Error generating speech from file:', err);
      setError(err.response?.data?.error || 'Failed to generate speech from file. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container className="my-5">
      <Row className="mb-4">
        <Col>
          <h1 className="text-center">Amazon Polly TTS</h1>
          <h4 className="text-center text-muted">Text-to-Speech Web Application</h4>
        </Col>
      </Row>

      {error && (
        <Row className="mb-3">
          <Col>
            <Alert variant="danger">{error}</Alert>
          </Col>
        </Row>
      )}

      {successMessage && (
        <Row className="mb-3">
          <Col>
            <Alert variant="success">{successMessage}</Alert>
          </Col>
        </Row>
      )}

      <Row className="mb-4">
        <Col md={6} className="mb-3 mb-md-0">
          <Form onSubmit={handleTextSubmit}>
            <h4>Convert Text to Speech</h4>
            <Form.Group className="mb-3">
              <Form.Label>Enter Text</Form.Label>
              <Form.Control
                as="textarea"
                rows={5}
                value={text}
                onChange={handleTextChange}
                placeholder="Enter the text you want to convert to speech..."
              />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Select Voice</Form.Label>
              <Form.Select value={selectedVoice} onChange={handleVoiceChange}>
                {Object.entries(voicesByLanguage).map(([langCode, voiceList]) => (
                  <optgroup key={langCode} label={`${langCode}`}>
                    {voiceList.map(voice => (
                      <option key={voice.id} value={voice.id}>
                        {voice.name} ({voice.gender})
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Form.Select>
            </Form.Group>

            <Button variant="primary" type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
                  <span className="ms-2">Converting...</span>
                </>
              ) : (
                'Convert to Speech'
              )}
            </Button>
          </Form>
        </Col>

        <Col md={6}>
          <Form onSubmit={handleFileSubmit}>
            <h4>Upload Text File</h4>
            <Form.Group className="mb-3">
              <Form.Label>Select Text File</Form.Label>
              <Form.Control
                type="file"
                onChange={handleFileChange}
                accept=".txt"
              />
              <Form.Text className="text-muted">
                Only .txt files are supported.
              </Form.Text>
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Select Voice</Form.Label>
              <Form.Select value={selectedVoice} onChange={handleVoiceChange}>
                {Object.entries(voicesByLanguage).map(([langCode, voiceList]) => (
                  <optgroup key={langCode} label={`${langCode}`}>
                    {voiceList.map(voice => (
                      <option key={voice.id} value={voice.id}>
                        {voice.name} ({voice.gender})
                      </option>
                    ))}
                  </optgroup>
                ))}
              </Form.Select>
            </Form.Group>

            <Button variant="secondary" type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" />
                  <span className="ms-2">Converting...</span>
                </>
              ) : (
                'Convert File to Speech'
              )}
            </Button>
          </Form>
        </Col>
      </Row>

      {audioUrl && (
        <Row className="mt-4">
          <Col>
            <h4>Generated Audio</h4>
            <div className="p-3 border rounded">
              <audio controls className="w-100" src={audioUrl}>
                Your browser does not support the audio element.
              </audio>
              <div className="mt-2">
                <Button variant="outline-primary" href={audioUrl} download>
                  Download Audio
                </Button>
              </div>
            </div>
          </Col>
        </Row>
      )}
    </Container>
  );
}

export default App;