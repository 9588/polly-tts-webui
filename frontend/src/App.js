import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Container, Row, Col, Form, Button, Alert, Spinner, ListGroup, Card, OverlayTrigger, Tooltip } from 'react-bootstrap';
import 'bootstrap/dist/css/bootstrap.min.css';

function App() {
  const [text, setText] = useState('');
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState('');
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [files, setFiles] = useState([]);
  const [successMessage, setSuccessMessage] = useState('');
  const [audioResults, setAudioResults] = useState([]);
  const textareaRef = useRef(null);
  const [serverUrl] = useState(
    window.location.hostname === 'localhost' ? 'http://localhost:5000' : window.location.origin
  );

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
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
  };

  const handleInsertSeparator = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const cursorPosition = textarea.selectionStart;
    const textBeforeCursor = text.substring(0, cursorPosition);
    const textAfterCursor = text.substring(cursorPosition);
    
    // Add a newline before the separator if not at beginning of line
    const prefix = cursorPosition > 0 && text[cursorPosition - 1] !== '\n' ? '\n' : '';
    
    // Insert separator template
    const separator = `${prefix}---------- [put your output file name here]\n`;
    const newText = textBeforeCursor + separator + textAfterCursor;
    setText(newText);
    
    // Focus back on textarea and place cursor after the inserted separator
    setTimeout(() => {
      textarea.focus();
      const placeholderStart = cursorPosition + prefix.length + 11; // "---------- ".length
      const placeholderEnd = placeholderStart + 32; // "[put your output file name here]".length
      textarea.setSelectionRange(placeholderStart, placeholderEnd);
    }, 0);
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
    setAudioResults([]);

    try {
      const selectedVoiceObj = voices.find(voice => voice.id === selectedVoice);
      
      const response = await axios.post('/api/synthesize', {
        text: text,
        voiceId: selectedVoice,
        languageCode: selectedVoiceObj ? selectedVoiceObj.language : 'en-US'
      });

      if (response.data.multipart && response.data.results) {
        setSuccessMessage(`Successfully converted ${response.data.results.length} sections to speech!`);
        setAudioResults(response.data.results.map(result => ({
          originalFilename: result.name,
          audioFilename: result.filename,
          url: result.url,
          downloadUrl: result.downloadUrl
        })));
      } else {
        setSuccessMessage('Audio generated successfully!');
        setAudioUrl(response.data.url);
        // Store download URL if available
        if (response.data.downloadUrl) {
          setAudioResults([{
            originalFilename: 'Audio',
            audioFilename: response.data.filename,
            url: response.data.url,
            downloadUrl: response.data.downloadUrl
          }]);
        }
      }

      // Display any errors that occurred during processing
      if (response.data.errors && response.data.errors.length > 0) {
        const errorMessages = response.data.errors.map(err => `${err.name}: ${err.error}`).join('\n');
        setError(`Some sections could not be processed:\n${errorMessages}`);
      }
    } catch (err) {
      console.error('Error generating speech:', err);
      setError(err.response?.data?.error || 'Failed to generate speech. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSubmit = async (e) => {
    e.preventDefault();

    if (!files.length) {
      setError('Please select at least one file to upload.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccessMessage('');
    setAudioUrl(null);
    setAudioResults([]);

    try {
      const formData = new FormData();
      
      // Append all selected files
      files.forEach(file => {
        formData.append('file', file);  // Using 'file' as the key for compatibility with existing backend
      });
      
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

      let totalAudioCount = 0;
      const processedResults = [];

      if (response.data.results && response.data.results.length > 0) {
        response.data.results.forEach(result => {
          if (result.hasParts && result.parts) {
            // Handle multi-part file
            result.parts.forEach(part => {
              processedResults.push({
                originalFilename: `${result.originalFilename} - ${part.partName}`,
                audioFilename: part.audioFilename,
                url: part.url,
                downloadUrl: part.downloadUrl
              });
            });
            totalAudioCount += result.parts.length;
          } else {
            // Handle single file
            processedResults.push({
              originalFilename: result.originalFilename,
              audioFilename: result.audioFilename,
              url: result.url,
              downloadUrl: result.downloadUrl
            });
            totalAudioCount += 1;
          }
        });

        setSuccessMessage(`Successfully converted ${totalAudioCount} audio files!`);
        setAudioResults(processedResults);
      } else {
        setSuccessMessage('Audio generated successfully!');
      }

      // If there's only one result, also set the audioUrl for compatibility with the single player
      if (processedResults.length === 1) {
        setAudioUrl(processedResults[0].url);
      }

      // Display any errors that occurred during processing
      if (response.data.errors && response.data.errors.length > 0) {
        const errorMessages = response.data.errors.map(err => 
          `${err.filename}${err.partName ? ' - ' + err.partName : ''}: ${err.error}`
        ).join('\n');
        setError(`Some files could not be processed:\n${errorMessages}`);
      }
    } catch (err) {
      console.error('Error generating speech from files:', err);
      setError(err.response?.data?.error || 'Failed to generate speech from files. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Helper function to ensure download URLs have the proper extension
  const formatDownloadUrl = (url) => {
    if (!url) return '';
    
    // If URL already has a file extension, return as is
    if (url.match(/\.(mp3|wav|ogg)$/i)) {
      return url;
    }
    
    // Add .mp3 extension for download URLs
    return `${url}`;
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
            <Alert variant="danger" style={{ whiteSpace: 'pre-line' }}>{error}</Alert>
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
              <div className="mb-2">
                <OverlayTrigger
                  placement="top"
                  overlay={<Tooltip>Insert separator for multiple outputs. Format: "---------- [output filename]"</Tooltip>}
                >
                  <Button 
                    variant="outline-secondary" 
                    size="sm"
                    onClick={handleInsertSeparator}
                  >
                    Insert Section Separator
                  </Button>
                </OverlayTrigger>
                <span className="text-muted ms-2 small">
                  Use separator to create multiple audio files
                </span>
              </div>
              <Form.Control
                as="textarea"
                rows={5}
                value={text}
                onChange={handleTextChange}
                placeholder="Enter the text you want to convert to speech..."
                ref={textareaRef}
              />
              <Form.Text className="text-muted">
                Use "---------- section_name" to split your text into multiple audio files.
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
            <h4>Upload Text Files</h4>
            <Form.Group className="mb-3">
              <Form.Label>Select Text Files</Form.Label>
              <Form.Control
                type="file"
                onChange={handleFileChange}
                accept=".txt"
                multiple
              />
              <Form.Text className="text-muted">
                Multiple .txt files are supported. Each file will be converted to a separate audio file.
                Files can also contain separators ("---------- section_name") to create multiple outputs per file.
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
                'Convert Files to Speech'
              )}
            </Button>
          </Form>
        </Col>
      </Row>

      {audioUrl && !audioResults.length && (
        <Row className="mt-4">
          <Col>
            <h4>Generated Audio</h4>
            <div className="p-3 border rounded">
              <audio controls className="w-100" src={audioUrl}>
                Your browser does not support the audio element.
              </audio>
              <div className="mt-2">
                <Button 
                  variant="outline-primary" 
                  href={
                    serverUrl + formatDownloadUrl(
                      audioUrl.replace('/api/audio/', '/api/download/')
                    )
                  }
                  download
                >
                  Download Audio
                </Button>
              </div>
            </div>
          </Col>
        </Row>
      )}

      {audioResults.length > 0 && (
        <Row className="mt-4">
          <Col>
            <h4>Generated Audio Files</h4>
            <ListGroup>
              {audioResults.map((result, index) => (
                <ListGroup.Item key={index} className="p-3">
                  <Card>
                    <Card.Body>
                      <Card.Title>{result.originalFilename}</Card.Title>
                      <audio controls className="w-100 mt-2 mb-2" src={result.url}>
                        Your browser does not support the audio element.
                      </audio>
                      <Button 
                        variant="outline-primary" 
                        href={serverUrl + formatDownloadUrl(result.downloadUrl || result.url.replace('/api/audio/', '/api/download/'))}
                        download={result.audioFilename || "audio.mp3"}
                      >
                        Download Audio
                      </Button>
                    </Card.Body>
                  </Card>
                </ListGroup.Item>
              ))}
            </ListGroup>
          </Col>
        </Row>
      )}
    </Container>
  );
}

export default App;