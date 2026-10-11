#!/usr/bin/env python

import logging

from PIL import Image
import PIL.ImageOps

from brother_pt.labels import ALL_LABELS
from brother_pt.raster import BrotherQLRaster

logger = logging.getLogger(__name__)

logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

LABELS = {label.identifier: label for label in ALL_LABELS}

def _rasterize_images(qlr: BrotherQLRaster, images, label, **kwargs):
    """Convert images to P-touch raster instructions."""
    label_spec = LABELS[label]
    page_options = kwargs.pop('page_options', None)
    if page_options is not None and len(page_options) != len(images):
        raise ValueError("page_options must contain one entry per image")

    dots_printable = label_spec.dots_printable
    right_margin_dots = label_spec.offset_r
    device_pixel_width = qlr.get_pixel_width()

    qlr.add_switch_mode()

    page_data = []
    logger.info("Rasterizing %d pages", len(images))
    for i, image in enumerate(images):
        options = dict(kwargs)
        if page_options is not None:
            options.update(page_options[i])
        cut = options.get('cut', True)
        dither = options.get('dither', False)
        compress = options.get('compress', False)
        rotate = options.get('rotate', 'auto')
        if rotate != 'auto':
            rotate = int(rotate)
        hires = options.get('hires', False)
        chain_print = options.get('chain_print', False)
        hq = options.get('hq', True)
        threshold = 100.0 - options.get('threshold', 70)
        threshold = min(255, max(0, int(threshold / 100.0 * 255)))

        if isinstance(image, Image.Image):
            im = image
        else:
            try:
                im = Image.open(image)
            except OSError:
                raise NotImplementedError(
                    "The image argument needs to be an Image() instance, "
                    "the filename to an image, or a file handle."
                )

        if im.mode.endswith('A'):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, im.split()[-1])
            im = bg
        elif im.mode == "P":
            im = im.convert("L")

        if rotate not in ('auto', 0):
            im = im.rotate(rotate, expand=True)
        if hires:
            im = im.resize((im.size[0] // 2, im.size[1]))
        if im.size[0] != dots_printable:
            hsize = int((dots_printable / im.size[0]) * im.size[1])
            im = im.resize((dots_printable, hsize), Image.LANCZOS)
            logger.debug('Need to resize the image...')
        if im.size[0] < device_pixel_width:
            new_im = Image.new(im.mode, (device_pixel_width, im.size[1]), (255,) * len(im.mode))
            new_im.paste(im, (device_pixel_width - im.size[0] - right_margin_dots, 0))
            im = new_im

        im = im.convert("L")
        im = PIL.ImageOps.invert(im)
        if dither:
            im = im.convert("1", dither=Image.FLOYDSTEINBERG)
        else:
            im = im.point(lambda x: 0 if x < threshold else 255, mode="1")

        tape_size = label_spec.tape_size
        qlr.mtype = label_spec.media_type
        qlr.mwidth = tape_size
        qlr.mlength = 0
        qlr.pquality = int(hq)
        qlr.add_media_and_quality(im.size[1])
        qlr.add_autocut(cut)
        qlr.half_cut = options.get('half_cut', False)
        qlr.hires = hires
        qlr.cut_at_end = cut
        qlr.no_chain_printing = not chain_print
        qlr.add_expanded_mode()
        qlr.add_margins(label_spec.feed_margin * (2 if hires else 1))
        qlr.add_compression(compress)
        qlr.add_raster_data(im)

        if i == len(images) - 1:
            qlr.add_print()
        else:
            qlr.add_print(last_page=False)

        qlr.page_number += 1
        page_data.append(qlr.data)
        qlr.clear()

    return b''.join(page_data)


def convert(qlr: BrotherQLRaster, images, label, **kwargs):
    """Convert images using the legacy single-result API."""
    qlr.add_invalidate()
    qlr.add_initialize()
    setup_data = qlr.data
    qlr.clear()
    page_data = _rasterize_images(qlr, images, label, **kwargs)
    return setup_data + page_data
