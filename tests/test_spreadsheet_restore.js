const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/main.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../app/labeldesigner/templates/labeldesigner.html'), 'utf8');
const defaultValue = template.match(/id="spreadsheet_data"[^>]*data-default='([^']+)'/)[1];
const mode = { id: 'spreadsheet_mode', type: 'checkbox', checked: true };
const sheet = { id: 'spreadsheet_data', type: 'textarea', value: '[["A"],["B"]]' };
const count = { id: 'print_count', type: 'number', value: '2', disabled: true, data: {} };
const autoLength = { id: 'label_length_auto', type: 'checkbox', checked: true };
let saved;
const context = {
    LS_KEY: 'settings', window: {},
    localStorage: { getItem: () => JSON.stringify(saved) },
    updateCutOptions() {}, preview() {},
    $(selector) {
        const el = typeof selector === 'object' ? selector : ({ '#spreadsheet_mode': mode, '#spreadsheet_data': sheet, '#print_count': count }[selector] || { data: {} });
        return {
            each(callback) { [mode, sheet, count, autoLength].forEach(input => callback.call(input)); },
            attr() { return defaultValue; },
            removeData(key) { delete el.data[key]; return this; },
            is() { return el.checked; },
            prop(key, value) { if (arguments.length === 1) return el[key]; el[key] = value; return this; },
            val(value) { if (!arguments.length) return el.value; el.value = String(value); return this; },
            data(key, value) { if (arguments.length === 1) return el.data[key]; el.data[key] = value; return this; },
        };
    },
};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function spreadsheetRows()'), source.indexOf('function renderSpreadsheet()')), context);
context.renderSpreadsheet = () => context.updateSpreadsheetMode();
vm.runInContext(source.slice(source.indexOf('function restoreAllSettingsFromLocalStorage()'), source.indexOf('// --- Repository UI functions')), context);

// Loading a label saved before spreadsheet mode existed clears the previous sheet.
saved = { print_count: '1' };
context.restoreAllSettingsFromLocalStorage();
assert.equal(mode.checked, false);
assert.equal(sheet.value, defaultValue);
assert.equal(count.disabled, false);
assert.equal(count.value, '1');
assert.equal(autoLength.checked, true);

saved = { label_length: 50 };
context.restoreAllSettingsFromLocalStorage();
assert.equal(autoLength.checked, false);

saved = { label_length: 50, label_length_auto: true };
context.restoreAllSettingsFromLocalStorage();
assert.equal(autoLength.checked, true);

// Mode and rows restore together, and the row count overrides a saved count.
saved = { spreadsheet_mode: true, spreadsheet_data: '[["first"],["second"]]', print_count: '99' };
context.restoreAllSettingsFromLocalStorage();
assert.equal(mode.checked, true);
assert.equal(sheet.value, saved.spreadsheet_data);
assert.equal(count.disabled, true);
assert.equal(count.value, '2');

// Loading/undoing to a manual label must preserve its saved count.
saved = { spreadsheet_mode: false, spreadsheet_data: defaultValue, print_count: '7' };
context.restoreAllSettingsFromLocalStorage();
assert.equal(mode.checked, false);
assert.equal(count.disabled, false);
assert.equal(count.value, '7');

// Disabling spreadsheet mode resets the count to one.
mode.checked = true;
context.updateSpreadsheetMode();
assert.equal(count.value, '1');
mode.checked = false;
context.updateSpreadsheetMode();
assert.equal(count.value, '1');
console.log('Spreadsheet restore and mode toggle checks passed');
