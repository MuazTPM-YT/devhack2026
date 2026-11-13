import assert from "node:assert/strict";
import { test } from "node:test";

import { DEFAULT_PREFS, readPrefs, togglePref } from "./prefs.ts";

test("panel prefs: bad or missing storage means every panel open", () => {
  assert.deepEqual(readPrefs(null), DEFAULT_PREFS);
  assert.deepEqual(readPrefs("{not json"), DEFAULT_PREFS);
  assert.deepEqual(readPrefs("[1,2]"), DEFAULT_PREFS);
  assert.deepEqual(readPrefs('"closed"'), DEFAULT_PREFS);
  // only a real true folds a panel; unknown keys are dropped
  assert.deepEqual(readPrefs('{"nav":true,"list":"yes","other":true}'), { nav: true, list: false, sheet: false });
});

test("toggling one panel leaves the others alone", () => {
  const once = togglePref(DEFAULT_PREFS, "sheet");
  assert.deepEqual(once, { nav: false, list: false, sheet: true });
  assert.deepEqual(togglePref(once, "sheet"), DEFAULT_PREFS);
  assert.deepEqual(DEFAULT_PREFS, { nav: false, list: false, sheet: false });
});
