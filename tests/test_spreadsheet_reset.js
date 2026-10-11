const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/main.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../app/labeldesigner/templates/labeldesigner.html'), 'utf8');
const defaultValue = template.match(/id="spreadsheet_data"[^>]*data-default='([^']+)'/)[1];
const input = { type: 'textarea', value: '[["edited"]]' };
const context = {
    $(selector) {
        return {
            removeData() {},
            each(callback) { callback.call(input); },
            attr() { return defaultValue; },
            // jQuery parses JSON data attributes and coerces arrays passed to .val().
            data() { return JSON.parse(defaultValue); },
            val(value) {
                if (arguments.length === 0) return input.value;
                input.value = Array.isArray(value) ? value.map(String).join(',') : String(value);
            },
        };
    },
};
vm.createContext(context);
for (const [start, end] of [
    ['function spreadsheetRows()', 'function updateSpreadsheetMode()'],
    ['function set_all_inputs_default(', 'window.onload ='],
]) {
    vm.runInContext(source.slice(source.indexOf(start), source.indexOf(end)), context);
}

context.set_all_inputs_default();
assert.equal(input.value, '[["edited"]]');
context.set_all_inputs_default(true);
assert.equal(input.value, defaultValue);
assert.equal(JSON.stringify(context.spreadsheetRows()), '[["",""]]');

// Recover settings saved by the old reset code.
input.value = ',';
assert.equal(JSON.stringify(context.spreadsheetRows()), '[["",""]]');
assert.equal(input.value, defaultValue);

input.value = '[["kept","value"]]';
assert.equal(JSON.stringify(context.spreadsheetRows()), '[["kept","value"]]');
console.log('Spreadsheet reset and recovery checks passed');
