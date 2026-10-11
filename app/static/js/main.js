// Global printer status object to be populated from the API
var printer_status = {
    'errors': [],
    'model': 'Unknown',
    'media_width': null,
    'media_length': 0,
    'phase_type': 'Unknown'
};

const DEFAULT_FONT = 'Droid Serif,Regular';

// Returns an array of font settings for each line of label text.
// Each new line inherits the font settings of the previous line.
var fontSettingsPerLine = [];

// Helper: parse a data:...;base64,<b64> data URL into mime and base64 parts
function parseDataUrl(dataUrl) {
    const comma = dataUrl.indexOf(',');
    if (comma === -1) return { mime: null, b64: null };
    const header = dataUrl.substring(5, comma); // skip leading 'data:'
    const mime = header.split(';')[0];
    const b64 = dataUrl.substring(comma + 1);
    return { mime, b64 };
}
// IndexedDB helpers for storing image base64 data (so we avoid large localStorage entries)
function _openImageDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open('brother_pt_images', 1);
        req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains('images')) db.createObjectStore('images');
        };
        req.onsuccess = (e) => resolve(e.target.result);
        req.onerror = (e) => reject(e.target.error);
    });
}

function _saveImageToDB(id, mime, b64) {
    return _openImageDB().then(db => new Promise((resolve, reject) => {
        const tx = db.transaction('images', 'readwrite');
        const store = tx.objectStore('images');
        // Use add() so we don't overwrite an existing entry with the same id.
        const req = store.add({ mime, b64 }, id);
        req.onsuccess = () => { db.close(); resolve(true); };
        req.onerror = (e) => {
            const err = e && e.target && e.target.error;
            // If the key already exists, add() will throw a ConstraintError —
            // in that case we resolve(false) to indicate we did not change the DB.
            if (err && err.name === 'ConstraintError') {
                db.close();
                resolve(false);
            } else {
                db.close();
                reject(err);
            }
        };
    })).catch(() => null);
}

function _getImageFromDB(id) {
    return _openImageDB().then(db => new Promise((resolve, reject) => {
        const tx = db.transaction('images', 'readonly');
        const store = tx.objectStore('images');
        const req = store.get(id);
        req.onsuccess = (e) => { db.close(); resolve(e.target.result || null); };
        req.onerror = (e) => { db.close(); reject(e.target.error); };
    })).catch(() => null);
}

function _deleteImagesFromDB(id = null) {
    return _openImageDB().then(db => new Promise((resolve, reject) => {
        const tx = db.transaction('images', 'readwrite');
        const store = tx.objectStore('images');
        const req = id === null ? store.clear() : store.delete(id);
        req.onsuccess = () => { db.close(); resolve(true); };
        req.onerror = (e) => { db.close(); reject(e.target.error); };
    })).catch(() => null);
}
function setFontSettingsPerLine() {
    var text = $('#label_text').val() || '';
    var lines = text.split(/\r?\n/);

    // Default font settings from the current UI controls
    var currentFont = {
        font: $('#font option:selected').val() || DEFAULT_FONT,
        size: $('#font_size').val(),
        auto_scale: $('#font_auto_scale').is(':checked'),
        inverted: $('#font_inverted').is(':checked'),
        align: $('input[name=font_align]:checked').val() || 'center',
        line_spacing: $('#line_spacing').val() || '100'
    };

    // Create lines in the <option> with id #lineSelect
    var lineSelect = $('#lineSelect');
    // Get currently selected line number
    var selectedLine = lineSelect.val();
    // Recreate options with possibly updated text
    lineSelect.empty();
    $.each(lines, function (index, line) {
        lineSelect.append($("<option></option>")
            .attr("value", index).text(lines[index] || '(line ' + (index + 1) + ' is empty)'));
    });
    lineSelect.val(selectedLine ?? 0);

    // Should we use the same font settings for all lines?
    const isSynced = $('#sync_font_settings').is(':checked');
    if (isSynced) {
        fontSettingsPerLine = lines.map(text => ({ ...currentFont, text }));
        return;
    }

    // We may need to initialize new lines with current font settings
    for (var i = fontSettingsPerLine.length; i < lines.length; i++) {
        if (i === selectedLine || selectedLine === null) {
            // Initialize with default
            fontSettingsPerLine.push(Object.assign({}, currentFont));
        } else {
            // Inherit from previous line
            fontSettingsPerLine.push(Object.assign({}, fontSettingsPerLine[i - 1]));
        }
    }

    // If we have more font settings, remove the excess
    while (fontSettingsPerLine.length > lines.length) {
        fontSettingsPerLine.pop();
    }

    // Update the current line's font settings
    if (fontSettingsPerLine[selectedLine]) {
        fontSettingsPerLine[selectedLine] = Object.assign({}, currentFont);
    }

    // Set text
    for (var i = 0; i < lines.length; i++) {
        fontSettingsPerLine[i]['text'] = lines[i];
    }
}

// Update font controls when a line is selected
$(document).ready(function () {
    $('#lineSelect').on('change', function () {
        var idx = parseInt($(this).val(), 10);
        if (isNaN(idx) || !fontSettingsPerLine || !fontSettingsPerLine[idx]) return;
        var fs = fontSettingsPerLine[idx];
        // Set font
        $('#font').val(fs.font || DEFAULT_FONT);
        // Set font size
        $('#font_size').val(fs.size);
        $('#font_auto_scale').prop('checked', !!fs.auto_scale);
        toggleFontSize();
        // Set alignment
        $('input[name=font_align]').prop('checked', false);
        $('input[name=font_align][value="' + fs.align + '"]').prop('checked', true).trigger("change");
        // Set line spacing
        $('#line_spacing').val(fs.line_spacing || '100');
        // Set font inversion
        $('#font_inverted').prop('checked', fs.inverted);
    });

    // When the user changes the caret/selection in the textarea, update #lineSelect and font controls
    $('#label_text').on('click keyup', function (e) {
        var textarea = this;
        var caret = textarea.selectionStart;
        var lines = textarea.value.split(/\r?\n/);
        var charCount = 0;
        var lineIdx = 0;
        for (var i = 0; i < lines.length; i++) {
            var nextCount = charCount + (lines[i] ? lines[i].length : 0) + 1; // +1 for newline
            if (caret < nextCount) {
                lineIdx = i;
                break;
            }
            charCount = nextCount;
        }
        $('#lineSelect').val(lineIdx).trigger('change');
    });
});

