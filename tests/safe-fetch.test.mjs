import assert from 'node:assert/strict';
import test from 'node:test';

import { isBlockedAddress, safeFetch } from '../functions/lib/safe-fetch.js';

const headers = values => ({
  get(name) { return values?.[String(name).toLowerCase()] ?? null; },
});

const bodyOf = chunks => ({
  getReader() {
    let index = 0;
    return {
      async read() {
        if (index >= chunks.length) return { done: true };
        return { done: false, value: chunks[index++] };
      },
      async cancel() {},
    };
  },
});

test('DNSがlink-local metadata IPを返したらfetch前に拒否する', async () => {
  let fetchCalls = 0;
  await assert.rejects(safeFetch('https://public.example/', {
    resolveHost: async () => ['169.254.169.254'],
    fetchImpl: async () => { fetchCalls++; throw new Error('must not fetch'); },
  }), error => error.code === 'private_destination');
  assert.equal(fetchCalls, 0);
});

test('公開URLからloopbackへのredirectを追わない', async () => {
  let fetchCalls = 0;
  await assert.rejects(safeFetch('https://public.example/', {
    resolveHost: async () => ['93.184.216.34'],
    fetchImpl: async () => {
      fetchCalls++;
      return { status: 302, headers: headers({ location: 'http://127.0.0.1/admin' }), body: null };
    },
  }), error => error.code === 'private_destination');
  assert.equal(fetchCalls, 1);
});

test('body読み取りにも全体deadlineを適用する', async () => {
  const first = new TextEncoder().encode('first');
  await assert.rejects(safeFetch('https://public.example/', {
    deadlineMs: 15,
    resolveHost: async () => ['93.184.216.34'],
    fetchImpl: async () => ({
      status: 200,
      headers: headers(),
      body: {
        getReader() {
          let index = 0;
          return {
            async read() {
              if (index++ === 0) return { done: false, value: first };
              return new Promise(resolve => setTimeout(() => resolve({ done: true }), 80));
            },
            async cancel() {},
          };
        },
      },
    }),
  }), error => error.code === 'deadline_exceeded');
});

test('IPv4-mapped IPv6の16進表記でもprivate IPv4を拒否する', () => {
  assert.equal(isBlockedAddress('::ffff:7f00:1'), true);
  assert.equal(isBlockedAddress('0:0:0:0:0:ffff:a9fe:a9fe'), true);
});

test('整数表記IPv4はURL正規化後にloopbackとして拒否する', async () => {
  await assert.rejects(safeFetch('http://2130706433/', {
    fetchImpl: async () => { throw new Error('must not fetch'); },
  }), error => error.code === 'private_destination');
});

test('最大byte数で本文を切り詰める', async () => {
  const result = await safeFetch('https://public.example/', {
    maxBytes: 4,
    resolveHost: async () => ['93.184.216.34'],
    fetchImpl: async () => ({
      status: 200,
      headers: headers(),
      body: bodyOf([new TextEncoder().encode('abcdef')]),
    }),
  });
  assert.equal(result.text, 'abcd');
  assert.equal(result.bytes, 4);
  assert.equal(result.truncated, true);
});
