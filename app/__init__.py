#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This is a web service to print labels on Brother P-touch printers.
"""

import sys
import logging

from flask import Flask

from . import fonts
from config import Config

FONTS = None


def create_app(config_class=Config) -> Flask:
    global FONTS
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_pyfile('application.py', silent=True)

    app.logger.setLevel(app.config.get('LOG_LEVEL', 'INFO'))
    logging.getLogger(__name__).setLevel(app.config.get('LOG_LEVEL', 'INFO'))

    FONTS = init_fonts(app)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.labeldesigner import bp as labeldesigner_bp
    app.register_blueprint(labeldesigner_bp, url_prefix='/labeldesigner')

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    return app


def init_fonts(app: Flask):
    FONTS = fonts.Fonts(app.logger,
                        app.config.get('LABEL_DEFAULT_FONT_FAMILY'),
                        app.config.get('LABEL_DEFAULT_FONT_STYLE'),
                        app.config.get('FONT_FOLDER'))
    if not FONTS.fonts_available():
        app.logger.error("No fonts found on your system. Please install some.")
        sys.exit(2)

    return FONTS
