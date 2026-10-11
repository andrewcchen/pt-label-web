const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/js/main.js'), 'utf8');
const cells = [];
let saved;
const context = {
    spreadsheetRows: () => [['kept', '']],
    saveSpreadsheet: rows => { saved = JSON.parse(JSON.stringify(rows)); },
    updateSpreadsheetMode() {},
    $(selector) {
        const el = {
            handlers: {}, empty() { return this; }, append() { return this; },
            text() { return this; }, val() { return this; }, attr() { return this; }, prop() { return this; },
            on(event, handler) { this.handlers[event] = handler; return this; },
        };
        if (selector.startsWith('<input')) cells.push(el);
        return el;
    },
};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function parseSpreadsheetPaste('), source.indexOf('function spreadsheetRows()')), context);

for (const [text, expected] of [
    ['A\tB\r\nC\tD\r\n', [['A', 'B'], ['C', 'D']]],
    ['"two\nlines"\tX\n', [['two lines', 'X']]],
    ['"tab\there"\t"say ""hi"""\n', [['tab\there', 'say "hi"']]],
    ['"two\r\nlines"\tX\r\n', [['two lines', 'X']]],
    ['\t\n\t\n', [['', ''], ['', '']]],
    ['A\t', [['A', '']]],
    ['A\n\n', [['A'], ['']]],
    ['plain "quote"\tB', [['plain "quote"', 'B']]],
    ['""\t""', [['', '']]],
    ['', [['']]],
]) {
    assert.deepEqual(JSON.parse(JSON.stringify(context.parseSpreadsheetPaste(text))), expected);
}

vm.runInContext(source.slice(source.indexOf('function renderSpreadsheet()'), source.indexOf('function saveSpreadsheet(')), context);
context.renderSpreadsheet();
let prevented = false;
cells[1].handlers.paste({
    originalEvent: { clipboardData: { getData: () => '"two\nlines"\t"say ""hi"""\n' } },
    preventDefault() { prevented = true; },
});
assert(prevented);
assert.deepEqual(saved, [['kept', 'two lines', 'say "hi"']]);
console.log('Spreadsheet quoted paste checks passed');
