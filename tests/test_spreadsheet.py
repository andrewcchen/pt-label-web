import json
from types import SimpleNamespace

import pytest
from flask import Flask

from app import utils
from app.labeldesigner import bp, routes
from config import Config
from app.labeldesigner.label import SimpleLabel


def test_spreadsheet_columns_in_text_and_code():
    label = SimpleLabel(
        text=[{'text': '{{2}} / {{1}} / {{3}} / {{counter}}'}],
        code_text='{{1}}-{{2}}',
        spreadsheet_row=['{{counter}}', 'second'],
        counter=4,
    )
    for _ in range(2):
        label.process_templates()
        assert label.text[0]['text'] == 'second / {{counter}} /  / 5'
        assert label._code_text == '{{counter}}-second'


def test_spreadsheet_columns_stay_literal_when_disabled():
    label = SimpleLabel(text=[{'text': '{{1}}'}], code_text='{{2}}')
    label.process_templates()
    assert label.text[0]['text'] == '{{1}}'
    assert label._code_text == '{{2}}'


@pytest.mark.parametrize('rows', [[], ['cell'], [[]], [[123]]])
def test_invalid_spreadsheet(rows):
    with pytest.raises(ValueError):
        routes.spreadsheet_rows({'spreadsheet_mode': 1, 'spreadsheet_data': json.dumps(rows)})


def test_prints_each_row_and_ignores_print_count(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(bp)
    labels = []

    class Queue:
        def add_label_to_queue(self, label, cut, *args, **kwargs):
            label.process_templates()
            labels.append((label.text[0]['text'], label._code_text, cut))

        def process_queue(self):
            return ''

    monkeypatch.setattr(routes, 'create_printer_from_request', lambda request: Queue())
    monkeypatch.setattr(routes, 'FONTS', SimpleNamespace(get_path=lambda font: 'unused.ttf'))
    response = app.test_client().post('/api/print', data={
        'spreadsheet_mode': 1,
        'spreadsheet_data': json.dumps([['first', 'A'], ['second', 'B']]),
        'text': json.dumps([{'text': '{{1}}-{{counter}}', 'size': 24}]),
        'code_text': '{{2}}',
        'print_count': 99,
        'cut_once': 1,
    })
    assert response.status_code == 200
    assert response.json['success']
    assert labels == [('first-1', 'A', False), ('second-2', 'B', True)]


@pytest.mark.parametrize('enabled', [False, True])
def test_repository_preserves_spreadsheet_settings(tmp_path, monkeypatch, enabled):
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(bp)
    monkeypatch.setattr(utils, 'FONTS', SimpleNamespace(get_default_font=lambda: ('Test', 'Regular')))
    monkeypatch.setattr(routes, '_get_repo_dir', lambda: str(tmp_path))
    client = app.test_client()
    rows = json.dumps([['first', 'A'], ['second', 'B']])
    response = client.post('/api/repository/save', json={
        'name': 'spreadsheet',
        'spreadsheet_mode': enabled,
        'spreadsheet_data': rows,
        'fontSettingsPerLine': '[]',
    })
    assert response.status_code == 200
    restored = client.get('/api/repository/load', query_string={'name': response.json['name']})
    assert restored.status_code == 200
    assert restored.json['spreadsheet_mode'] is enabled
    assert restored.json['spreadsheet_data'] == rows
