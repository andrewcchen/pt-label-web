import json

import pytest
from flask import Flask

from app.labeldesigner.routes import _label_options_from_request, _generate_preview
from app.labeldesigner.printer import PrinterQueue
from app.labeldesigner.label import SimpleLabel
from app.labeldesigner import bp
from config import Config


@pytest.mark.parametrize('label_size', [None, ''])
@pytest.mark.parametrize('endpoint', ['/api/preview', '/api/print', '/api/repository/preview', '/api/repository/print', '/api/webhook/print'])
def test_label_size_is_required(endpoint, label_size, tmp_path):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(LABEL_DEFAULT_SIZE='tze12', LABEL_REPOSITORY_DIR=str(tmp_path), WEBHOOK_PASSWORD='test')
    app.register_blueprint(bp)
    data = {} if label_size is None else {'label_size': label_size}
    if '/repository/' in endpoint:
        (tmp_path / 'saved.json').write_text(json.dumps(data))
        data = {'name': 'saved.json'}
    response = app.test_client().post(endpoint, data=data, headers={'Authorization': 'Bearer test'})
    assert response.status_code == 400
    assert response.json['message'] == 'label_size is required'


@pytest.mark.parametrize('orientation', ['standard', 'rotated'])
@pytest.mark.parametrize('high_res', [0, 1])
def test_fixed_length_includes_feed_and_content_margins(orientation, high_res):
    label = SimpleLabel(**_label_options_from_request({
        'label_size': 'tze12', 'label_length': '50',
        'orientation': orientation, 'high_res': high_res,
        'margin_left': 20, 'margin_right': 30,
        'margin_top': 10, 'margin_bottom': 15,
    }))
    preview = _generate_preview(label)
    scale = 2 if high_res else 1
    assert preview.size == (round(50 * 180 * scale / 25.4) - 28 * scale, 70 * scale)
    queue = PrinterQueue('PT-P750W', 'simulation', 'tze12')
    queue.add_label_to_queue(label, high_res=bool(high_res))
    raster = queue._rasterize_entries(queue._print_queue)
    info = raster.data.index(b'\x1b\x69\x7a')
    assert int.from_bytes(raster.data[info + 7:info + 11], 'little') == preview.width


@pytest.mark.parametrize('length', ['-1', 'nan', 'inf', '3'])
def test_invalid_label_length(length):
    with pytest.raises(ValueError):
        _label_options_from_request({'label_size': 'tze24', 'label_length': length})


def test_fixed_length_crops_content_and_warns():
    label = SimpleLabel(**_label_options_from_request({'label_size': 'tze24', 'label_length': 5}))
    preview = _generate_preview(label)
    assert preview.width == round(5 * 180 / 25.4) - 28
    assert label.render_warning == 'Content was cropped to fit the fixed label length.'
    queue = PrinterQueue('PT-P750W', 'simulation', 'tze24')
    queue.add_label_to_queue(label)
    queue._rasterize_entries(queue._print_queue)
    assert queue.warnings == [label.render_warning]


@pytest.mark.parametrize('length_options', [
    {'label_length': 0},
    {'label_length': 50, 'label_length_auto': 1},
])
def test_automatic_length_keeps_content_margins(length_options):
    label = SimpleLabel(**_label_options_from_request({'label_size': 'tze12', **length_options}))
    assert _generate_preview(label).size == (40, 70)


def test_crop_warning_in_preview_and_spreadsheet_print():
    app = Flask(__name__)
    app.register_blueprint(bp)
    data = {
        'label_size': 'tze24', 'label_length': 5, 'printer': 'simulation', 'model': 'PT-P750W',
        'spreadsheet_mode': 1, 'spreadsheet_data': '[["first"],["second"]]',
    }
    client = app.test_client()
    preview = client.post('/api/preview', data=data)
    assert preview.status_code == 200
    warning = 'Content was cropped to fit the fixed label length.'
    assert preview.json['warnings'] == [f'Row 1: {warning}', f'Row 2: {warning}']
    printed = client.post('/api/print', data=data)
    assert printed.status_code == 200
    assert printed.json['success']
    assert printed.json['warnings'] == [warning]


@pytest.mark.parametrize('repository', [False, True])
@pytest.mark.parametrize('label_size,tape_width', [('tze12', 12), ('tze3.5', 3.5), ('hse2-5.8', 5.8), ('hse3-5.2', 5.2)])
def test_preview_metadata_matches_render_settings(repository, label_size, tape_width, tmp_path):
    app = Flask(__name__)
    app.register_blueprint(bp)
    data = {'label_size': label_size, 'high_res': 1}
    if repository:
        app.config['LABEL_REPOSITORY_DIR'] = str(tmp_path)
        (tmp_path / 'saved.json').write_text(json.dumps(data))
        response = app.test_client().get('/api/repository/preview?name=saved.json')
    else:
        response = app.test_client().post('/api/preview', data=data)
    assert response.status_code == 200
    metadata = response.json
    assert metadata['font_sizes'] == []
    assert metadata['code_cell_size'] is None
    assert {key: metadata[key] for key in ('dpi', 'tape_width', 'feed_margin')} == {
        'dpi': 360, 'tape_width': tape_width, 'feed_margin': 14,
    }
