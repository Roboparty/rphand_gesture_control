const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');

const { attachLogForwarder } = require('../log-forwarder.cjs');

test('a closed parent log pipe cannot crash the packaged app', () => {
  const source = new EventEmitter();
  source.setEncoding = () => {};
  const writes = [];
  const destination = new EventEmitter();
  destination.writable = true;
  destination.destroyed = false;
  destination.write = (chunk) => writes.push(chunk);

  const detach = attachLogForwarder(source, destination);
  source.emit('data', 'first line');
  assert.deepEqual(writes, ['first line']);

  destination.destroyed = true;
  assert.doesNotThrow(() => {
    destination.emit('error', Object.assign(new Error('broken pipe'), { code: 'EPIPE' }));
    source.emit('data', 'second line');
  });
  assert.deepEqual(writes, ['first line']);

  detach();
});
