import assert from "node:assert/strict";
import { test } from "node:test";

import { duration, lead, plural, since } from "./format.ts";

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

test("a card shows its first line; the rest folds away", () => {
  assert.deepEqual(lead("FIXED in 1m 45s: payment errors 40.7% -> 0.0%\nWhy: flag change\nDid: put it back"),
    { head: "FIXED in 1m 45s: payment errors 40.7% -> 0.0%", rest: "Why: flag change\nDid: put it back" });
  // short single line: nothing to fold
  assert.deepEqual(lead("payment rolled back to 3.1.0."), { head: "payment rolled back to 3.1.0.", rest: "" });
  // one long paragraph: first sentence, and 40.7 is not a sentence end
  const long = `Errors went 40.7% to 0. ${"The flag flip explains it and nothing else changed. ".repeat(4)}`;
  assert.equal(lead(long).head, "Errors went 40.7% to 0.");
  assert.ok(lead(long).rest.startsWith("The flag flip"));
});
