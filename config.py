"""
This are the default settings. (DONT CHANGE THIS FILE)
Adjust your settings in 'instance/application.py'
"""

import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _from_env(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    if isinstance(default, bool):
        return value.lower() in ('1', 'true', 'yes', 'on')
    return type(default)(value)


class Config():
    DEBUG = False
    LOG_LEVEL = 'WARNING'

    SERVER_PORT = 8013
    SERVER_HOST = '0.0.0.0'

    PRINTER_MODEL = 'PT-P750W'
    PRINTER_PRINTER = '?'
    LABEL_DEFAULT_ORIENTATION = 'standard'
    LABEL_DEFAULT_SIZE = 'tze12'
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
    WEBHOOK_PASSWORD = ''


for _name, _default in vars(Config).items():
    if _name.isupper():
        setattr(Config, _name, _from_env(_name, _default))
