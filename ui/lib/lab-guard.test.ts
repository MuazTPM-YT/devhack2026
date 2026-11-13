import assert from "node:assert/strict";
import { test } from "node:test";

import { Attempts, refusal, same, sessionValue } from "./lab-guard.ts";

const TOKEN = "judge-token-0123456789";
const cookie = sessionValue(TOKEN);

test("this machine's own browser uses the lab without a passcode", () => {
  assert.equal(refusal({ host: "localhost:3000", origin: null, cookie: null }, TOKEN), null);
  assert.equal(refusal({ host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000", cookie: null }, TOKEN), null);
});

test("another site's page cannot borrow the server's token", () => {
  // plain cross-site POST
  assert.equal(refusal({ host: "localhost:3000", origin: "https://evil.example", cookie: null }, TOKEN)?.status, 403);
  // DNS rebinding: the attacker's name resolves to 127.0.0.1, so Host is theirs and the request looks same-origin
  assert.equal(refusal({ host: "evil.example:3000", origin: "http://evil.example:3000", cookie: null }, TOKEN)?.status, 401);
  assert.equal(refusal({ host: "localhost:3000", origin: "not a url", cookie: null }, TOKEN)?.status, 403);
  assert.equal(refusal({ host: null, origin: null, cookie: null }, TOKEN)?.status, 401);
});

test("from a tunnel or the LAN the lab stays locked until the passcode was typed", () => {
  const tunnel = { host: "demo.trycloudflare.com", origin: "https://demo.trycloudflare.com" };
  assert.match(refusal({ ...tunnel, cookie: null }, TOKEN)?.detail ?? "", /^locked/);
  assert.equal(refusal({ ...tunnel, cookie: "wrong" }, TOKEN)?.status, 401);
  assert.equal(refusal({ ...tunnel, cookie: sessionValue("another-token-000000") }, TOKEN)?.status, 401);
  assert.equal(refusal({ ...tunnel, cookie }, TOKEN), null);
});

test("the cookie is not the passcode", () => {
  assert.notEqual(cookie, TOKEN);
  assert.equal(cookie.length, 64);
  assert.ok(same(cookie, sessionValue(TOKEN)) && !same(cookie, cookie.slice(1)));
});

test("wrong passcodes are limited, however the caller names itself", () => {
  const tries = new Attempts(3, 60_000);
  for (const t of [0, 1000, 2000]) assert.equal(tries.take(t), true);
  assert.equal(tries.take(3000), false);
  assert.equal(tries.take(59_999), false);
  assert.equal(tries.take(62_001), true);  // the oldest tries aged out
});

test("a right passcode does not use up a try", () => {
  const tries = new Attempts(2, 60_000);
  for (let i = 0; i < 5; i++) { assert.equal(tries.take(i), true); tries.forgive(i); }
  assert.equal(tries.take(10), true);
});
