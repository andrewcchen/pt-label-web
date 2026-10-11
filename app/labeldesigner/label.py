from .enums import LabelContent, LabelOrientation
import uuid
from qrcode import QRCode, constants
from PIL import Image, ImageDraw, ImageFont, ImageChops
import logging
import barcode
import zxingcpp
from barcode.writer import ImageWriter
import datetime
import re
import random
import string
import copy
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Constants
WARNING_TEXT_LENGTH = 500
DEFAULT_RANDOM_LENGTH = 64
DEFAULT_FONT_SIZE = 12
FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


class SimpleLabel:
    """
    Represents a label with text, image, barcode, and QR code support.
    Handles rendering, template processing, and layout.
    """
    QR_CORRECTION_MAPPING = {
        'M': constants.ERROR_CORRECT_M,
        'L': constants.ERROR_CORRECT_L,
        'H': constants.ERROR_CORRECT_H,
        'Q': constants.ERROR_CORRECT_Q
    }

    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        label_content: LabelContent = LabelContent.TEXT_ONLY,
        label_orientation: LabelOrientation = LabelOrientation.STANDARD,
        barcode_type: str = "QR",
        label_margin: Tuple[int, int, int, int] = (0, 0, 0, 0),
        fore_color: Tuple[int, int, int] = (0, 0, 0),
        text: Optional[List[Dict[str, Any]]] = None,
        qr_size: int = 10,
        qr_correction: str = 'L',
        image_fit: bool = False,
        image_crop: bool = False,
        image_scaling_factor: float = 100.0,
        image_rotation: int = 0,
        image: Optional[Union[Image.Image, None]] = None,
        border_thickness: int = 0,
        border_roundness: int = 0,
        border_distance: Tuple[int, int] = (0, 0),
        border_color: Tuple[int, int, int] = (0, 0, 0),
        timestamp: int = 0,
        counter: int = 0,
        code_text: str = '',
        code_fit: bool = False,
        spreadsheet_row: list[str] | None = None,
        fixed_length: int = 0,
    ):
        """Initialize a SimpleLabel object."""
        # Input validation
        if width < 0 or height < 0:
            raise ValueError("Width and height must be non-negative.")
        if border_thickness < 0:
            raise ValueError("Border thickness must be non-negative.")
        if qr_size < 1:
            raise ValueError("QR size must be positive.")
        if label_content not in (LabelContent.QRCODE_ONLY, LabelContent.TEXT_QRCODE):
            if image_scaling_factor <= 0:
                raise ValueError("Image scaling factor must be > 0.")
            if image_rotation < 0 or image_rotation > 360:
                raise ValueError("Image rotation must be between 0 and 360 inclusive.")
        self._width = width
        self._height = height
        self._fixed_length = fixed_length
        self.render_warning = None
        self.label_content = label_content
        self.label_orientation = label_orientation
        self.barcode_type = barcode_type
        self._label_margin = label_margin
        self._fore_color = fore_color
        self.text = None
        self.input_text = text
        self._qr_size = qr_size
        self.qr_correction = qr_correction
        self._image = image
        self._image_fit = image_fit
        self._code_fit = code_fit
        self.rendered_code_cell_size = None
        self._image_crop = image_crop
        self._image_scaling_factor = image_scaling_factor
        self._image_rotation = image_rotation
        self._border_thickness = border_thickness
        self._border_roundness = border_roundness
        self._border_distance = border_distance
        self._border_color = border_color
        self._counter = counter
        self.spreadsheet_row = spreadsheet_row
        self._timestamp = timestamp
        self.input_code_text = code_text
        self._code_text = code_text

    @property
    def label_content(self):
        return self._label_content

    @label_content.setter
    def label_content(self, value):
        self._label_content = value

    def want_text(self, img: Optional[Image.Image]) -> bool:
        """Determine if text should be drawn on the label."""

        # If we are not drawing an image, we need to draw text or the label will
        # vanish
        if img is None:
            return True

        # If we want to draw only a code, suppress any text
        if self._label_content in (LabelContent.QRCODE_ONLY,):
            return False

        # If we are drawing an image, we want to draw text as well if there is
        # at least one line of text with non-empty content
        logger.debug(f"Text content: {self.text}")
        if self.text and any(line.get('text', '').strip() != '' for line in self.text):
            return True

        # Don't draw any text
        return False

    @property
    def need_image_text_distance(self):
        return self._label_content in (LabelContent.TEXT_QRCODE,
                                       LabelContent.IMAGE_BW,
                                       LabelContent.IMAGE_GRAYSCALE,
                                       LabelContent.IMAGE_COLORED)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value

    @property
    def qr_correction(self):
        for key, val in self.QR_CORRECTION_MAPPING.items():
            if val == self._qr_correction:
                return key
        return 'L'

    @qr_correction.setter
    def qr_correction(self, value):
        self._qr_correction = self.QR_CORRECTION_MAPPING.get(value, constants.ERROR_CORRECT_L)

    @property
    def label_orientation(self):
        return self._label_orientation

    @label_orientation.setter
    def label_orientation(self, value):
        self._label_orientation = value

    def process_templates(self) -> None:
        """Process templates in label text and code content."""
        self.text = copy.deepcopy(self.input_text)
        code_line = {'text': self.input_code_text}
        for line in self.text + [code_line]:
            text_val = line.get('text', '')
            if len(text_val) > WARNING_TEXT_LENGTH:
                logger.warning(
                    f"Text line is very long (> {WARNING_TEXT_LENGTH} characters), "
                    "this may lead to long processing times.")

            # Replace {{counter[:<start>]}} with current label counter (<start> is
            # an optional offset defaulting to 1)
            def counter_replacer(match):
                offset = int(match.group(1)) if match.group(1) else 1
                return str(self._counter + offset)
            text_val = re.sub(r"\{\{counter(?:\:(\d+))?\}\}", counter_replacer, text_val)

            # Replace {{datetime:<format>}} with current datetime formatted as <format>
            def datetime_replacer(match):
                fmt = match.group(1)
                now = datetime.datetime.fromtimestamp(self._timestamp) if self._timestamp > 0 else datetime.datetime.now()
                return now.strftime(fmt)
            text_val = re.sub(r"\{\{datetime:([^}]+)\}\}", datetime_replacer, text_val)

            # Replace {{uuid}} with a new UUID
            if "{{uuid}}" in text_val:
                ui = uuid.UUID(int=random.getrandbits(128))
                text_val = text_val.replace("{{uuid}}", str(ui))

            # Replace {{short-uuid}} with a shortened UUID
            if "{{short-uuid}}" in text_val:
                ui = uuid.UUID(int=random.getrandbits(128))
                text_val = text_val.replace("{{short-uuid}}", str(ui)[:8])

            # Replace {{random[:<len>][:shift]}} with random string of optional
            # length <len> and shifting instruction. ":s" is accepted as
            # shorthand for ":shift"
            def random_replacer(match):
                length = int(match.group(1)) if match.group(1) else DEFAULT_RANDOM_LENGTH
                if match.group(2):
                    line['shift'] = True
                return ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=length))
            text_val = re.sub(r"\{\{random(?:\:(\d+))?(?:\:(s(hift)?))?\}\}", random_replacer, text_val)

            if self.spreadsheet_row is not None:
                def column_replacer(match: re.Match[str]) -> str:
                    index = int(match.group(1)) - 1
                    return self.spreadsheet_row[index] if index < len(self.spreadsheet_row) else ''
                text_val = re.sub(r"\{\{([1-9]\d*)\}\}", column_replacer, text_val)

            line['text'] = text_val
        self._code_text = code_line['text']

    def generate(self):
        # Process possible templates in the text
        self.process_templates()
        rotated = self._label_orientation == LabelOrientation.ROTATED

        # Generate codes or load images if requested
        is_code = self._label_content in (LabelContent.QRCODE_ONLY, LabelContent.TEXT_QRCODE)
        if is_code:
            if self.barcode_type == "QR":
                img = self._generate_qr()
            elif self.barcode_type == "DATAMATRIX":
                img = self._generate_datamatrix()
            else:
                img = self._generate_barcode()
                if rotated:
                    img = img.transpose(Image.Transpose.ROTATE_90)
        elif self._label_content in (LabelContent.IMAGE_BW, LabelContent.IMAGE_GRAYSCALE, LabelContent.IMAGE_COLORED):
            img = self._image
        else:
            img = None

        # Initialize dimensions
        width, height = self._width, self._height
        margin_left, margin_right, margin_top, margin_bottom = self._label_margin
        available = max(width - margin_left - margin_right if rotated else height - margin_top - margin_bottom, 1)
        is_matrix_code = self.barcode_type in ('QR', 'DATAMATRIX')
        code_cell_size = self._qr_size if is_matrix_code else 4
        self.rendered_code_cell_size = None

        # Fit codes independently of image settings.
        if is_code:
            if self._code_fit:
                fixed_size = img.width if rotated else img.height
                if is_matrix_code:
                    cells = fixed_size // self._qr_size
                    code_cell_size = available // cells
                    if code_cell_size < 1:
                        raise ValueError('Code is too dense to fit the label at one pixel per cell.')
                    new_size = (cells * code_cell_size, cells * code_cell_size)
                else:
                    new_size = (available, img.height) if rotated else (img.width, available)
                img = img.resize(new_size, Image.Resampling.NEAREST)
            if is_matrix_code:
                self.rendered_code_cell_size = code_cell_size
        elif img is not None:
            if self._image_crop:
                img = self._crop_image_to_content(img)

            # First rotate the image if requested
            if self._image_rotation != 0 and self._image_rotation != 360:
                img = img.rotate(-self._image_rotation, expand=True, fillcolor="white")

            # Rotation with expand=True may add an empty border around content.
            if self._image_crop:
                img = self._crop_image_to_content(img)

            img_width, img_height = img.size
            # Resize image to fit if image_fit is True
            if self._image_fit:
                logger.debug(f"Available printable size: {available} px")
                logger.debug(f"Original image size: {img_width}x{img_height} px")
                scale = available / (img_width if rotated else img_height)
                logger.debug(f"Scaling image by factor: {scale}")
            else:
                # Use image_scaling_factor if provided
                scale = self._image_scaling_factor / 100.0
                logger.debug(f"Manual image scaling factor: {scale}")
            new_size = (max(1, int(img_width * scale)), max(1, int(img_height * scale)))
            logger.debug(f"Resized image size: {new_size} px")
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        img_width, img_height = img.size if img is not None else (0, 0)

        want_text = self.want_text(img)
        bboxes = []
        if want_text:
            self._auto_scale_text(available, height=not rotated)
            bboxes = self._draw_text(None, [])
        textsize = self._compute_bbox(bboxes)

        code_text_gap = code_cell_size if is_code and want_text else 0

        # Adjust the tape length to fit the content and position text and images.
        if rotated:
            height = img_height + code_text_gap + textsize[3] - textsize[1] + margin_top + margin_bottom
            vertical_offset_text = margin_top
            if self.need_image_text_distance and not is_code:
                # Slightly increase the margin to get some distance from the QR code.
                vertical_offset_text *= 1.25

            vertical_offset_text += img_height + code_text_gap
            horizontal_offset_text = max((width - textsize[2])//2, 0)
            horizontal_offset_image = (width - img_width)//2
            vertical_offset_image = margin_top

        else:
            width = img_width + code_text_gap + textsize[2] + margin_left + margin_right
            vertical_offset_text = (height - textsize[3])//2
            vertical_offset_text += (margin_top - margin_bottom)//2
            horizontal_offset_text = margin_left
            if self.need_image_text_distance and not is_code:
                # Slightly increase the margin to get some distance from the QR code.
                horizontal_offset_text *= 1.25

            horizontal_offset_text += img_width + code_text_gap
            horizontal_offset_image = margin_left
            vertical_offset_image = (height - img_height)//2

        # Ensure height and width are at least 1 to avoid generating valishing
        # preview images for empty inputs. PIL cannot store images with 0
        # width/height dimensions
        width = max(int(width), 1)
        height = max(int(height), 1)

        text_offset = horizontal_offset_text, vertical_offset_text
        image_offset = horizontal_offset_image, vertical_offset_image

        logger.debug(f"Image resolution: {width} x {height} px")
        imgResult = Image.new('RGB', (width, height), 'white')

        if img is not None:
            imgResult.paste(img, image_offset)

        if want_text:
            self._draw_text(imgResult, bboxes, text_offset)

        self.render_warning = None
        if self._fixed_length:
            content_length = height if rotated else width
            size = (width, self._fixed_length) if rotated else (self._fixed_length, height)
            if content_length > self._fixed_length:
                self.render_warning = 'Content was cropped to fit the fixed label length.'
                imgResult = imgResult.crop((0, 0, *size))
            elif content_length < self._fixed_length:
                offset = (self._fixed_length - content_length) // 2
                padded = Image.new('RGB', size, 'white')
                padded.paste(imgResult, (0, offset) if rotated else (offset, 0))
                imgResult = padded

        # Draw border if thickness > 0
        if self._border_thickness > 0:
            draw = ImageDraw.Draw(imgResult)
            # Calculate border rectangle (inside the image, respecting thickness)
            rect = [self._border_distance[0],
                    self._border_distance[1],
                    imgResult.width - self._border_distance[0] - 1,
                    imgResult.height - self._border_distance[1] - 1]
            # Validity checks on rect:
            # - x1 >= x0
            # - y1 >= y0
            if rect[2] < rect[0] or rect[3] < rect[1]:
                raise ValueError("Invalid border rectangle")

            # Draw (rounded) rectangle
            draw.rounded_rectangle(rect, radius=self._border_roundness, outline=self._border_color, width=self._border_thickness)
        return imgResult

    def _auto_scale_text(self, available: int, height: bool) -> None:
        """Choose the largest font size that fits the label's constrained axis."""
        auto_lines = [line for line in self.text if line.get('auto_scale')]
        if not auto_lines or not any(line.get('text', '') for line in auto_lines):
            return

        def fits(size: int) -> bool:
            for line in auto_lines:
                line['size'] = size
            bbox = self._compute_bbox(self._draw_text(None, []))
            used = bbox[3] - bbox[1] if height else bbox[2]
            return used <= available

        low, high = 1, 4096
        while low < high:
            candidate = (low + high + 1) // 2
            if fits(candidate):
                low = candidate
            else:
                high = candidate - 1
        for line in auto_lines:
            line['size'] = low

    @staticmethod
    def _crop_image_to_content(img: Image.Image) -> Image.Image:
        """Trim uniform border/background from an image.

        The background color is inferred from the top-left pixel to support
        white as well as non-white backgrounds.
        """
        if img.width <= 1 or img.height <= 1:
            return img

        if 'A' in img.getbands():
            alpha_bbox = img.getchannel('A').getbbox()
            if alpha_bbox is not None:
                return img.crop(alpha_bbox)

        background_color = img.getpixel((0, 0))
        background = Image.new(img.mode, img.size, background_color)
        diff = ImageChops.difference(img, background)
        bbox = diff.getbbox()
        if bbox is None:
            return img
        return img.crop(bbox)

    def _generate_barcode(self):
        barcode_generator = barcode.get_barcode_class(self.barcode_type)
        if len(self._code_text) > 0:
            value = self._code_text
        else:
            # Take value from the first line of text
            value = self.text[0].get('text', '') if self.text and self.text[0].get('text', '') else ''
        my_barcode = barcode_generator(value, writer=ImageWriter())
        return my_barcode.render(writer_options={'write_text': False})

    def _generate_datamatrix(self):
        text = self._code_text or "\n".join(line.get('text', '') for line in self.text)
        code = zxingcpp.create_barcode(text, zxingcpp.BarcodeFormat.DataMatrix, force_square=True)
        return Image.fromarray(code.to_image(scale=self._qr_size, add_quiet_zones=False))

    def _generate_qr(self):
        qr = QRCode(
            version=1,
            error_correction=self._qr_correction,
            box_size=self._qr_size,
            border=0,
        )
        text = self._code_text or "\n".join(line.get('text', '') for line in self.text)
        qr.add_data(text.encode("utf-8-sig"))
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color="white")
        return qr_img.get_image()

    def _draw_text(self, img = None, bboxes = [], text_offset = (0, 0)):
        """
        Returns a list of bounding boxes for each line, so each line can use a different font.
        """
        do_draw = img is not None
        if not do_draw:
            img = Image.new('L', (20, 20), 'white')
        draw = ImageDraw.Draw(img)
        y = 0
        if do_draw:
            min_bbox_x = min((bbox[0][0] for bbox in bboxes), default=0)
            max_bbox_x = max((bbox[0][2] for bbox in bboxes), default=0)

        # Iterate over lines of text
        for i, line in enumerate(self.text):
            # Calculate spacing
            spacing = int(int(line['size'])*((int(line['line_spacing']) - 100) / 100)) if 'line_spacing' in line else 0

            # Get font
            font = self._get_font(line['path'], line['size'])

            # Determine anchors
            anchor = None
            align = line.get('align', 'center')

            # Left aligned text
            if align == "left":
                anchor = "lt"
            # Center aligned text
            elif align == "center":
                anchor = "mt"
            # Right aligned text
            elif align == "right":
                anchor = "rt"
            # else: error
            else:
                raise ValueError(f"Unsupported alignment: {align}")

            color = (0, 0, 0)

            INVERT_LINE = 'inverted' in line and line['inverted']

            # Either calculate bbox or actually draw
            if not do_draw:
                # Get bbox of the text
                bbox = draw.textbbox((0, y), line['text'], font=font, align=align, anchor="lt")

                # Ensure consistent line heights for each line except the last
                # one (where it is not needed).
                IS_LAST_LINE = i == len(self.text) - 1
                if not IS_LAST_LINE:
                    # Some characters may need special height
                    all_characters = ''.join(string.ascii_letters + string.digits + string.punctuation)
                    Ag = draw.textbbox((0, y), all_characters, font, anchor="lt")
                    # Get bbox with width of text and dummy height
                    bbox = (bbox[0], Ag[1], bbox[2], Ag[3])
                bboxes.append((bbox, y))
                y += bbox[3] - bbox[1] + (spacing if i < len(self.text)-1 else 0)
            else:
                bbox = bboxes[i][0]
                y = bboxes[i][1] + text_offset[1]
                # Left aligned text
                if align == "left":
                    x = min_bbox_x + text_offset[0]
                # Center aligned text
                elif align == "center":
                    x = (max_bbox_x - min_bbox_x) // 2 + min_bbox_x + text_offset[0]
                # Right aligned text
                elif align == "right":
                    x = max_bbox_x + text_offset[0]

                if INVERT_LINE:
                    text_bbox = draw.textbbox((x, y), line['text'], font=font, align=align, anchor=anchor)
                    padding = max(1, round(int(line['size']) * 0.1))
                    line_top = min(text_bbox[1] - padding, bbox[1] + text_offset[1])
                    line_bottom = max(text_bbox[3] + padding, bbox[3] + text_offset[1])
                    draw.rectangle((text_bbox[0], line_top, text_bbox[2], line_bottom), fill=color)
                    color = (255, 255, 255)

                draw.text((x, y), line['text'], color, font=font, anchor=anchor, align=align, spacing=spacing)

                # Shift text around if requested
                if "shift" in line:
                    def get_shift_amount():
                        return 0.03 * random.randint(5, 10) * int(line['size'])
                    for x_shift in [-get_shift_amount(), get_shift_amount()]:
                        for y_shift in [-get_shift_amount(), get_shift_amount()]:
                            new_random_text = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=len(line['text'])))
                            draw.text((x + x_shift, y + y_shift), new_random_text, color, font=font, anchor=anchor, align=align, spacing=spacing)

        # Return total bbox
        # each in form (x0, y0, x1, y1)
        return bboxes

    def _compute_bbox(self, bboxes):
        # Edge case: No text
        if not bboxes:
            return (0, 0, 0, 0)
        # Iterate over right margins of multiple text lines and find the maximum
        # width needed to fit all lines of text
        max_width = max(bbox[0][2] for bbox in bboxes)
        return (bboxes[0][0][0], bboxes[0][0][1], max_width, bboxes[-1][0][3])

    def _get_font(self, font_path: str, size: int) -> ImageFont.FreeTypeFont:
        """Get a font object, using cache for performance."""
        key = (font_path, size)
        if key in FONT_CACHE:
            return FONT_CACHE[key]
        try:
            font = ImageFont.truetype(font_path, int(size))
            FONT_CACHE[key] = font
            return font
        except Exception as e:
            logger.error(f"Failed to load font '{font_path}' with size {size}: {e}")
            return ImageFont.load_default()
