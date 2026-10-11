"""Helpers for sending raster data and reading printer status."""

import logging
import time

from brother_pt.backends import backend_factory, guess_backend
from brother_pt.backends.generic import BrotherQLBackendGeneric
from brother_pt.reader import interpret_response

logger = logging.getLogger(__name__)


def send(instructions, printer_identifier=None, backend_identifier=None, blocking=True):
    """Send raster instructions to a printer."""
    status = {
        'instructions_sent': True,
        'outcome': 'unknown',
        'printer_state': None,
        'did_print': False,
        'ready_for_next_job': False,
    }

    if backend_identifier:
        selected_backend = backend_identifier
    else:
        try:
            selected_backend = guess_backend(printer_identifier)
        except ValueError:
            logger.info("No backend stated. Selecting the default linux_kernel backend.")
            selected_backend = 'linux_kernel'

    printer_class = backend_factory(selected_backend)['backend_class']
    printer = printer_class(printer_identifier)

    start = time.time()
    logger.info('Sending instructions to the printer. Total: %d bytes.', len(instructions))
    printer.write(instructions)
    status['outcome'] = 'sent'

    if not blocking or selected_backend == 'network':
        return status

    while time.time() - start < 10:
        data = printer.read()
        if not data:
            time.sleep(0.005)
            continue
        try:
            result = interpret_response(data)
        except (NameError, ValueError):
            logger.error("TIME %.3f - Couldn't understand response: %s",
                         time.time() - start, data)
            continue
        status['printer_state'] = result
        logger.debug('TIME %.3f - result: %s', time.time() - start, result)
        if result['errors']:
            logger.error('Errors occurred: %s', result['errors'])
            status['outcome'] = 'error'
            break
        if result['status_type'] == 'Printing completed':
            status['did_print'] = True
            status['outcome'] = 'printed'
        if result['status_type'] == 'Phase change' and result['phase_type'] == 'Waiting to receive':
            status['ready_for_next_job'] = True
        if status['did_print'] and status['ready_for_next_job']:
            break

    if not status['did_print']:
        logger.warning("'printing completed' status not received.")
    if not status['ready_for_next_job']:
        logger.warning("'waiting to receive' status not received.")
    if status['did_print'] and status['ready_for_next_job']:
        logger.info("Printing was successful. Waiting for the next job.")

    return status


def get_status(
    printer: BrotherQLBackendGeneric,
    receive_only=False,
    target_status=None,
):
    """Read and parse the current printer status."""
    if not receive_only:
        printer.write(b"\x1b\x69\x53")
    result = interpret_response(printer.read())
    if target_status is not None and result['status_code'] != target_status:
        raise ValueError(
            f"Printer reported 0x{result['status_code']:02x} status "
            f"instead of 0x{target_status:02x}"
        )
    return result
