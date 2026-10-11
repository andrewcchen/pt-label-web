const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(`${__dirname}/../app/static/js/main.js`, 'utf8');
const warning = 'Content was cropped to fit the fixed label length.';
let html;
let cellSize;
const context = {
    preview: true, type: 'preview', dropZoneMode: 'preview',
    dataJson: 'current', lastPreviewData: 'current',
    updatePreview() {}, updateAutoFontSizes() {},
    Dropzone: { QUEUED: 'queued' },
    $(selector) {
        return {
            html(value) { if (selector === '#statusPanel') html = value; return this; },
            toggle() {}, prop() {},
            is() { return true; },
            val(value) { if (selector === '#qrcode_size') cellSize = value; },
            removeClass() { return this; }, addClass() {},
        };
    },
};
vm.createContext(context);
const formPreviewStart = source.indexOf('function updateFormPreview(');
vm.runInContext(source.slice(formPreviewStart, source.indexOf('function updateAutoFontSizes(', formPreviewStart)), context);
const statusStart = source.indexOf('function setStatus(');
vm.runInContext(source.slice(statusStart, source.indexOf('\n}', statusStart) + 2), context);

function callback(start, end) {
    const offset = source.indexOf(start);
    const code = source.slice(offset + 'success: '.length, source.indexOf(end, offset)).trim().replace(/,$/, '');
    return vm.runInContext(`(${code})`, context);
}

const ajaxSuccess = callback('success: function (data)', 'error: function (xhr, _status, error)');
const uploadSuccess = callback('success: function (file, response)', 'accept: function (file, done)');
ajaxSuccess({ warnings: [warning], code_cell_size: 3 });
assert.ok(html.includes(warning));
assert.equal(cellSize, 3);
const currentStatus = html;
context.dataJson = 'stale';
ajaxSuccess({ success: true });
assert.equal(html, currentStatus);
context.dataJson = 'current';
uploadSuccess({}, { warnings: [warning], code_cell_size: 4 });
assert.equal(cellSize, 4);
assert.ok(html.includes(warning));

context.preview = false;
context.type = context.dropZoneMode = 'printing';
ajaxSuccess({ success: true, warnings: [warning] });
assert.ok(html.includes(warning));
uploadSuccess({}, { success: true, warnings: [warning] });
assert.ok(html.includes(warning));
context.setStatus({ type: 'printing', status: 'success', warnings: [warning] });
assert.ok(html.includes(warning));
console.log('Crop warning text appears for previews and prints');
