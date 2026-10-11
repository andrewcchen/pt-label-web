from attr import attrs, attrib


@attrs
class Model(object):
    """
    This class represents a P-touch printer model. All specifics of a
    certain model and the opcodes it supports are contained in this class.
    """

    identifier = attrib(type=str)
    number_bytes_per_row = attrib(type=int, default=90)
    series_code = attrib(type=int, default=0xFFFF)
    model_code = attrib(type=int, default=0xFFFF)
    product_id = attrib(type=int, default=0xFFFF)

ALL_MODELS = [
    Model(
        identifier="PT-E550W",
        number_bytes_per_row=16,
        series_code=0x30,
        model_code=0x66,
        product_id=0x2060,
    ),
    Model(
        identifier="PT-P700",
        number_bytes_per_row=16,
        series_code=0x30,
        model_code=0x67,
        product_id=0x2061,
    ),
    Model(
        identifier="PT-P750W",
        number_bytes_per_row=16,
        series_code=0x30,
        model_code=0x68,
        product_id=0x2062,
    ),
    # Model(
    #     identifier="PT-P900W",
    #     number_bytes_per_row=70,
    #     series_code=0x30,
    #     model_code=0x69,
    #     product_id=0x2085,
    # ),
    # Model(
    #     identifier="PT-P950NW",
    #     number_bytes_per_row=70,
    #     series_code=0x30,
    #     model_code=0x70,
    #     product_id=0x2086,
    # ),
]
