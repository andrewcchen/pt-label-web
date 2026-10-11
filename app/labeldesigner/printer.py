import base64
import logging
import os
import socket
import time
from urllib.parse import urlparse
from brother_pt.backends.helpers import send
from brother_pt import BrotherQLRaster
from brother_pt.conversion import convert
from brother_pt.backends.helpers import get_status
from brother_pt.backends import backend_factory, guess_backend
from brother_pt.reader import interpret_response
from flask import Config
from PIL import Image
from .label import LabelOrientation

# Default maximum number of labels to rasterize and send in a single batch.
# Sending too many labels at once can cause printer timeouts/failures.
# Override via PRINT_BATCH_SIZE environment variable or Flask config.
DEFAULT_BATCH_SIZE = 5

logger = logging.getLogger(__name__)


def render_label_bitmap(label):
    return label.generate().convert('1', dither=Image.Dither.NONE)

# Brother private SNMP OID 1.3.6.1.4.1.2435.3.3.9.1.6.1.0. The response
# contains the same 32-byte status structure used by the USB backend.
BROTHER_SNMP_STATUS_REQUEST = bytes.fromhex(
    '30 2c 02 01 00 04 06 70 75 62 6c 69 63 a0 1f 02 01 00 02 01 00 '
    '02 01 00 30 14 30 12 06 0e 2b 06 01 04 01 93 03 03 03 09 01 06 '
    '01 00 05 00'
)


def get_network_status(device_specifier: str, timeout: float = 2.0):
    """Request a Brother status record over SNMP."""
    parsed = urlparse(device_specifier)
    if parsed.scheme != 'tcp' or not parsed.hostname:
        raise ValueError(f'Invalid TCP printer address: {device_specifier}')

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as snmp_socket:
        snmp_socket.settimeout(timeout)
        snmp_socket.sendto(BROTHER_SNMP_STATUS_REQUEST, (parsed.hostname, 161))
        response, _ = snmp_socket.recvfrom(4096)

    status_start = response.find(b'\x80\x20\x42')
    if status_start < 0 or len(response) < status_start + 32:
        raise ValueError('Brother SNMP response did not contain a status record')
    return interpret_response(response[status_start:status_start + 32])


class PrinterQueue:
    def __init__(self, model, device_specifier, label_size):
        self.model = model
        self.device_specifier = device_specifier
        self.label_size = label_size
        self._print_queue = []
        self.warnings = []

    def add_label_to_queue(self, label, cut: bool = True, high_res: bool = False, chain_print: bool = False, half_cut: bool = False, no_cut: bool = False):
        self._print_queue.append({
            'label': label,
            'cut': cut and not no_cut,
            'half_cut': half_cut and not no_cut,
            'high_res': high_res,
            'chain_print': chain_print or no_cut
        })

    def _rasterize_entries(self, entries):
        """Rasterize a list of queue entries into a BrotherQLRaster."""
        qlr = BrotherQLRaster(self.model)
        images = []
        page_options = []
        for entry in entries:
            label = entry['label']
            rotate = 0 if label.label_orientation == LabelOrientation.ROTATED else 90
            img = render_label_bitmap(label)
            warning = label.render_warning
            if warning and warning not in self.warnings:
                self.warnings.append(warning)
            images.append(img)
            page_options.append({
                'cut': entry['cut'],
                'half_cut': entry['half_cut'],
                'hires': entry['high_res'],
                'chain_print': entry['chain_print'],
                'rotate': rotate,
            })
        qlr.data = convert(
            qlr,
            images,
            self.label_size,
            dither=False,
            page_options=page_options
        )
        return qlr

    def _send_raster(self, qlr, batch_index=0) -> str:
        """Send rasterized data to the printer or simulator.
        Returns an empty string on success, or an error message."""
        try:
            # Simulator: pretend we sent data, log the printer commands, and return success
            if isinstance(self.device_specifier, str) and self.device_specifier in ['simulation', '?']:
                logger.debug('Simulated sending %d bytes to simulator printer (batch %d)',
                             len(qlr.data), batch_index)
                encoded = base64.b64encode(bytes(qlr.data)).decode('ascii')
                logger.debug('Simulated printer commands (batch %d) base64: %s',
                             batch_index, encoded)
                return ""

            network_printer = isinstance(self.device_specifier, str) and self.device_specifier.startswith('tcp://')
            logger.info("Sending %d bytes to printer at %s (batch %d)",
                        len(qlr.data), self.device_specifier, batch_index)
            info = send(qlr.data, self.device_specifier)
            logger.info('Sent %d bytes to printer %s', len(qlr.data), self.device_specifier)
            if network_printer:
                logger.info('Network printer does not provide status information.')
                return ""
            logger.info('Printer response: %s', str(info))
            if info.get('did_print') and info.get('ready_for_next_job'):
                logger.info('Label printed successfully and printer is ready for next job')
                return ""
            logger.warning("Failed to print label (batch %d)", batch_index)
            return f"Failed to print label (batch {batch_index})"
        except Exception as e:
            logger.exception("Exception during sending to printer (batch %d): %s", batch_index, e)
            return f"Exception during sending to printer (batch {batch_index}): {e}"

    def process_queue(self, batch_size: int = 0) -> str:
        if not self._print_queue:
            logger.warning("Print queue is empty.")
            return "Print queue is empty."

        if batch_size < 1:
            batch_size = int(os.environ.get('PRINT_BATCH_SIZE', DEFAULT_BATCH_SIZE))
        if batch_size < 1:
            batch_size = DEFAULT_BATCH_SIZE

        total = len(self._print_queue)
        entries = list(self._print_queue)
        self._print_queue.clear()

        # Split into batches to avoid printer timeouts on large jobs
        for batch_index, start in enumerate(range(0, total, batch_size), start=1):
            batch = entries[start:start + batch_size]
            logger.info('Processing batch %d (%d labels, %d/%d)',
                        batch_index, len(batch), start + len(batch), total)
            qlr = self._rasterize_entries(batch)
            status = self._send_raster(qlr, batch_index)
            if status:
                return status

        return ""


