from attr import attrs, attrib


@attrs
class Label(object):
    """A P-touch tape and the dimensions needed by the rasterizer."""

    identifier = attrib(type=str)
    tape_size = attrib(type=int)
    dots_printable = attrib(type=int)
    offset_r = attrib(type=int)
    feed_margin = attrib(type=int, default=0)

    @property
    def name(self):
        return '{0}mm P-touch endless'.format(self.tape_size)


ALL_LABELS = (
    Label("pt12", 12, 70, 29, feed_margin=14),
    Label("pt18", 18, 112, 8, feed_margin=14),
    Label("pt24", 24, 128, 0, feed_margin=14),
    Label("pt36", 36, 454, 61, feed_margin=14),
)
