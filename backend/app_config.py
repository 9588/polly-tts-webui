from flask import Flask
import logging

def configure_app(app: Flask):
    """Configure Flask application with debugging settings"""
    # Set up logging
    app.logger.setLevel(logging.DEBUG)
    
    # Set up debug settings
    app.config['DEBUG'] = True
    app.config['PROPAGATE_EXCEPTIONS'] = True
    
    # Enable JSON pretty printing
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    return app
