import assert from "node:assert/strict";
import { test } from "node:test";

import { duration, plural, since } from "./format.ts";

test("durations never print 60 seconds", () => {
  assert.equal(duration(119.6), "1m 59s");
  assert.equal(since(219.9, 100), "+1m 59s");
  assert.equal(duration(162), "2m 42s");
  assert.equal(duration(4.25), "4.3 s");
  assert.equal(duration(3725), "1h 2m");
});

test("plural picks the right word", () => {
  assert.equal(plural(1, "event"), "1 event");
  assert.equal(plural(0, "event"), "0 events");
  assert.equal(plural(41, "event"), "41 events");
  assert.equal(plural(2, "match", "matches"), "2 matches");
});
