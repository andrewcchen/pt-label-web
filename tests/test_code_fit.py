import pytest
import zxingcpp

from app.labeldesigner.label import LabelContent, LabelOrientation, SimpleLabel
from app.labeldesigner.printer import render_label_bitmap


@pytest.mark.parametrize('barcode_type', ['QR', 'DATAMATRIX', 'CODE128'])
@pytest.mark.parametrize('code_fit', [False, True])
@pytest.mark.parametrize('label_content', [LabelContent.QRCODE_ONLY, LabelContent.TEXT_QRCODE])
def test_codes_ignore_image_settings(barcode_type, code_fit, label_content):
    label = SimpleLabel(
        height=400,
        label_content=label_content,
        barcode_type=barcode_type,
        text=[],
        code_text='hello',
        code_fit=code_fit,
    )
    expected = label.generate()
    actual = SimpleLabel(
        height=400,
        label_content=label_content,
        barcode_type=barcode_type,
        text=[],
        code_text='hello',
        code_fit=code_fit,
        image_fit=True,
        image_crop=True,
        image_rotation=361,
        image_scaling_factor=0,
    ).generate()
    assert actual.size == expected.size
    assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize('settings', [{'image_scaling_factor': 0}, {'image_rotation': 361}])
def test_image_settings_are_still_validated_for_images(settings):
    with pytest.raises(ValueError):
        SimpleLabel(label_content=LabelContent.IMAGE_BW, **settings)


@pytest.mark.parametrize('barcode_type', ['QR', 'DATAMATRIX'])
@pytest.mark.parametrize('orientation', [LabelOrientation.STANDARD, LabelOrientation.ROTATED])
def test_code_fit_preserves_cells_and_decodes(barcode_type, orientation):
    label = SimpleLabel(
        width=137,
        height=137,
        label_content=LabelContent.QRCODE_ONLY,
        label_orientation=orientation,
        label_margin=(8, 8, 8, 8),
        barcode_type=barcode_type,
        text=[],
        code_text='hello',
        code_fit=True,
    )
    bitmap = render_label_bitmap(label)
    result = zxingcpp.read_barcode(bitmap)
    assert result is not None
    assert result.text.removeprefix('\ufeff') == 'hello'
    bbox = bitmap.point(lambda value: 255 - value).getbbox()
    fixed_size = bbox[2] - bbox[0] if orientation == LabelOrientation.ROTATED else bbox[3] - bbox[1]
    code = label._generate_qr() if barcode_type == 'QR' else label._generate_datamatrix()
    cells = code.width // label._qr_size
    assert label.rendered_code_cell_size == 121 // cells
    assert fixed_size == cells * (121 // cells)


def test_code_fit_rejects_code_too_dense_for_label():
    label = SimpleLabel(text=[], height=10, label_content=LabelContent.QRCODE_ONLY, code_text='hello', code_fit=True)
    with pytest.raises(ValueError, match='too dense'):
        label.generate()


@pytest.mark.parametrize('orientation', [LabelOrientation.STANDARD, LabelOrientation.ROTATED])
@pytest.mark.parametrize('size', [52, 76, 128])
def test_linear_barcode_fit_preserves_bar_widths_and_decodes(orientation, size):
    label = SimpleLabel(
        width=size,
        height=size,
        text=[],
        label_content=LabelContent.QRCODE_ONLY,
        label_orientation=orientation,
        label_margin=(8, 8, 8, 8),
        barcode_type='CODE128',
        code_text='1234567890',
        code_fit=True,
    )
    original = label._generate_barcode()
    bitmap = render_label_bitmap(label)
    length = bitmap.height if orientation == LabelOrientation.ROTATED else bitmap.width
    assert length == original.width + 16
    result = zxingcpp.read_barcode(bitmap)
    assert result is not None
    assert result.text == '1234567890'


def test_linear_barcode_has_no_caption():
    label = SimpleLabel(text=[], barcode_type='CODE128', code_text='1234567890')
    image = label._generate_barcode().convert('L')
    bounds = image.point(lambda value: 255 - value).getbbox()
    bars = image.crop(bounds)
    row = bars.crop((0, 0, bars.width, 1)).tobytes()
    assert bars.tobytes() == row * bars.height
