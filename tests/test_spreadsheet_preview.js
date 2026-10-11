const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(`${__dirname}/../app/static/js/main.js`, 'utf8');
function item() {
    const img = { dataset: {} };
    return { img, cloneNode: item, querySelector: () => img };
}
const container = {
    replaceChildren(...children) { this.children = children; },
};
const sized = [];
let autoLength = false;
let length = '75';
const context = {
    document: { getElementById: id => id === 'labelPreviews' ? container : { content: { firstElementChild: item() } } },
    sizePreview: img => { sized.push(img); return img.src.endsWith('second') ? '60.0' : '50.0'; },
    $: () => ({ is: () => autoLength, val: value => { length = value; } }),
};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function updatePreview('), source.indexOf("window.addEventListener('resize'")), context);

context.updatePreview({ images: ['first', 'second', 'third'], dpi: 360, tape_width: 24, feed_margin: 14 });
assert.equal(container.children.length, 3);
container.children.forEach(({ img }, index) => {
    assert.equal(img.dataset.dpi, 360);
    assert.equal(img.dataset.tapeWidth, 24);
    assert.equal(img.src, `data:image/png;base64,${['first', 'second', 'third'][index]}`);
    img.onload();
});
assert.equal(sized.length, 3);
assert.equal(length, '75');
autoLength = true;
context.updatePreview({ images: ['single'], dpi: 180, tape_width: 12, feed_margin: 14 });
assert.equal(container.children.length, 1);
container.children[0].img.onload();
assert.equal(length, '50.0');
assert.equal(container.children[0].img.src, 'data:image/png;base64,single');
assert.equal(container.children[0].img.dataset.dpi, 180);
assert.equal(container.children[0].img.dataset.tapeWidth, 12);
assert.equal(container.children[0].img.dataset.feedMargin, 14);
context.updatePreview({ images: ['first', 'second'], dpi: 180, tape_width: 12, feed_margin: 14 });
container.children[0].img.onload();
container.children[1].img.onload();
assert.equal(length, '50.0');
autoLength = false;
length = '75';
container.children[0].img.onload();
assert.equal(length, '75');
console.log('All spreadsheet previews render and reset to a single label');
