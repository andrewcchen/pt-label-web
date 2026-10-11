"""
This module contains the implementation of the raster language
of Brother P-touch label printers according to their
documentation and to reverse engineering efforts.

The central piece of code in this module is the class
:py:class:`BrotherQLRaster`.
"""

import struct
import logging

import packbits
from PIL import Image

from brother_pt.models import ALL_MODELS

from . import BrotherQLUnknownModel, BrotherQLRasterError
from io import BytesIO

logger = logging.getLogger(__name__)

class BrotherQLRaster(object):

    """
    This class facilitates the creation of a complete set
    of raster instructions by adding them one after the other
    using the methods of the class. Each method call is adding
    instructions to the member variable :py:attr:`data`.

    Instatiate the class by providing the printer
    model as argument.

    :param str model: Choose from the list of available models.

    :ivar bytes data: The resulting bytecode with all instructions.
    """

    def __init__(self, model='PT-P750W'):
        try:
            self._model = next(model_info for model_info in ALL_MODELS
                               if model_info.identifier == model)
        except StopIteration:
            raise BrotherQLUnknownModel()
        self.model = model
        self.data = b''
        self._pquality = True
        self.page_number = 0
        self.cut_at_end = True
        self.hires = False
        self.compression_enabled = False
        self.half_cut = True
        self.no_chain_printing = True

    def add_initialize(self):
        self.page_number = 0
        self.data += b'\x1B\x40' # ESC @

    def add_status_information(self):
        """ Status Information Request """
        self.data += b'\x1B\x69\x53' # ESC i S

    def add_switch_mode(self):
        """
        Switch dynamic command mode
        Switch to the raster mode on the printers that support
        the mode change (others are in raster mode already).
        """
        self.data += b'\x1B\x69\x61\x01' # ESC i a

    def add_invalidate(self):
        """ clear command buffer """
        self.data += b'\x00' * 100

    @property
    def mtype(self): return self._mtype

    @property
    def mwidth(self): return self._mwidth

    @property
    def mlength(self): return self._mlength

    @property
    def pquality(self): return self._pquality

    @mtype.setter
    def mtype(self, value):
        self._mtype = None if value is None else bytes([value & 0xFF])

    @mwidth.setter
    def mwidth(self, value):
        self._mwidth = bytes([value & 0xFF])

    @mlength.setter
    def mlength(self, value):
        self._mlength = bytes([value & 0xFF])

    @pquality.setter
    def pquality(self, value):
        self._pquality = bool(value)

    def add_media_and_quality(self, rnumber):
        self.data += b'\x1B\x69\x7A' # ESC i z
        valid_flags = 0x80
        valid_flags |= (self._mtype is not None) << 1
        valid_flags |= (self._mwidth is not None) << 2
        valid_flags |= (self._mlength is not None) << 3
        valid_flags |= self._pquality << 6
        self.data += bytes([valid_flags])
        vals = [self._mtype, self._mwidth, self._mlength]
        self.data += b''.join(b'\x00' if val is None else val for val in vals)
        self.data += struct.pack('<L', rnumber)
        self.data += bytes([0 if self.page_number == 0 else 1])
        self.data += b'\x00'
        # INFO:  media/quality (1B 69 7A) --> found! (payload: 8E 0A 3E 00 D2 00 00 00 00 00)

    def add_autocut(self, autocut = False):
        self.data += b'\x1B\x69\x4D' # ESC i M
        self.data += bytes([autocut << 6])

    def add_cut_interval(self, pages=1):
        self.data += b'\x1B\x69\x41' + bytes([pages]) # ESC i A

    def add_expanded_mode(self):
        self.data += b'\x1B\x69\x4B' # ESC i K
        flags = 0x00
        flags |= self.half_cut << 2
        flags |= self.no_chain_printing << 3
        flags |= self.hires << 6
        self.data += bytes([flags])

    def add_margins(self, dots=0x23):
        self.data += b'\x1B\x69\x64' # ESC i d
        self.data += struct.pack('<H', dots)

    def add_compression(self, compression=True):
        """
        Add an instruction enabling or disabling compression for the transmitted raster image lines.

        :param bool compression: Whether compression should be on or off
        """
        self.compression_enabled = compression
        self.data += b'\x4D' # M
        self.data += bytes([compression << 1])

    def get_pixel_width(self):
        return self._model.number_bytes_per_row * 8

    def add_raster_data(self, image):
        """
        Add the image data to the instructions.
        The provided image has to be binary (every pixel
        is either black or white).

        :param PIL.Image.Image image: The image to be converted and added to the raster instructions
        """
        logger.debug("raster_image_size: {0}x{1}".format(*image.size))
        if image.size[0] != self.get_pixel_width():
            fmt = 'Wrong pixel width: {}, expected {}'
            raise BrotherQLRasterError(fmt.format(image.size[0], self.get_pixel_width()))
        frames = []
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
        image = image.convert("1")
        frames.append(bytes(image.tobytes(encoder_name='raw')))
        frame_len = len(frames[0])
        row_len = image.size[0] // 8
        start = 0
        file_str = BytesIO()
        while start + row_len <= frame_len:
            row = frames[0][start:start+row_len]
            if self.compression_enabled:
                row = packbits.encode(row)
            translen = len(row) # number of bytes to be transmitted
            file_str.write(b'\x47')
            file_str.write(bytes([translen % 256, translen // 256]))
            file_str.write(row)
            start += row_len
        self.data += file_str.getvalue()

    def add_print(self, last_page=True):
        if last_page:
            self.data += b'\x1A' # 0x1A = ^Z = SUB; here: EOF = End of File
        else:
            self.data += b'\x0C' # 0x0C = FF  = Form Feed

    def clear(self):
        self.data = b''
