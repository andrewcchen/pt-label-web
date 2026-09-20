#!/usr/bin/env python

import logging
from brother_ql.models import ALL_MODELS

logger = logging.getLogger(__name__)

RESP_ERROR_INFORMATION_1_DEF = {
  0: 'No media when printing',
  1: 'End of media',
  2: 'Tape cutter jam',
  3: 'Weak batteries',
  4: 'Main unit in use',
  5: 'Printer turned off',
  6: 'High-voltage adapter (not used)',
  7: 'Fan doesn\'t work',
}

RESP_ERROR_INFORMATION_2_DEF = {
  0: 'Replace media error',
  1: 'Expansion buffer full error',
  2: 'Transmission / Communication error',
  3: 'Communication buffer full error (not used)',
  4: 'Cover opened while printing',
  5: 'Cancel key or overheating error',
  6: 'Media cannot be fed (also when the media end is detected)',
  7: 'System error',
}

RESP_MEDIA_TYPES = {
  0x00: 'No media',
  0x01: 'Laminated tape',
  0x03: 'Non-laminated type',
  0x04: 'Fabric tape',
  0x11: 'Heat-Shrink Tube (HS 2:1)',
  0x13: 'Fle tape',
  0x14: 'Flexible ID tape',
  0x15: 'Satin tape',
  0x17: 'Heat-Shrink Tube (HS 3:1)',
  0xFF: 'Incompatible tape',
}

RESP_MEDIA_CATEGORIES = {
  0x00: 'No media',
  0x01: 'TZe', # probably also HGe (high grade)
  0x03: 'TZe', # probably also STe (stencil)
  0x04: 'TZe',
  0x11: 'HSe',
  0x13: 'Fle',
  0x14: 'TZe',
  0x15: 'TZe',
  0x17: 'HSe',
  0xFF: 'Incompatible',
}

RESP_TAPE_COLORS = {
  0x00: 'No Media',
  0x01: 'White',
  0x02: 'Other',
  0x03: 'Clear',
  0x04: 'Red',
  0x05: 'Blue',
  0x06: 'Yellow',
  0x07: 'Green',
  0x08: 'Black',
  0x09: 'Clear(White text)',
  0x20: 'Matte White',
  0x21: 'Matte Clear',
  0x22: 'Matte Silver',
  0x23: 'Satin Gold',
  0x24: 'Satin Silver',
  0x30: 'Blue(D)',
  0x31: 'Red(D)',
  0x40: 'Fluorescent Orange',
  0x41: 'Fluorescent Yellow',
  0x50: 'Berry Pink(S)',
  0x51: 'Light Gray(S)',
  0x52: 'Lime Green(S)',
  0x60: 'Yellow(F)',
  0x61: 'Pink(F)',
  0x62: 'Blue(F)',
  0x70: 'White(Heat-shrink Tube)',
  0x90: 'White(Flex. ID)',
  0x91: 'Yellow(Flex. ID)',
  0xF0: 'Cleaning',
  0xF1: 'Stencil',
  0xFF: 'Incompatible',
}

RESP_TEXT_COLORS = {
  0x00: 'No Media',
  0x01: 'White',
  0x04: 'Red',
  0x05: 'Blue',
  0x08: 'Black',
  0x0A: 'Gold',
  0x62: 'Blue(F)',
  0xF0: 'Cleaning',
  0xF1: 'Stencil',
  0x02: 'Other',
  0xFF: 'Incompatible',
}

RESP_STATUS_TYPES = {
  0x00: 'Reply to status request',
  0x01: 'Printing completed',
  0x02: 'Error occurred',
  0x03: 'Exit IF mode',
  0x04: 'Turned off',
  0x05: 'Notification',
  0x06: 'Phase change',
  0xF0: 'Settings report',
}

RESP_PHASE_TYPES = {
  0x00: 'Waiting to receive',
  0x01: 'Printing state',
}

