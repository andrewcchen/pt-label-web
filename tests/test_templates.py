import uuid

import pytest
import zxingcpp

from app.labeldesigner.label import LabelContent, SimpleLabel
from app.labeldesigner.printer import render_label_bitmap


@pytest.mark.parametrize('barcode_type', ['QR', 'DATAMATRIX'])
def test_code_content_expands_templates(barcode_type):
    label = SimpleLabel(
        width=600,
        height=200,
        text=[{'text': 'ignored'}],
        label_content=LabelContent.QRCODE_ONLY,
        barcode_type=barcode_type,
        code_text='item-{{counter:10}}-{{datetime:%Y}}',
        counter=2,
        timestamp=1704067200,
        image_fit=True,
    )

    for counter in (2, 3):
        label._counter = counter
        result = zxingcpp.read_barcode(render_label_bitmap(label))
        assert result is not None
        assert result.text.removeprefix('\ufeff') == f'item-{counter + 10}-2024'


def test_code_content_random_templates():
    label = SimpleLabel(text=[], code_text='{{uuid}}|{{short-uuid}}|{{random:12}}')
    label.process_templates()
    full, short, random_text = label._code_text.split('|', 2)
    uuid.UUID(full)
    assert len(short) == 8
    assert len(random_text) == 12


def test_env_templates_stay_literal(monkeypatch):
    monkeypatch.setenv('LABEL_TEMPLATE_TEST', 'secret')
    template = '{{env:LABEL_TEMPLATE_TEST}}'
    label = SimpleLabel(text=[{'text': template}], code_text=template)
    label.process_templates()
    assert label.text[0]['text'] == template
    assert label._code_text == template


def test_barcode_content_expands_templates():
    label = SimpleLabel(text=[], barcode_type='CODE128', code_text='item-{{counter}}', counter=2)
    label.process_templates()
    result = zxingcpp.read_barcode(label._generate_barcode())
    assert result is not None
    assert result.text == 'item-3'
