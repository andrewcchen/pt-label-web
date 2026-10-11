import pytest
import zxingcpp

from app.labeldesigner.label import LabelContent, LabelOrientation, SimpleLabel
from app.labeldesigner.printer import render_label_bitmap


@pytest.mark.parametrize('value', ['1234567890', 'Hello\nWorld', 'café 日本語', 'x' * 500])
@pytest.mark.parametrize('orientation', [LabelOrientation.STANDARD, LabelOrientation.ROTATED])
def test_datamatrix_round_trip(value, orientation):
    label = SimpleLabel(
        width=200,
        height=200,
        text=[{'text': 'ignored'}],
        label_content=LabelContent.QRCODE_ONLY,
        label_orientation=orientation,
        barcode_type='DATAMATRIX',
        code_text=value,
        code_fit=True,
    )

    result = zxingcpp.read_barcode(render_label_bitmap(label))

    assert result is not None
    assert result.format == zxingcpp.BarcodeFormat.DataMatrix
    assert result.text == value


def test_datamatrix_uses_all_text_lines_without_override():
    label = SimpleLabel(
        height=200,
        text=[{'text': 'first'}, {'text': 'second'}],
        label_content=LabelContent.QRCODE_ONLY,
        barcode_type='DATAMATRIX',
    )

    result = zxingcpp.read_barcode(render_label_bitmap(label))

    assert result is not None
    assert result.text == 'first\nsecond'
