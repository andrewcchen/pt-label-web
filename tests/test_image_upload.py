from io import BytesIO

import pytest
from flask import Flask
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.labeldesigner import routes


@pytest.mark.parametrize('image_mode,mode,pixel', [
    ('colored', 'RGB', (255, 0, 0)),
    ('grayscale', 'L', 76),
    ('bw', '1', 255),
])
def test_pdf_upload_honors_image_mode(monkeypatch, image_mode, mode, pixel):
    monkeypatch.setattr(routes, 'pdffile_to_image', lambda file, dpi: Image.new('RGB', (20, 20), 'red'))
    uploaded = FileStorage(stream=BytesIO(b'pdf'), filename='test.pdf')
    with Flask(__name__).app_context():
        options = routes._label_options_from_request({
            'label_size': 'tze24', 'print_type': 'image', 'image_mode': image_mode,
        }, {'image': uploaded})
    assert options['image'].mode == mode
    assert options['image'].getpixel((0, 0)) == pixel