function toggleFontSize() {
    $('#font_size').prop('disabled', $('#font_auto_scale').is(':checked'));
}

function getModelFromSelectedPrinter(printerSelect) {
    if (printerSelect && printerSelect.value && window.available_printers) {
        const p = window.available_printers.find(p => p.path === printerSelect.value);
        if (p && p.model && p.model !== 'Unknown') return p.model;
    }
    if (printer_status && printer_status.model && printer_status.model !== 'Unknown') {
        return printer_status.model;
    }
    return null;
}

function updateCutOptions() {
    $('#cut_once, #half_cut, #chain_print').prop('disabled', $('#no_cut').is(':checked'));
}

function parseSpreadsheetPaste(text) {
    text = text.replace(/\r\n?/g, '\n');
    const rows = [[]];
    let cell = '';
    let quoted = false;
    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        if (quoted) {
            if (char === '"' && text[i + 1] === '"') { cell += '"'; i++; }
            else if (char === '"') quoted = false;
            else cell += char === '\n' ? ' ' : char;
        } else if (char === '"' && cell === '') {
            quoted = true;
        } else if (char === '\t' || char === '\n') {
            rows[rows.length - 1].push(cell);
            cell = '';
            if (char === '\n') rows.push([]);
        } else {
            cell += char;
        }
    }
    rows[rows.length - 1].push(cell);
    if (text.endsWith('\n') && !quoted) rows.pop();
    return rows;
}

function spreadsheetRows() {
    const input = $('#spreadsheet_data');
    try {
        return JSON.parse(input.val());
    } catch {
        input.val(input.attr('data-default'));
        return JSON.parse(input.val());
    }
}

function updateSpreadsheetMode() {
    const enabled = $('#spreadsheet_mode').is(':checked');
    $('#spreadsheetEditor').prop('hidden', !enabled);
    const count = $('#print_count');
    if (!enabled && count.prop('disabled')) count.val(1);
    count.prop('disabled', enabled);
    if (enabled) count.val(spreadsheetRows().length);
}

function renderSpreadsheet() {
    const rows = spreadsheetRows();
    const table = $('#spreadsheetTable').empty();
    const header = $('<tr>').append($('<th>').text('#'));
    rows[0].forEach((_, column) => header.append($('<th>').text('{{' + (column + 1) + '}}')));
    header.append($('<th>'));
    table.append($('<thead>').append(header));
    const body = $('<tbody>');
    rows.forEach((row, index) => {
        const tr = $('<tr>').append($('<th>').text(index + 1));
        row.forEach((cell, column) => {
            const input = $('<input type="text" class="form-control form-control-sm">')
                .val(cell).attr('aria-label', 'Row ' + (index + 1) + ', column ' + (column + 1));
            input.on('input', function () {
                row[column] = this.value;
                saveSpreadsheet(rows, false);
            });
            input.on('paste', function (event) {
                const text = event.originalEvent.clipboardData.getData('text/plain');
                if (!/[\t\r\n]/.test(text)) return;
                event.preventDefault();
                const pasted = parseSpreadsheetPaste(text);
                const width = Math.max(rows[0].length, column + Math.max(...pasted.map(row => row.length)));
                while (rows.length < index + pasted.length) rows.push([]);
                rows.forEach(row => { while (row.length < width) row.push(''); });
                pasted.forEach((row, r) => row.forEach((cell, c) => { rows[index + r][column + c] = cell; }));
                saveSpreadsheet(rows);
            });
            tr.append($('<td>').append(input));
        });
        tr.append($('<td>').append($('<button type="button" class="btn btn-outline-secondary btn-sm">')
            .text('×').attr('aria-label', 'Delete row ' + (index + 1)).prop('disabled', rows.length === 1)
            .on('click', () => { rows.splice(index, 1); saveSpreadsheet(rows); })));
        body.append(tr);
    });
    table.append(body);
    updateSpreadsheetMode();
}

function saveSpreadsheet(rows, render = true) {
    $('#spreadsheet_data').val(JSON.stringify(rows));
    if (render) renderSpreadsheet();
    $('#spreadsheet_data').trigger('change');
    preview();
}

