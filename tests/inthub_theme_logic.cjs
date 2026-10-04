// Theme controller tests without a browser or visual validation.
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../apps/inthub_web/static/theme.js'), 'utf8');
function setup(saved, darkSystem = false, blockedStorage = false) {
  const attributes = new Map();
  const button = {dataset: {}, innerHTML: '', setAttribute(key, value) {attributes.set(key, value);}};
  const mark = {src: '', setAttribute(_, value) {this.src = value;}};
  const settings = ['system', 'light', 'dark'].map(mode => ({
    dataset: {themeSetting: mode}, textContent: mode, selected: false, pressed: '',
    setAttribute(_, value) {this.pressed = value;},
    classList: {toggle(_, value) {settings.find(x => x.dataset.themeSetting === mode).selected = value;}},
  }));
  const media = {matches: darkSystem, addEventListener(_, fn) {this.changed = fn;}};
  const handlers = new Map();
  const document = {
    documentElement: {dataset: {}, style: {}},
    querySelector() {return null;},
    querySelectorAll(selector) {return selector === '[data-theme-switch]' ? [button] : selector === '[data-theme-setting]' ? settings : [mark];},
    addEventListener(event, fn) {handlers.set(event, fn);},
  };
  const cx = {
    document,
    localStorage: {
      getItem() {if (blockedStorage) throw new Error('blocked'); return saved;},
      setItem(key, value) {if (blockedStorage) throw new Error('blocked'); saved = value;},
    },
    window: {
      matchMedia() {return media;},
      addEventListener(event, fn) {handlers.set(event, fn);},
      IntHubI18n: {t(key) {return `localized:${key}`;}},
    },
  };
  vm.runInNewContext(source, cx);
  handlers.get('DOMContentLoaded')();
  return {cx, document, media, handlers, button, mark, attributes, settings};
}
const dark = setup('dark');
assert.equal(dark.document.documentElement.dataset.theme, 'dark');
assert.ok(dark.mark.src.endsWith('#dark'));
assert.equal(dark.attributes.get('aria-label'), 'localized:Theme: Dark');
assert.equal(dark.settings[2].pressed, 'true');
assert.equal(dark.settings[2].textContent, 'dark');
dark.cx.window.IntHubTheme.setPreference('light');
assert.equal(dark.document.documentElement.dataset.theme, 'light');
assert.ok(!dark.mark.src.includes('#dark'));
dark.media.matches = true;
dark.media.changed();
assert.equal(dark.document.documentElement.dataset.theme, 'light');
dark.cx.window.IntHubTheme.setPreference('system');
assert.equal(dark.document.documentElement.dataset.theme, 'dark');
dark.media.matches = false;
dark.media.changed();
assert.equal(dark.document.documentElement.dataset.theme, 'light');
dark.handlers.get('click')({target: {closest(selector) {return selector === '[data-theme-switch]';}}});
assert.equal(dark.cx.window.IntHubTheme.preference, 'light');
dark.handlers.get('click')({target: {closest(selector) {return selector === '[data-theme-switch]';}}});
assert.equal(dark.cx.window.IntHubTheme.preference, 'dark');
dark.handlers.get('click')({target: {closest(selector) {return selector === '[data-theme-setting]' ? dark.settings[1] : null;}}});
assert.equal(dark.cx.window.IntHubTheme.preference, 'light');
assert.equal(dark.settings[1].pressed, 'true');
assert.equal(dark.settings[2].pressed, 'false');
dark.cx.window.IntHubTheme.setPreference('invalid');
assert.equal(dark.cx.window.IntHubTheme.preference, 'light');
const blocked = setup(null, true, true);
assert.equal(blocked.document.documentElement.dataset.theme, 'dark');
blocked.cx.window.IntHubTheme.setPreference('light');
assert.equal(blocked.document.documentElement.dataset.theme, 'light');
console.log('Saved/system/manual themes, localized controls and blocked-storage fallback passed.');