def get_printer(printer_identifier=None, backend_identifier=None):
    """
    Instantiate a printer object for communication. Only bidirectional transport backends are supported.

    :param str printer_identifier: Identifier for the printer.
    :param str backend_identifier: Can enforce the use of a specific backend.1
    """

    selected_backend = None
    if backend_identifier:
        selected_backend = backend_identifier
    else:
        try:
            selected_backend = guess_backend(printer_identifier)
        except ValueError:
            logger.info("No backend stated. Selecting the default linux_kernel backend.")
            selected_backend = "linux_kernel"

    be = backend_factory(selected_backend)
    BrotherQLBackend = be["backend_class"]
    printer = BrotherQLBackend(printer_identifier)
    return printer


_last_scan_ts = 0
_cached_printers = []


def get_ptr_status(config: Config):
    # Simple in-memory cache for detected printers
    global _last_scan_ts, _cached_printers

    device_specifier = config['PRINTER_PRINTER']
    default_model = config['PRINTER_MODEL']

    SIMULATOR_PRINTER = {
        'errors': [],
        'path': 'simulation',
        'media_category': None,
        'media_length': 0,
        'media_type': None,
        'media_width': None,
        'model': default_model,
        'model_code': None,
        'phase_type': 'Simulator',
        'series_code': None,
        'setting': None,
        'status_code': 0,
        'status_type': 'Simulator',
        'tape_color': '',
        'text_color': '',
    }

    status = {
        "errors": [],
        "path": device_specifier,
        "media_category": None,
        "media_length": 0,
        "media_type": None,
        "media_width": None,
        "model": "Unknown",
        "model_code": None,
        "phase_type": "Unknown",
        "series_code": None,
        "setting": None,
        "status_code": 0,
        "status_type": "Unknown",
        "tape_color": "",
        "text_color": "",
    }
    try:
        # If device_specifier is the default '?', try to auto-detect multiple printers
        if device_specifier == '?':
            now = time.time()
            # Refresh cache every 10 seconds
            if now - _last_scan_ts > 10:
                logger.debug('Auto-detecting printers: scanning local USB')
                found_list = []
                for i in range(0, 11):
                    dev = f"/dev/usb/lp{i}"
                    if not os.path.exists(dev):
                        continue
                    spec = f"file://{dev}"
                    try:
                        printer = get_printer(spec)
                        printer_state = get_status(printer)
                        printer_state.setdefault('path', spec)
                        found_list.append(printer_state)
                        logger.debug('Found compatible printer at %s -> %s', spec, printer_state.get('model'))
                    except Exception:
                        logger.debug('Device %s exists but is not a compatible printer or failed to query', dev, exc_info=True)

                _cached_printers = found_list
                _last_scan_ts = now
            # Prepare response: include list of printers and a top-level status for the first one (compatibility)
            # Ensure simulator printer is always present
            sim = SIMULATOR_PRINTER.copy()
            printers = list(_cached_printers)
            # append simulator if not present
            if not any(p.get('path') == 'simulator' for p in printers):
                printers.append(sim)
            if printers:
                # Use first detected printer as default top-level status for backward compatibility
                first = printers[0]
                for key, value in first.items():
                    status[key] = value
                return {
                    'printers': printers,
                    'selected': status.get('path'),
                    **status
                }
            else:
                status['status_type'] = 'Offline'
                status['errors'].append('No compatible printer detected')
                return {
                    'printers': [sim],
                    'selected': None,
                    **status
                }
        elif device_specifier.startswith('tcp://'):
            printer_state = get_network_status(device_specifier)
            printer_state['model'] = default_model
            for key, value in printer_state.items():
                status[key] = value
            printer = status.copy()
            sim = SIMULATOR_PRINTER.copy()
            status['printers'] = [printer, sim]
            status['selected'] = device_specifier
            return status
        else:
            printer = get_printer(device_specifier)
            printer_state = get_status(printer)
            for key, value in printer_state.items():
                status[key] = value
        # Always include simulator in returned printers list
        sim = SIMULATOR_PRINTER.copy()
        return {
            'printers': [sim],
            'selected': status.get('path'),
            **status
        }
    except Exception as e:
        logger.exception("Printer status error: %s", e)
        status['errors'] = [str(e)]
        return status
