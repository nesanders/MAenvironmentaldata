// Unit tests for the pure, DOM-free helpers in ai_analysis.js.
// Run with: node --test docs/assets/   (Node >= 18, no dependencies)
//
// These lock in the fixes for:
//   - LLM SQL that used unsupported window functions (prompt rule)
//   - JSON responses with prose/commentary after the object (parseJSON)
//   - the reserved-word `index` quoting (normalizeGeneratedSql)

const test = require('node:test');
const assert = require('node:assert');
const ai = require('./ai_analysis.js');

test('parseJSON: plain object', () => {
  assert.deepStrictEqual(ai.parseJSON('{"sql": null, "reasoning": "ok"}'),
    { sql: null, reasoning: 'ok' });
});

test('parseJSON: strips ```json code fences', () => {
  assert.deepStrictEqual(ai.parseJSON('```json\n{"sql":"SELECT 1"}\n```'),
    { sql: 'SELECT 1' });
});

test('parseJSON: tolerates trailing prose after the JSON object', () => {
  // The exact failure the user hit: "Unexpected non-whitespace character
  // after JSON at position 563".
  const r = ai.parseJSON('{"sql":"SELECT 1","reasoning":"x"}\n\nHere is why: trailing prose.');
  assert.strictEqual(r.sql, 'SELECT 1');
});

test('parseJSON: leading prose + braces inside string literals', () => {
  const r = ai.parseJSON('Sure!\n{"sql":null,"answer":"because {nested} braces"}\n\nHope that helps.');
  assert.strictEqual(r.answer, 'because {nested} braces');
});

test('parseJSON: still throws when there is no JSON at all', () => {
  assert.throws(() => ai.parseJSON('not json, no braces here'));
});

test('extractFirstJSONObject: returns null when no object present', () => {
  assert.strictEqual(ai.extractFirstJSONObject('nothing to see'), null);
});

test('extractFirstJSONObject: ignores braces inside strings', () => {
  assert.strictEqual(
    ai.extractFirstJSONObject('{"a":"}{"}trailing'),
    '{"a":"}{"}'
  );
});

test('normalizeGeneratedSql: quotes a bare `index` keyword', () => {
  assert.match(ai.normalizeGeneratedSql('SELECT index FROM t'), /"index"/);
});

test('normalizeGeneratedSql: leaves an already-quoted string literal alone', () => {
  const out = ai.normalizeGeneratedSql('SELECT a FROM t WHERE b = "index"');
  assert.strictEqual((out.match(/"index"/g) || []).length, 1);
});

test('buildStage1SystemPrompt: forbids window functions', () => {
  const p = ai.buildStage1SystemPrompt('CREATE TABLE t (a INTEGER);');
  assert.match(p, /window functions/i);
  assert.match(p, /ROW_NUMBER/);
  assert.match(p, /PARTITION BY/);
});

test('buildStage1SystemPrompt: recommends the correlated-subquery pattern', () => {
  const p = ai.buildStage1SystemPrompt('CREATE TABLE t (a INTEGER);');
  assert.match(p, /correlated subquery/i);
});
