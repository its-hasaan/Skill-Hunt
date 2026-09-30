import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker, { ping } from './worker.js';

test('ping reports a healthy endpoint', async () => {
  const calls = [];
  const fakeFetch = async (url) => { calls.push(url); return { ok: true, status: 200 }; };
  const result = await ping({ HEALTH_URL: 'https://api.example.com/health' }, fakeFetch);
  assert.equal(result.ok, true);
  assert.equal(result.status, 200);
  assert.deepEqual(calls, ['https://api.example.com/health']);
});

test('ping reports failure instead of throwing', async () => {
  const result = await ping({ HEALTH_URL: 'https://x.test' }, async () => { throw new Error('boom'); });
  assert.equal(result.ok, false);
  assert.match(result.error, /boom/);
});

test('scheduled handler hands the ping to waitUntil', async () => {
  let waited;
  globalThis.fetch = async () => ({ ok: true, status: 200 });
  await worker.scheduled({}, { HEALTH_URL: 'https://x.test' }, { waitUntil: (p) => { waited = p; } });
  assert.equal((await waited).ok, true);
});
