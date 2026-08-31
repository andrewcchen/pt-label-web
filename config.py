"""
This are the default settings. (DONT CHANGE THIS FILE)
Adjust your settings in 'instance/application.py'
"""

import os
import logging

basedir = os.path.abspath(os.path.dirname(__file__))

class Config(object):
    DEBUG = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', logging.WARNING)

    SERVER_PORT = 8013
    SERVER_HOST = '0.0.0.0'

    PRINTER_MODEL = os.environ.get('PRINTER_MODEL', 'PT-P750W')
    PRINTER_PRINTER = os.environ.get('PRINTER_PRINTER', '?')

    LABEL_DEFAULT_ORIENTATION = os.environ.get('LABEL_DEFAULT_ORIENTATION', 'standard')
    LABEL_DEFAULT_SIZE = os.environ.get('LABEL_DEFAULT_SIZE', 'tze12')
    LABEL_DEFAULT_FONT_SIZE = 70
    LABEL_DEFAULT_QR_SIZE = 10
    LABEL_DEFAULT_LINE_SPACING = 100
    LABEL_DEFAULT_FONT_FAMILY = 'DejaVu Serif'
    LABEL_DEFAULT_FONT_STYLE = 'Book'

    IMAGE_DEFAULT_MODE = 'grayscale'
    IMAGE_DEFAULT_BW_THRESHOLD = 70

    LABEL_DEFAULT_MARGIN_TOP = 0
    LABEL_DEFAULT_MARGIN_BOTTOM = 0
    LABEL_DEFAULT_MARGIN_LEFT = 0
    LABEL_DEFAULT_MARGIN_RIGHT = 0

    LABEL_REPOSITORY_DIR = os.path.join(basedir, 'labels')

    FONT_FOLDER = ''

    # Webhook print endpoint password. The webhook is disabled when empty.
    # Generate a secure password with:
    #   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    WEBHOOK_PASSWORD = os.environ.get('WEBHOOK_PASSWORD', '')