function formData() {
    const data = {
        text: JSON.stringify(fontSettingsPerLine),
        spreadsheet_mode: $('#spreadsheet_mode').is(':checked') ? 1 : 0,
        spreadsheet_data: $('#spreadsheet_data').val(),
        label_size: $('#label_size').val(),
        label_length: $('#label_length_auto').is(':checked') ? 0 : parseFloat($('#label_length').val()) || 0,
        label_length_auto: $('#label_length_auto').is(':checked') ? 1 : 0,
        orientation: $('input[name=orientation]:checked').val(),
        margin_top: parseInt($('#margin_top').val(), 10) || 0,
        margin_bottom: parseInt($('#margin_bottom').val(), 10) || 0,
        margin_left: parseInt($('#margin_left').val(), 10) || 0,
        margin_right: parseInt($('#margin_right').val(), 10) || 0,
        print_type: $('input[name=print_type]:checked').val(),
        barcode_type: $('#barcode_type').val(),
        code_text: $('#code_text').val() || '',
        qrcode_size: parseInt($('#qrcode_size').data('manual-size') ?? $('#qrcode_size').val(), 10) || 0,
        qrcode_correction: $('#qrcode_correction option:selected').val(),
        code_fit: $('#code_fit').is(':checked') ? 1 : 0,
        image_bw_threshold: parseInt($('#image_bw_threshold').val(), 10) || 0,
        image_mode: $('input[name=image_mode]:checked').val(),
        image_fit: $('#image_fit').is(':checked') ? 1 : 0,
        image_crop: $('#image_crop').is(':checked') ? 1 : 0,
        print_count: parseInt($('#print_count').val(), 10) || 0,
        log_level: $('#log_level').val(),
        cut_once: $('#cut_once').is(':checked') ? 1 : 0,
        half_cut: $('#half_cut').is(':checked') ? 1 : 0,
        no_cut: $('#no_cut').is(':checked') ? 1 : 0,
        chain_print: $('#chain_print').is(':checked') ? 1 : 0,
        border_thickness: parseInt($('#border_thickness').val(), 10) || 0,
        border_roundness: parseInt($('#border_roundness').val(), 10) || 0,
        border_distance_x: parseInt($('#border_distance_x').val(), 10) || 0,
        border_distance_y: parseInt($('#border_distance_y').val(), 10) || 0,
        high_res: $('#high_res').is(':checked') ? 1 : 0,
        image_scaling_factor: parseInt($('#image_scaling_factor').val(), 10) || 0,
        image_rotation: parseInt($('#image_rotation').val(), 10) || 0,
        sync_font_settings: $('#sync_font_settings').is(':checked') ? 1 : 0
    }

    // Include selected printer if available
    const printerSelect = document.getElementById('printer');
    if (printerSelect && printerSelect.value) {
        data['printer'] = printerSelect.value;
        const modelFromPrinter = getModelFromSelectedPrinter(printerSelect);
        if (modelFromPrinter) {
            data['model'] = modelFromPrinter;
        }
    }

    return data;
}

function sizePreview(img) {
    const dpi = Number(img.dataset.dpi);
    const feed = Number(img.dataset.feedMargin) * dpi / default_dpi;
    const tapeWidth = Number(img.dataset.tapeWidth);
    const side = Math.max(0, (tapeWidth * dpi / 25.4 - img.naturalHeight) / 2);
    const fullWidth = img.naturalWidth + 2 * feed;
    const fullHeight = img.naturalHeight + 2 * side;
    const availableWidth = img.parentElement.parentElement.clientWidth - 4;
    const scale = Math.min(128 / fullHeight, availableWidth / fullWidth);
    img.parentElement.style.padding = `${side * scale}px ${feed * scale}px`;
    img.style.width = `${img.naturalWidth * scale}px`;
    img.style.height = `${img.naturalHeight * scale}px`;
    const length = (fullWidth / dpi * 25.4).toFixed(1);
    const item = $(img).closest('.preview-item');
    item.find('.label-width').text(length);
    item.find('.label-height').text(tapeWidth.toFixed(1));
    return length;
}

function updatePreview(data) {
    const container = document.getElementById('labelPreviews');
    const template = document.getElementById('labelPreviewTemplate').content.firstElementChild;
    const dimensions = {
        dpi: data.dpi,
        feedMargin: data.feed_margin,
        tapeWidth: data.tape_width,
    };
    container.replaceChildren(...data.images.map((image, index) => {
        const item = template.cloneNode(true);
        const img = item.querySelector('.preview-img');
        Object.assign(img.dataset, dimensions);
        img.onload = () => {
            const length = sizePreview(img);
            if (index === 0 && $('#label_length_auto').is(':checked')) $('#label_length').val(length);
        };
        img.src = 'data:image/png;base64,' + image;
        return item;
    }));
}

window.addEventListener('resize', function () {
    document.querySelectorAll('.preview-img').forEach(img => {
        if (img.naturalWidth) sizePreview(img);
    });
});

var lastPreviewData = null;
var pendingDropZoneData = null;
function gen_label(preview = true) {
    $('#label_length').prop('disabled', $('#label_length_auto').is(':checked'));
    // Check label against installed label in the printer
    updatePrinterStatus();

    // Update font settings for each line
    setFontSettingsPerLine();

    // Capture the request before asynchronous image processing starts.
    const data = formData();
    const type = preview ? 'preview' : 'printing';
    $('#groupLabelImage').toggle(data.print_type === 'image');

    // Process image upload
    if (data.print_type === 'image') {
        setStatus({ type: type, 'status': 'pending' });
        pendingDropZoneData = data;
        dropZoneMode = type;
        imageDropZone.processQueue();
        return;
    }

    // Get data and compare to the last preview generation, return if nothing
    // has changed
    const dataJson = JSON.stringify(data);
    if (preview && dataJson === lastPreviewData) {
        console.debug("No changes detected, not generating new preview.");
        return;
    }
    // Keep preview caching separate from printing. A print must not affect
    // whether a later preview is generated.
    if (preview) {
        lastPreviewData = dataJson;
    }

    // Update status box
    setStatus({ type: type, 'status': 'pending' });

    // Send printing request
    const url = preview ? url_for_preview : url_for_print;
    $.ajax({
        type: 'POST',
        url: url,
        data: data,
        success: function (data) {
            if (preview && dataJson !== lastPreviewData) return;
            const status = data?.success === false ? 'error' : 'success';
            setStatus({ type, status, warnings: data?.warnings });
            if (preview) {
                updateFormPreview(data);
            }
        },
        error: function (xhr, _status, error) {
            if (preview && dataJson !== lastPreviewData) return;
            message = xhr.responseJSON ? xhr.responseJSON.message : error;
            setStatus({ type: type, 'status': 'error', 'message': message });
        }
    });
}