RESP_BYTE_NAMES = [
  'Print head mark (0x80)',
  'Size (0x20)',
  'Brother code (B=0x42)',
  'Series code',
  'Model code',
  'Country code',
  'Power status',
  'Reserved',
  'Error information 1',
  'Error information 2',
  'Media width',
  'Media type',
  'Number of colors',
  'Media length (high)',
  'Media sensor value',
  'Mode',
  'Density',
  'Media length (low)',
  'Status type',
  'Phase type',
  'Phase number (high)',
  'Phase number (low)',
  'Notification number',
  'Expansion area',
  'Tape color information',
  'Text color information',
  'Hardware settings 1',
  'Hardware settings 2',
  'Hardware settings 3',
  'Hardware settings 4',
  'Requested setting',
  'Reserved',
]

def hex_format(data):
    return ' '.join('{:02X}'.format(byte) for byte in data)

def interpret_response(data):
    data = bytes(data)
    if len(data) < 32:
        raise NameError('Insufficient amount of data received', hex_format(data))
    if not data.startswith(b'\x80\x20\x42'):
        raise NameError("Printer response doesn't start with the usual header (80:20:42)", hex_format(data))
    for i, byte_name in enumerate(RESP_BYTE_NAMES):
        logger.debug('Byte %2d %24s %02X', i, byte_name+':', data[i])
    series_code = data[3]
    model_code = data[4]

    # printer model detection
    model = "Unknown"
    for m in ALL_MODELS:
        if series_code == m.series_code and model_code == m.model_code:
            model = m.identifier
            break

    errors = []
    error_info_1 = data[8]
    error_info_2 = data[9]
    for error_bit in RESP_ERROR_INFORMATION_1_DEF:
        if error_info_1 & (1 << error_bit):
            logger.error('Error: ' + RESP_ERROR_INFORMATION_1_DEF[error_bit])
            errors.append(RESP_ERROR_INFORMATION_1_DEF[error_bit])
    for error_bit in RESP_ERROR_INFORMATION_2_DEF:
        if error_info_2 & (1 << error_bit):
            logger.error('Error: ' + RESP_ERROR_INFORMATION_2_DEF[error_bit])
            errors.append(RESP_ERROR_INFORMATION_2_DEF[error_bit])

    media_width  = data[10]
    media_length = data[17]

    media_code = data[11]
    media_sensor = data[14]
    media_category = ""
    if media_code in RESP_MEDIA_TYPES:
        media_type = RESP_MEDIA_TYPES[media_code]
        media_category = RESP_MEDIA_CATEGORIES[media_code]
        logger.debug("Media type: %s", media_type)
    else:
        logger.error("Unknown media type %02X", media_code)

    tape_color_code = data[24]
    text_color_code = data[25]
    tape_color = ''
    text_color = ''
    tape_color = RESP_TAPE_COLORS.get(tape_color_code, 'Unknown')
    text_color = RESP_TEXT_COLORS.get(text_color_code, 'Unknown')

    status_code = data[18]
    if status_code in RESP_STATUS_TYPES:
        status_type = RESP_STATUS_TYPES[status_code]
        logger.debug("Status type: %s", status_type)
    else:
        logger.error("Unknown status type %02X", status_code)

    phase_code = data[19]
    phase_type = ''
    if phase_code in RESP_PHASE_TYPES:
        phase_type = RESP_PHASE_TYPES[phase_code]
        logger.debug("Phase type: %s", phase_type)
    else:
        logger.error("Unknown phase type %02X", phase_code)

    # settings report
    setting = None
    if status_code == 0xF0:
        logger.debug("Settings report detected")
        setting = data[30]

    response = {
      'series_code': series_code,
      'model_code': model_code,
      'model': model,
      'status_type': status_type,
      'status_code': status_code,
      'phase_type': phase_type,
      'phase_code': phase_code,
      'media_type': media_type,
      'media_category': media_category,
      'media_sensor': media_sensor,
      'tape_color': tape_color,
      'text_color': text_color,
      'media_width': media_width,
      'media_length': media_length,
      'setting': setting,
      'errors': errors,
    }
    return response
