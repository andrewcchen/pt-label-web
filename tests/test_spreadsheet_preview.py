import base64
from io import BytesIO

import pytest
import zxingcpp
from flask import Flask
from PIL import Image

from app.labeldesigner import bp, routes


@pytest.mark.parametrize('repository', [False, True])
def test_preview_every_row_with_own_templates_and_length(monkeypatch, repository):
    app = Flask(__name__)
    app.register_blueprint(bp)
    data = {
        'spreadsheet_mode': 1,
        'spreadsheet_data': '[["first"],["a much longer value for the second row"]]',
        'label_size': 'tze24', 'label_length_auto': 1, 'label_length': 50,
        'print_type': 'qrcode', 'code_text': '{{1}}-{{counter}}',
        'qrcode_size': 2, 'code_fit': 0, 'border_thickness': 0,
    }
    client = app.test_client()
    if repository:
        monkeypatch.setattr(routes, '_load_repo_json', lambda name: data)
        response = client.get('/api/repository/preview?name=test')
    else:
        response = client.post('/api/preview', data=data)
    assert response.status_code == 200
    previews = [Image.open(BytesIO(base64.b64decode(image))) for image in response.json['images']]
    assert len(previews) == 2
    assert [zxingcpp.read_barcode(image).text.removeprefix('\ufeff') for image in previews] == ['first-1', 'a much longer value for the second row-2']
    assert previews[1].width > previews[0].width
    assert response.json['warnings'] == []
    assert response.json['font_sizes'] == []
    assert response.json['code_cell_size'] == 2

    data.update(label_length_auto=0, label_length=(previews[0].width + 28) * 25.4 / 180)
    cropped = client.post('/api/preview', data=data)
    assert cropped.status_code == 200
    assert cropped.json['warnings'] == ['Row 2: Content was cropped to fit the fixed label length.']
    assert len(cropped.json['images']) == 2


def test_image_upload_can_be_previewed_for_every_row():
    app = Flask(__name__)
    app.register_blueprint(bp)
    image = BytesIO()
    Image.new('RGB', (20, 20), 'black').save(image, format='PNG')
    image.seek(0)
    response = app.test_client().post('/api/preview', data={
        'label_size': 'tze24',
        'spreadsheet_mode': 1, 'spreadsheet_data': '[["a"],["b"]]',
        'print_type': 'image', 'image': (image, 'test.png'),
    })
    assert response.status_code == 200
    assert len(response.json['images']) == 2
    assert response.json['images'][0] == response.json['images'][1]