function updateFormPreview(data) {
    updateAutoFontSizes(data.font_sizes);
    if (data.code_cell_size && $('#code_fit').is(':checked')) {
        $('#qrcode_size').val(data.code_cell_size);
    }
    updatePreview(data);
}

function updateAutoFontSizes(sizes) {
    if (!sizes) return;
    sizes.forEach(function (size, index) {
        if (fontSettingsPerLine[index]?.auto_scale) {
            fontSettingsPerLine[index].size = size;
        }
    });
    const selectedLine = parseInt($('#lineSelect').val(), 10);
    if (fontSettingsPerLine[selectedLine]?.auto_scale) {
        $('#font_size').val(fontSettingsPerLine[selectedLine].size);
    }
}

function print() {
    gen_label(false);
}

function preview() {
    toggleQrSettings();
    gen_label(true);
}

function setStatus(data) {
    let type = data.type || '';
    let status = data.status || '';
    let message = data.message || data.warnings?.join('<br />') || '';
    if (status === 'success' && message) status = 'warning';
    let errors = data?.errors || [];
    let extra_info = message ? ':<br />' + message : '';
    if (errors.length > 0) {
        extra_info += '<br />' + errors.join('<br />');
    }

    // Default: clear status
    let html = '';
    let iconClass = '';

    if (type === 'preview' || type === 'printing') {
        if (status === 'pending') {
            // Busy preparing preview or printing
            let action = type === 'printing' ? "Printing" : "Generating preview";
            html = `<div id="statusBox" class="alert alert-info" role="alert">
                        <i class="fas fa-hourglass-half"></i>
                        <span>${action}...</span>
                    </div>`;
            iconClass = 'float-end fas fa-hourglass-half text-muted';
        } else if (status === 'success') {
            // Success for preview or printing
            if (type === 'preview') {
                html = `<div id="statusBox" class="alert alert-info" role="alert">
                            <i class="fas fa-eye"></i>
                            <span>Preview generated successfully.</span>
                        </div>`;
                iconClass = 'float-end fas fa-check text-success';
            } else {
                html = `<div id="statusBox" class="alert alert-success" role="alert">
                            <i class="fas fa-check"></i>
                            <span>Printing was successful.</span>
                        </div>`;
                iconClass = 'float-end fas fa-print text-success';
            }
        } else if (status === 'warning' || status === 'error') {
            let action = type === 'preview' ? "Preview generation failed" : "Printing failed";
            const text = status === 'warning' ? message : action + extra_info;
            html = `<div id="statusBox" class="alert alert-warning" role="alert">
                        <i class="fas fa-exclamation-triangle"></i>
                        <span>${text}</span>
                    </div>`;
            iconClass = 'float-end fas fa-exclamation-triangle text-danger';
        }
    } else if (type === 'status') {
        if (status === 'error') {
            let action = "Error";
            html = `<div id="statusBox" class="alert alert-warning" role="alert">
                        <i class="fas fa-exclamation-triangle"></i>
                        <span>${action}${extra_info}</span>
                    </div>`;
            iconClass = 'float-end fas fa-exclamation-triangle text-danger';
        }
    }

    const elem = $(type === 'status' ? '#printerStatusPanel' : '#statusPanel');
    elem.html(html).toggle(html.length > 0);

    $('#statusIcon').removeClass().addClass(iconClass);
    $('#printButton, #dropdownPrintButton').prop('disabled', false);
}

let imageDropZone = null;
new Dropzone("#image-dropzone", {
    url: () => dropZoneMode === 'preview' ? url_for_preview : url_for_print,
    paramName: "image", // The name that will be used to transfer the file
    acceptedFiles: 'image/*,application/pdf',
    maxFiles: 1,
    addRemoveLinks: true,
    autoProcessQueue: false,
    thumbnailMethod: 'contain',
    init: function () {
        imageDropZone = this;

        this.on("addedfile", function () {
            if (this.files[1] != null) {
                this.removeFile(this.files[0]);
            }
        });
    },

    sending: function (file, xhr, data) {
        // append all parameters to the request
        $.each(pendingDropZoneData, function (key, value) {
            data.append(key, value);
        });
    },

    success: function (file, response) {
        // If preview or print was successfull update the previewpane or print status
        const status = response?.success === false ? 'error' : 'success';
        setStatus({ type: dropZoneMode, status, warnings: response?.warnings });
        if (dropZoneMode == 'preview') {
            updateFormPreview(response);
        }
        file.status = Dropzone.QUEUED;
    },

    accept: function (file, done) {
        // If a valid file was added, perform the preview
        done();
        preview();
    },

    removedfile: function (file) {
        file.previewElement.remove();
        preview();
        document.getElementById('labelPreviews').replaceChildren();
    }
});


function toggleQrSettings() {
    const cellSize = $('#qrcode_size');
    const autoFit = $('#code_fit').is(':checked');
    if (autoFit && cellSize.data('manual-size') === undefined) {
        cellSize.data('manual-size', cellSize.val());
    } else if (!autoFit && cellSize.data('manual-size') !== undefined) {
        cellSize.val(cellSize.data('manual-size')).removeData('manual-size');
    }
    cellSize.prop('disabled', autoFit);
    var barcodeType = document.getElementById('barcode_type');
    var qrCodeSize = document.getElementById('qrCodeSizeContainer');
    var qrCodeCorrection = document.getElementById('qrCodeCorrectionContainer');
    if (barcodeType) {
        qrCodeSize.style.display = (barcodeType.value === 'QR' || barcodeType.value === 'DATAMATRIX') ? '' : 'none';
        qrCodeCorrection.style.display = (barcodeType.value === 'QR') ? '' : 'none';
    }
}

