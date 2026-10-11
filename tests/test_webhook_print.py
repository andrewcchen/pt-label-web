from io import BytesIO

import pytest
from flask import Flask
from PIL import Image

from app.labeldesigner import bp, routes
from config import Config


@pytest.mark.parametrize('orientation', ['standard', 'rotated'])
@pytest.mark.parametrize('high_res', [0, 1])
@pytest.mark.parametrize('narrow', [False, True])
def test_webhook_fits_images_in_renderer(monkeypatch, orientation, high_res, narrow):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['WEBHOOK_PASSWORD'] = 'test'
    app.register_blueprint(bp)
    rendered = []

    class Queue:
        def __init__(self, **kwargs):
            pass

        def add_label_to_queue(self, label, **kwargs):
            rendered.append(label.generate())

        def process_queue(self):
            return ''

    monkeypatch.setattr(routes, 'PrinterQueue', Queue)
    size = (1, 1000) if narrow else (80, 60)
    if orientation == 'rotated':
        size = size[::-1]
    image = BytesIO()
    Image.new('RGB', size, 'black').save(image, format='PNG')
    image.seek(0)
    response = app.test_client().post('/api/webhook/print', data={
        'label_size': 'tze12', 'orientation': orientation, 'high_res': high_res,
        'images': (image, 'test.png'),
    }, headers={'Authorization': 'Bearer test'})
    assert response.status_code == 200
    assert response.json == {'success': True, 'count': 1}
    assert len(rendered) == 1
    fixed_axis = 1 if orientation == 'standard' else 0
    assert rendered[0].size[fixed_axis] == 70 * (2 if high_res else 1)
    assert rendered[0].size[1 - fixed_axis] >= 1


def test_webhook_unknown_label_size():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['WEBHOOK_PASSWORD'] = 'test'
    app.register_blueprint(bp)
    response = app.test_client().post('/api/webhook/print', data={
        'label_size': 'unknown',
    }, headers={'Authorization': 'Bearer test'})
    assert response.status_code == 400
    assert response.json == {'success': False, 'message': 'Unknown label_size: unknown'}
