// Theme controller tests without a browser or visual validation.
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '../apps/inthub_web/static/theme.js'), 'utf8');
function setup(saved, darkSystem = false, blockedStorage = false, search = '') {
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
    URLSearchParams,
    document,
    localStorage: {
      getItem() {if (blockedStorage) throw new Error('blocked'); return saved;},
      setItem(key, value) {if (blockedStorage) throw new Error('blocked'); saved = value;},
    },
    window: {
      location: {search},
      matchMedia() {return media;},
      addEventListener(event, fn) {handlers.set(event, fn);},
      IntHubI18n: {t(key) {return `localized:${key}`;}},
    },
  };
  vm.runInNewContext(source, cx);
  handlers.get('DOMContentLoaded')();
  return {cx, document, media, handlers, button, mark, attributes, settings, saved: () => saved};
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
const incoming = setup('light', false, false, '?theme=dark');
assert.equal(incoming.document.documentElement.dataset.theme, 'dark');
assert.equal(incoming.saved(), 'dark');
assert.equal(setup(incoming.saved()).document.documentElement.dataset.theme, 'dark');
for (const search of ['?theme=unknown', '?theme=system', '?theme=dark&theme=light']) {
  assert.equal(setup('light', false, false, search).document.documentElement.dataset.theme, 'light');
}
assert.equal(setup(null, false, true, '?theme=dark').document.documentElement.dataset.theme, 'dark');

const languageSource = fs.readFileSync(path.join(__dirname, '../apps/inthub_web/static/i18n.js'), 'utf8');
function languageBoot(search, saved = 'zh-CN', blockedStorage = false) {
  const cx = {URLSearchParams, navigator: {language: 'zh-CN'}, window: {location: {search}},
    localStorage: {getItem() {if (blockedStorage) throw Error('blocked'); return saved;}, setItem(_, value) {if (blockedStorage) throw Error('blocked'); saved = value;}},
  };
  vm.runInNewContext(languageSource, cx);
  return {language: cx.window.IntHubI18n.language, saved};
}
const english = languageBoot('?lang=en');
assert.equal(english.language, 'en'); assert.equal(english.saved, 'en');
assert.equal(languageBoot('', english.saved).language, 'en');
assert.equal(languageBoot('?lang=zh', 'en').language, 'zh-CN');
for (const search of ['?lang=unknown', '?lang=zh-CN', '?lang=en&lang=zh']) {
  assert.equal(languageBoot(search).language, 'zh-CN');
}
assert.equal(languageBoot('?lang=en', undefined, true).language, 'en');
console.log('Saved/system/manual themes, localized controls and blocked-storage fallback passed.');
