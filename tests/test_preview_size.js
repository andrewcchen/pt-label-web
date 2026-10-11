const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(`${__dirname}/../app/static/js/main.js`, 'utf8');
const sizes = {};
const context = {
    default_dpi: 180,
    $(selector) {
        if (typeof selector === 'object') return { closest() { return { find(selector) { return context.$(selector); } }; } };
        return {
            text(value) { sizes[selector] = value; },
            val(value) { sizes[selector] = value; },
        };
    },
};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function sizePreview('), source.indexOf('function updatePreview(')), context);

for (const scale of [1, 2]) {
    const dpi = 180 * scale;
    const img = {
        dataset: { dpi, feedMargin: 14, tapeWidth: 12 },
        naturalWidth: Math.round(50 * dpi / 25.4) - 28 * scale,
        naturalHeight: 70 * scale,
        style: {},
        parentElement: { style: {}, parentElement: { clientWidth: 400 } },
    };
    sizes['#label_length'] = '75';
    assert.equal(context.sizePreview(img), '50.0');
    assert.equal(sizes['.label-width'], '50.0');
    assert.equal(sizes['.label-height'], '12.0');
    assert.equal(sizes['#label_length'], '75');
    const padding = img.parentElement.style.padding.split(' ').map(parseFloat);
    assert.ok(padding[0] > 0 && padding[1] > 0);
    assert.ok(parseFloat(img.style.width) + 2 * padding[1] <= 396);
    assert.ok(parseFloat(img.style.height) + 2 * padding[0] <= 128);
}


const img = {
    dataset: { dpi: 180, feedMargin: 14 }, naturalWidth: 40,
    style: {}, parentElement: { style: {}, parentElement: { clientWidth: 400 } },
};
for (const [width, height] of [[3.5, 24], [5.8, 28], [5.2, 20]]) {
    img.dataset.tapeWidth = width;
    img.naturalHeight = height;
    context.sizePreview(img);
    assert.equal(sizes['.label-height'], width.toFixed(1));
    const scale = Math.min(128 / (width * 180 / 25.4), 396 / 68);
    const side = (width * 180 / 25.4 - height) / 2;
    assert.ok(Math.abs(parseFloat(img.parentElement.style.padding) - side * scale) < 1e-9);
}
console.log('Preview physical size and margins checks passed');