function get_barcode_types() {
    // Populate barcode select menu from /api/barcodes
    return fetch(url_for_get_barcodes)
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('barcode_type');
            barcodes = data['barcodes'];
            if (select && Array.isArray(barcodes) && barcodes.length > 0) {
                barcodes.forEach((barcode, idx) => {
                    const opt = document.createElement('option');
                    opt.value = barcode;
                    opt.textContent = barcode === 'DATAMATRIX' ? 'Data Matrix' : barcode;
                    if (idx === 0) {
                        opt.selected = true;
                        // Set data-default="1" for first element
                        opt.setAttribute("data-default", "1");
                    }
                    select.appendChild(opt);
                });
                toggleQrSettings();
                select.addEventListener('change', toggleQrSettings);

                // Continue initializing page...
                init2();
            }
        });
}

function updatePrinterStatus() {
    const labelSizeX = document.getElementById('label-width');
    if (labelSizeX) {
        const labelDetails = [];
        labelDetails.push((printer_status.media_width ?? "???") + " mm");
        if (printer_status.media_type && printer_status.media_type !== 'Unknown') {
            labelDetails.push(printer_status.media_type);
        }
        if (printer_status.tape_color && printer_status.tape_color !== 'Unknown') {
            labelDetails.push(printer_status.tape_color + ' tape');
        }
        if (printer_status.text_color && printer_status.text_color !== 'Unknown') {
            labelDetails.push(printer_status.text_color + ' text');
        }
        labelSizeX.textContent = labelDetails.join(' · ');
    }

    // Check for label size mismatch compared to data-x property of select
    const labelSizeSelect = document.getElementById('label_size');
    const labelMismatch = document.getElementById('labelMismatch');
    const labelMismatchIcon = document.getElementById('labelMismatchIcon');
    if (labelSizeSelect && labelMismatch && labelMismatchIcon) {
        const selectedOption = labelSizeSelect.options[labelSizeSelect.selectedIndex];
        const dataX = selectedOption.getAttribute('data-x');
        const dataY = selectedOption.getAttribute('data-y');
        if (printer_status.media_width !== null && (printer_status.media_width !== parseInt(dataX) || printer_status.media_length !== parseInt(dataY))) {
            labelMismatch.style.display = '';
            labelMismatchIcon.style.display = '';
        } else {
            labelMismatch.style.display = 'none';
            labelMismatchIcon.style.display = 'none';
        }
    }

    if (printer_status.errors && printer_status.errors.length > 0) {
        setStatus({ type: 'status', status: 'error', errors: printer_status.errors });
    }
    else {
        // Clear printer errors
        setStatus({ type: 'status', status: 'success' });
    }
}

function selectDetectedLabelSize() {
    if (printer_status.media_width === null) return;

    let prefix = 'tze';
    if (printer_status.media_type === 'Heat-Shrink Tube (HS 2:1)') prefix = 'hse2-';
    if (printer_status.media_type === 'Heat-Shrink Tube (HS 3:1)') prefix = 'hse3-';

    const select = document.getElementById('label_size');
    const detected = Array.from(select.options).find(option =>
        option.value.startsWith(prefix) &&
        Number(option.getAttribute('data-x')) === Number(printer_status.media_width)
    );
    if (detected && select.value !== detected.value) {
        select.value = detected.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
    }
}

