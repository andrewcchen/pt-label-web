from attr import attrs, attrib


@attrs
class Label(object):
    """A P-touch tape and the dimensions needed by the rasterizer."""

    identifier = attrib(type=str)
    tape_size = attrib(type=int)
    dots_printable = attrib(type=int)
    offset_r = attrib(type=int)
    feed_margin = attrib(type=int)
    label_name = attrib(type=str)
    media_type = attrib(default=None)

    @property
    def name(self):
        return self.label_name


def _tze(identifier, name, media_width, printable, offset):
    return Label(identifier, media_width, printable, offset, feed_margin=14, label_name=name)


def _hse(identifier, name, media_width, printable, offset, media_type):
    return Label(identifier, media_width, printable, offset, feed_margin=14, label_name=name, media_type=media_type)


# Brother PT-E550W/PT-P750W/PT-P710BT Raster Command Reference, sections
# 2.3.5 (printable pins) and 4 (media width and media type).
ALL_LABELS = (
    _tze("tze3.5", "3.5mm TZe tape", 4, 24, 52),
    _tze("tze6", "6mm TZe tape", 6, 32, 48),
    _tze("tze9", "9mm TZe tape", 9, 50, 39),
    _tze("tze12", "12mm TZe tape", 12, 70, 29),
    _tze("tze18", "18mm TZe tape", 18, 112, 8),
    _tze("tze24", "24mm TZe tape", 24, 128, 0),
    _hse("hse2-5.8", "5.8mm HSe tube (2:1)", 6, 28, 50, 0x11),
    _hse("hse2-8.8", "8.8mm HSe tube (2:1)", 9, 48, 40, 0x11),
    _hse("hse2-11.7", "11.7mm HSe tube (2:1)", 12, 66, 31, 0x11),
    _hse("hse2-17.7", "17.7mm HSe tube (2:1)", 18, 106, 11, 0x11),
    _hse("hse2-23.6", "23.6mm HSe tube (2:1)", 24, 128, 0, 0x11),
    _hse("hse3-5.2", "5.2mm HSe tube (3:1)", 6, 20, 54, 0x17),
    _hse("hse3-9.0", "9.0mm HSe tube (3:1)", 9, 44, 42, 0x17),
    _hse("hse3-11.2", "11.2mm HSe tube (3:1)", 12, 50, 39, 0x17),
    _hse("hse3-21.0", "21.0mm HSe tube (3:1)", 24, 120, 4, 0x17),
)