async function getPrinterStatus() {
    const response = await fetch(url_for_get_printer_status);
    const data = await response.json();
    // If server returned multiple printers, populate the select and pick the chosen one
    if (data && Array.isArray(data.printers)) {
        const select = document.getElementById('printer');
        if (select) {
            // remember current selection
            const cur = select.value;
            select.innerHTML = '';
            data.printers.forEach((p) => {
                const opt = document.createElement('option');
                opt.value = p.path || '';
                const displayPath = p.path? p.path.replace(/file:\/\//g, '' ) : '';
                opt.textContent = (p.model || 'Unknown') + ' @ ' + displayPath;
                select.appendChild(opt);
            });
            // choose previously selected or server selected or first
            if (cur && Array.from(select.options).some(o => o.value === cur)) {
                select.value = cur;
            } else if (data.selected) {
                select.value = data.selected;
            } else if (data.printers[0]) {
                select.value = data.printers[0].path;
            }
        }
        // Choose active printer status based on the select value
        const chosenPath = (document.getElementById('printer') || {}).value || (data.selected || (data.printers[0] && data.printers[0].path));
        let chosen = data.printers.find(p => p.path === chosenPath) || data.printers[0] || {};
        printer_status = chosen;
        // keep a list of available printers globally
        window.available_printers = data.printers;
    } else {
        printer_status = data;
    }
    selectDetectedLabelSize();
    updatePrinterStatus();
}

// --- Local Storage Save/Restore/Export/Import/Reset ---
const MAX_HISTORY = 40;
const LS_KEY = 'labeldesigner_settings_v1';
const LS_HISTORY_KEY = 'labeldesigner_settings_history_v1';
var current_restoring = false;
function saveAllSettingsToLocalStorage() {
    const data = {};
    // Save all input/select/textarea values
    $('input, select, textarea').each(function () {
        // Skip the value of #lineSelect
        if (this.id === 'lineSelect') return;
        // Prefer name over id for correct handling of radio buttons
        const key = this.type === 'radio' && this.name.length > 0 ? this.name : this.id;
        if (key.length == 0) return;
        if (this.type === 'checkbox') {
            data[key] = $(this).is(':checked');
        }
        else if (this.type === 'radio') {
            if ($(this).is(':checked') || $(this).parent().hasClass('active')) {
                data[key] = $(this).val();
            }
        } else {
            data[key] = $(this).val();
        }
    });
    // Save fontSettingsPerLine if available
    data.qrcode_size = $('#qrcode_size').data('manual-size') ?? $('#qrcode_size').val();
    if (window.fontSettingsPerLine) {
        data['fontSettingsPerLine'] = JSON.stringify(window.fontSettingsPerLine);
    }
    // Store image metadata and persist base64 into IndexedDB (avoid large localStorage entries)
    try {
        if (imageDropZone && imageDropZone.files && imageDropZone.files.length > 0) {
            const f = imageDropZone.files[0];
            const dataUrl = imageDropZone.files[0].dataURL;
            const parsed = parseDataUrl(dataUrl);
            if (parsed.b64) {
                const imageHash = generateHash(parsed.b64);
                _saveImageToDB(imageHash, parsed.mime, parsed.b64).catch(e => console.debug('Failed saving image to IndexedDB', e));
                data['image_ref'] = imageHash;
                data['image_mime'] = parsed.mime;
                data['image_name'] = f.name || 'image';
            }
        }
    } catch (e) {
        console.debug('No image to save to localStorage', e);
    }
    const this_settings = JSON.stringify(data);
    localStorage.setItem(LS_KEY, this_settings);

    // --- History logic ---
    let history = [];
    try {
        history = JSON.parse(localStorage.getItem(LS_HISTORY_KEY)) || [];
    } catch { history = []; }
    // Only push if different from last
    if (history.length === 0 || JSON.stringify(history[history.length - 1]) !== this_settings) {
        history.push(data);
        if (history.length > MAX_HISTORY) history = history.slice(history.length - MAX_HISTORY);
        localStorage.setItem(LS_HISTORY_KEY, JSON.stringify(history));
    }
    updateUndoButton();
}

function undoSettings() {
    let history = [];
    try {
        history = JSON.parse(localStorage.getItem(LS_HISTORY_KEY)) || [];
    } catch { history = []; }
    if (history.length < 2) return; // nothing to undo
    // Remove current state
    history.pop();
    const prev = history[history.length - 1];
    localStorage.setItem(LS_HISTORY_KEY, JSON.stringify(history));
    localStorage.setItem(LS_KEY, JSON.stringify(prev));
    restoreAllSettingsFromLocalStorage();
    updateUndoButton();
}

function updateUndoButton() {
    let history = [];
    try {
        history = JSON.parse(localStorage.getItem(LS_HISTORY_KEY)) || [];
    } catch { history = []; }
    $('#undoSettingsBtn').prop('disabled', history.length < 2);
}

function restoreAllSettingsFromLocalStorage() {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;

    let data;
    try { data = JSON.parse(raw); } catch { return; }
    lastPreviewData = null;
    current_restoring = true;
    data.spreadsheet_mode ??= false;
    data.label_length_auto ??= !Number(data.label_length);
    data.spreadsheet_data ??= $('#spreadsheet_data').attr('data-default');
    $('#print_count').prop('disabled', false);
    $('#qrcode_size').removeData('manual-size');
    $('input, select, textarea').each(function () {
        const key = this.type === 'radio' && this.name.length > 0 ? this.name : this.id;
        if (!(key in data)) return;
        if (this.type === 'checkbox') {
            $(this).prop('checked', !!data[key]);
        } else if (this.type === 'radio') {
            this.checked = $(this).val() == data[key];
            $(`label[for="${this.id}"]`).toggleClass('active', this.checked);
        } else {
            this.value = data[key];
        }
    });

    updateCutOptions();
    renderSpreadsheet();

    // Restore fontSettingsPerLine if available
    if (data['fontSettingsPerLine'] && window.fontSettingsPerLine) {
        try {
            window.fontSettingsPerLine = JSON.parse(data['fontSettingsPerLine']);
            $('#lineSelect').val(0);
            preview();
        } catch { }
    }

    // If image data is available (embedded) populate Dropzone, otherwise try IndexedDB by image_ref
    let imageRestorePromise = Promise.resolve();
    try {
        if (data.image_ref) {
            // try to retrieve from IndexedDB
            imageRestorePromise = _getImageFromDB(data.image_ref).then(record => {
                if (record && record.b64) {
                    const dataUrl = 'data:' + (record.mime || 'image/png') + ';base64,' + record.b64;
                    return fetch(dataUrl)
                        .then(res => res.blob())
                        .then(blob => {
                            const file = new File([blob], data.image_name || 'image', { type: record.mime || 'image/png' });
                            try { imageDropZone.removeAllFiles(true); } catch (e) { }
                            try { imageDropZone.addFile(file); } catch (e) { }
                        }).catch(e => {
                            console.debug('Failed to fetch blob from IndexedDB dataUrl', e);
                        });
                }
            }).catch(e => {
                console.debug('Failed to read image from IndexedDB', e);
            });
        }
    } catch (e) {
        console.debug('No image to restore from storage', e);
    }
    // Trigger preview after restore (after image restoration promise settles)
    imageRestorePromise.finally(() => {
        preview();
        current_restoring = false;
    });
}

// --- Repository UI functions ---------------------------------------------------------
function openRepositoryModal() {
    // show modal and load list
    const modalEl = document.getElementById('repoModal');
    if (!modalEl) return;
    const modal = new bootstrap.Modal(modalEl);
    modal.show();
    loadRepositoryList();
}

function loadRepositoryList() {
    const body = $('#repoListBody');
    body.html('<p class="text-muted">Loading...</p>');
    fetch(url_for_repo_list)
        .then(r => r.json())
        .then(data => {
            renderRepoList(data.files || []);
        })
        .catch(e => {
            body.html('<div class="text-danger">Failed to load repository list.</div>');
            console.error(e);
        });
}

function renderRepoList(files) {
    const body = $('#repoListBody');
    if (!files || files.length === 0) {
        body.html('<p class="text-muted">No labels in repository.</p>');
        return;
    }
    const table = $('<div class="list-group"></div>');
    files.forEach(f => {
        const item = $(
            ` <div class="list-group-item d-flex justify-content-between align-items-center">
                    <div class="d-flex gap-3 align-items-center">
                        <img class="repo-thumb" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEAAAAAQCAYAAAB49c9kAAAAE0lEQVR42mNgGAWjYBSMglEwCQAAP1gF8bQqT9kAAAAASUVORK5CYII=" />
                        <div>
                            <strong class="repo-name">${f.name}</strong><br/>
                            <small class="text-muted">${new Date(f.mtime * 1000).toLocaleString()} — ${f.size} bytes</small><br/>
                            <small class="text-muted">Label size: ${f.label_size ? f.label_size : 'unknown'}</small>
                        </div>
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-success repo-load" data-name="${f.name}">Load</button>
                        <button class="btn btn-sm btn-outline-primary repo-print" data-name="${f.name}">Print</button>
                        <button class="btn btn-sm btn-outline-danger repo-delete" data-name="${f.name}">Delete</button>
                    </div>
                </div>`
        );
        table.append(item);
        // fetch thumbnail asynchronously (do not override main preview)
        const img = item.find('.repo-thumb')[0];
        if (img) {
            repoFetchThumbnail(f.name, img);
        }
    });
    body.html(table);

    // Attach handlers
    $('.repo-load').on('click', function () {
        const name = $(this).data('name');
        repoLoad(name);
    });
    $('.repo-delete').on('click', function () {
        const name = $(this).data('name');
        if (!confirm('Delete ' + name + '?')) return;
        repoDelete(name);
    });
    $('.repo-print').on('click', function () {
        const name = $(this).data('name');
        repoPrint(name);
    });
}

function repoSaveCurrent() {
    const name = $('#repoSaveName').val();
    if (!name) {
        alert('Please provide a name to save.');
        return;
    }
    // Ensure settings are saved to localStorage
    try { saveAllSettingsToLocalStorage(); } catch (e) { }
    let payload = {};
    try { payload = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch (e) { payload = {}; }
    payload['name'] = name;

    // Save text properties
    try {
        if (!payload.hasOwnProperty('text')) {
            if (payload.hasOwnProperty('fontSettingsPerLine')) {
                payload['text'] = payload['fontSettingsPerLine'];
            } else if (window.fontSettingsPerLine) {
                payload['text'] = window.fontSettingsPerLine;
            } else if (typeof fontSettingsPerLine !== 'undefined') {
                payload['text'] = fontSettingsPerLine;
            } else {
                payload['text'] = '[]';
            }
        }
    } catch (e) { /* ignore */ }

    // If an image is present in Dropzone, encode it as base64 and include
    // it in the JSON payload so the server can accept pure JSON saves.
    function sendJsonPayload(p) {
        fetch(url_for_repo_save, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(p)
        }).then(r => r.json())
            .then(resp => {
                if (resp && (resp.success || resp.name)) {
                    try { $('#repoSaveName').val(''); } catch (e) {}
                    loadRepositoryList();
                } else {
                    alert('Save failed: ' + (resp && resp.message ? resp.message : 'Unknown'));
                }
            }).catch(e => {
                console.error(e);
                alert('Save failed');
            });
    }

    try {
        if (imageDropZone && imageDropZone.files && imageDropZone.files.length > 0) {
            const f = imageDropZone.files[0];
            // Use FileReader to read the file as data URL
            const reader = new FileReader();
            reader.onload = function (e) {
                try {
                    const dataUrl = e.target.result;
                    const parsed = parseDataUrl(dataUrl);
                    if (parsed.b64) {
                        payload['image_data'] = parsed.b64;
                        payload['image_mime'] = parsed.mime;
                        payload['image_name'] = f.name || 'image';
                    }
                } catch (err) {
                    console.warn('Failed to extract base64 from FileReader result', err);
                }
                sendJsonPayload(payload);
            };
            reader.onerror = function (err) {
                console.warn('Failed to read image for repo save', err);
                // fallback: send JSON without image
                sendJsonPayload(payload);
            };
            reader.readAsDataURL(f);
            return;
        }
    } catch (e) {
        console.warn('No image to attach to repo save', e);
    }

    // No image — send JSON payload directly
    sendJsonPayload(payload);
}

function repoLoad(name) {
    fetch(url_for_repo_load + '?name=' + encodeURIComponent(name))
        .then(r => {
            if (!r.ok) throw new Error('Load failed');
            return r.json();
        })
        .then(data => {
            try {
                data['fontSettingsPerLine'] = data['text'] || '[]';
                localStorage.setItem(LS_KEY, JSON.stringify(data));
            } catch (e) { }
            restoreAllSettingsFromLocalStorage();
            // If the repository entry includes an embedded image, populate Dropzone
            try {
                const img_b64 = data.image_data;
                const img_mime = data.image_mime || 'image/png';
                const img_name = data.image_name || data.image || 'image';
                if (img_b64) {
                    const dataUrl = 'data:' + img_mime + ';base64,' + img_b64;
                    fetch(dataUrl)
                        .then(res => res.blob())
                        .then(blob => {
                            const file = new File([blob], img_name, { type: img_mime });
                            try { imageDropZone.removeAllFiles(true); } catch (e) {}
                            // Use Dropzone's API to add the file so it is
                            // processed identically to a user upload.
                            try {
                                imageDropZone.addFile(file);
                            } catch (e) {
                                console.warn('Failed to populate Dropzone with repository image', e);
                            }
                            preview();
                        }).catch(e => console.warn('Failed to load image blob', e));
                }
            } catch (e) { console.warn(e); }
            // close modal
            const modalEl = document.getElementById('repoModal');
            bootstrap.Modal.getInstance(modalEl).hide();
        }).catch(e => {
            console.error(e);
            alert('Failed to load label');
        });
}

function repoDelete(name) {
    fetch(url_for_repo_delete + '?name=' + encodeURIComponent(name), { method: 'POST' })
        .then(r => r.json())
        .then(resp => {
            if (resp && resp.success) {
                loadRepositoryList();
            } else {
                alert('Delete failed: ' + (resp && resp.message ? resp.message : 'Unknown'));
            }
        }).catch(e => {
            console.error(e);
            alert('Delete failed');
        });
}

function repoPrint(name) {
    // Ask server to print a repository template by name
    const printerSelect = document.getElementById('printer');
    const body = new URLSearchParams();
    body.append('name', name);
    if (printerSelect && printerSelect.value) body.append('printer', printerSelect.value);
    const modelVal = getModelFromSelectedPrinter(printerSelect);
    if (modelVal) body.append('model', modelVal);

    fetch(url_for_repo_print, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' }, body: body })
        .then(r => r.json())
        .then(resp => {
            if (resp && resp.success) {
                setStatus({ type: 'printing', status: 'success', warnings: resp.warnings });
                console.log('Print job queued successfully');
            } else {
                const msg = resp && resp.message ? resp.message : 'Print failed';
                setStatus({ type: 'printing', status: 'error', message: msg });
                console.error(msg);
            }
        }).catch(e => {
            console.error(e);
            console.error('Print failed');
        });
}

function repoFetchThumbnail(name, imgEl) {
    fetch(url_for_repo_preview + '?name=' + encodeURIComponent(name) + '&thumbnail=1')
        .then(r => {
            if (!r.ok) throw new Error('Preview fetch failed');
            return r.json();
        })
        .then(data => {
            imgEl.src = 'data:image/png;base64,' + data.images[0];
        })
        .catch(e => {
            console.debug('Thumbnail fetch failed for', name, e);
            imgEl.style.opacity = 0.4;
        });
}

// Wire modal button on DOM ready
$(document).ready(function () {
    $('#openRepoBtn').off('click').on('click', openRepositoryModal);
    $('#repoSaveBtn').off('click').on('click', repoSaveCurrent);
});

function resetSettings() {
    if (confirm('Really reset all label settings to default?')) {
        localStorage.removeItem(LS_KEY);
        // Reset font settings
        window.fontSettingsPerLine = [];
        set_all_inputs_default(true);
        saveAllSettingsToLocalStorage();
        location.reload();
    }
}

function set_all_inputs_default(force = false) {
    $('#qrcode_size').removeData('manual-size');
    // Iterate over those <input> that have a data-default propery and set the value if empty
    $('input[data-default], select[data-default], textarea[data-default]').each(function () {
        if (this.type === 'checkbox' || this.type === 'radio') {
            $(this).prop('checked', $(this).data('default') == 1 || $(this).data('default') == true);
        }
        else if (this.type === 'select-one' || this.type === 'number') {
            $(this).val($(this).data('default'));

        }
        else if (!$(this).val() || force) {
            $(this).val($(this).attr('data-default'));
        }
    });
}

window.onload = async function () {
    // Get supported barcodes
    await get_barcode_types();

    // Detect the installed tape once after restoring the page settings.
    await getPrinterStatus();
}

function init2() {
    // Restore settings on load
    set_all_inputs_default();
    restoreAllSettingsFromLocalStorage();
    toggleFontSize();
    renderSpreadsheet();
    $('#spreadsheet_mode').on('change', function () { updateSpreadsheetMode(); preview(); });
    $('#spreadsheetAddRow').on('click', function () {
        const rows = spreadsheetRows();
        rows.push(rows[0].map(() => ''));
        saveSpreadsheet(rows);
    });
    $('#spreadsheetAddColumn').on('click', function () {
        const rows = spreadsheetRows();
        rows.forEach(row => row.push(''));
        saveSpreadsheet(rows);
    });
    $('#spreadsheetRemoveColumn').on('click', function () {
        const rows = spreadsheetRows();
        if (rows[0].length > 1) { rows.forEach(row => row.pop()); saveSpreadsheet(rows); }
    });
    updateCutOptions();
    $('#no_cut').on('change', updateCutOptions);

    // Save on change
    $(document).on('change input', 'input, select, textarea', function () {
        // Spreadsheet cells save through #spreadsheet_data; line selection is not a setting.
        if ($(this).is('#lineSelect, #spreadsheetTable input')) return;
        setFontSettingsPerLine();
        saveAllSettingsToLocalStorage();
    });

    // Add event handler to update active class on manual click for btn-check radios
    $('input.btn-check[type="radio"]').off('change.btnCheckActive').on('change.btnCheckActive', function () {
        const name = $(this).attr('name');
        $(`input[name="${name}"]`).each(function () {
            $(`label[for="${this.id}"]`).removeClass('active');
        });
        $(`label[for="${this.id}"]`).addClass('active');
    });
    // Reset button
    $('#resetSettings').on('click', resetSettings);

    // Undo button
    $('#undoSettingsBtn').on('click', undoSettings);
    updateUndoButton();

    // Trigger initial preview
    preview();
};

// Simple hash function to generate a hash from a string
// Uses a 64-bit FNV-1a style hash implemented with BigInt to reduce collision probability
const generateHash = (string) => {
    const FNV_OFFSET_BASIS = 14695981039346656037n; // 64-bit offset basis
    const FNV_PRIME = 1099511628211n;               // 64-bit FNV prime
    let hash = FNV_OFFSET_BASIS;

    for (let i = 0; i < string.length; i++) {
        hash ^= BigInt(string.charCodeAt(i));
        hash *= FNV_PRIME;
        // Constrain to 64 bits
        hash &= (1n << 64n) - 1n;
    }
    // Return as base36 string
    return hash.toString(36);
};
