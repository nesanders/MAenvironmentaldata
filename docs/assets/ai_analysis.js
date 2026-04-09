// ═════════════════════════════════════════════════════════════════════════════
// AMEND AI Analysis — Client-side Interactive Data Analysis
// ═════════════════════════════════════════════════════════════════════════════

// ─── State ───────────────────────────────────────────────────────────────────
const STATE = {
  worker: null,
  dbReady: false,
  schema: null,
  extendedContext: null,
  workerBusy: false,
  artifactCounter: 0,
  pendingWorkerResolve: null,
  pendingWorkerReject: null,
  conversationHistory: [],   // [{role, content}] for multi-turn context
};

const ARTIFACT_STORE = {}; // { [id]: { question, sql, queryResults, chartSpec, answerText } }

// ─── Constants ────────────────────────────────────────────────────────────────
const DB_URL = 'https://storage.googleapis.com/openamend-data/amend.db';
const SCHEMA_QUERY = "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name";
const MAX_PREVIEW_ROWS = 20;
const WRITE_BLOCK_RE = /\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b/i;

const PROVIDER_CONFIG = {
  groq: {
    endpoint: 'https://api.groq.com/openai/v1/chat/completions',
    defaultModel: 'llama-3.3-70b-versatile',
    format: 'openai',
  },
  openai: {
    endpoint: 'https://api.openai.com/v1/chat/completions',
    defaultModel: 'gpt-4o-mini',
    format: 'openai',
  },
  gemini: {
    endpoint: 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
    defaultModel: 'gemini-2.0-flash',
    format: 'gemini',
  },
};

const DEFAULTS = {
  provider: 'groq',
  model: PROVIDER_CONFIG.groq.defaultModel,
  apiKey: '',
  useExtendedContext: false,
};

const MAX_HISTORY_TURNS = 3;  // user+assistant pairs to keep in context

// ─── Geographic Map Config ────────────────────────────────────────────────────
const GEO_CONFIG = {
  towns: {
    url: 'assets/geo_json/TOWNSSURVEY_POLYM_geojson_simple.json',
    featureidkey: 'properties.TOWN',
    normalize: function(v) { return String(v).toUpperCase().trim(); },
  },
  watersheds: {
    url: 'assets/geo_json/watshdp1_geojson_simple.json',
    featureidkey: 'properties.NAME',
    normalize: function(v) { return String(v).toUpperCase().trim(); },
  },
  census_bg: {
    url: 'assets/geo_json/cb_2017_25_bg_500k.json',
    featureidkey: 'properties.GEOID',
    normalize: function(v) { return String(v); },
  },
};
const GEO_CACHE = {};

// ─── Worker Management ────────────────────────────────────────────────────────

function initWorker() {
  // Worker path relative to page root — ai_analysis.html is at docs/
  STATE.worker = new Worker('assets/worker.sql.js');
  STATE.worker.onerror = function(e) {
    if (STATE.pendingWorkerReject) STATE.pendingWorkerReject(e);
    showChatError('Worker error: ' + e.message);
  };
  STATE.worker.onmessage = function(event) {
    if (STATE.pendingWorkerResolve) {
      var resolve = STATE.pendingWorkerResolve;
      STATE.pendingWorkerResolve = null;
      STATE.pendingWorkerReject = null;
      STATE.workerBusy = false;
      resolve(event.data);
    }
  };
}

function workerExec(message, transferables) {
  return new Promise(function(resolve, reject) {
    if (STATE.workerBusy) {
      reject(new Error('Worker is busy'));
      return;
    }
    STATE.workerBusy = true;
    STATE.pendingWorkerResolve = resolve;
    STATE.pendingWorkerReject = reject;
    if (transferables) {
      STATE.worker.postMessage(message, transferables);
    } else {
      STATE.worker.postMessage(message);
    }
  });
}

// ─── Database Loading ─────────────────────────────────────────────────────────

function loadDatabase() {
  var loadBtn = document.getElementById('ai-load-db');
  var progressWrap = document.getElementById('ai-db-progress-wrap');
  var progressEl = document.getElementById('ai-db-progress');
  var progressLabel = document.getElementById('ai-db-progress-label');
  var statusText = document.getElementById('ai-db-status-text');

  loadBtn.disabled = true;
  progressWrap.style.display = 'block';
  statusText.textContent = 'Downloading database...';

  var xhr = new XMLHttpRequest();
  xhr.open('GET', DB_URL, true);
  xhr.responseType = 'arraybuffer';

  xhr.onprogress = function(e) {
    if (e.lengthComputable) {
      var pct = Math.round((e.loaded / e.total) * 100);
      progressEl.value = pct;
      progressLabel.textContent = pct + '%';
    }
  };

  xhr.onerror = function() {
    statusText.textContent = 'Download failed. Check network connection.';
    loadBtn.disabled = false;
    progressWrap.style.display = 'none';
  };

  xhr.onload = function() {
    if (this.status !== 200) {
      statusText.textContent = 'Download failed: HTTP ' + this.status +
        '. Check that the database is accessible. If testing locally, see CORS note below.';
      loadBtn.disabled = false;
      progressWrap.style.display = 'none';
      return;
    }
    statusText.textContent = 'Opening database in worker...';
    var uInt8Array = new Uint8Array(this.response);
    openDBInWorker(this.response)
      .then(function() {
        return loadSchema();
      })
      .then(function(schema) {
        STATE.schema = schema;
        STATE.dbReady = true;
        var useExt = loadSettings().useExtendedContext;
        if (useExt) return loadExtendedContext();
      })
      .then(function() {
        onDBReady();
      })
      .catch(function(err) {
        statusText.textContent = 'Error: ' + err.message;
        loadBtn.disabled = false;
      });
  };

  xhr.send();
}

function openDBInWorker(arrayBuffer) {
  // Clone buffer twice to safely attempt transfer + fallback
  var copy1 = arrayBuffer.slice(0);
  var copy2 = arrayBuffer.slice(0);

  return workerExec({ action: 'open', buffer: new Uint8Array(copy1) }, [copy1])
    .catch(function() {
      // Fallback: transfer failed, try without transferable
      STATE.workerBusy = false;
      return workerExec({ action: 'open', buffer: new Uint8Array(copy2) });
    });
}

function loadSchema() {
  return workerExec({ action: 'exec', sql: SCHEMA_QUERY })
    .then(function(data) {
      if (!data.results || data.results.length === 0) return '';
      var rows = data.results[0].values;
      return rows.map(function(r) { return r[1]; }).join('\n\n');
    });
}

function loadExtendedContext() {
  // Fetch data dictionary + methodology excerpts
  return Promise.all([
    fetchExtendedContext(),
  ]).then(function() {
    // Context loaded and cached in STATE.extendedContext
  }).catch(function(err) {
    console.warn('Failed to load extended context:', err);
    // Silently fall back to schema-only mode
    STATE.extendedContext = null;
  });
}

function fetchExtendedContext() {
  // Fetch docs/data/data_stats.yml for table descriptions
  // This is a simplified version; in production you might fetch more
  // For now, just fetch a brief context string
  return fetch('data/data_stats.yml')
    .then(function(r) { return r.text(); })
    .then(function(text) {
      // Parse YAML as simple key-value (not a full YAML parser)
      // Extract table descriptions
      var lines = text.split('\n');
      var context = 'Data Tables:\n';
      for (var i = 0; i < lines.length; i++) {
        if (lines[i].includes('MADEP') || lines[i].includes('EEA') || lines[i].includes('CSO')) {
          context += lines[i] + '\n';
        }
      }
      STATE.extendedContext = context || null;
    });
}

function onDBReady() {
  var statusEl = document.getElementById('ai-db-status');
  statusEl.querySelector('#ai-db-status-text').textContent = 'Database loaded. Ready.';
  statusEl.querySelector('#ai-db-progress-wrap').style.display = 'none';
  document.getElementById('ai-submit').disabled = false;
  document.getElementById('ai-question').placeholder = 'Ask a question about the environmental data... (Shift+Enter for newline, Enter to submit)';
}

// ─── Settings Management ──────────────────────────────────────────────────────

function loadSettings() {
  return {
    provider: localStorage.getItem('ai_provider') || DEFAULTS.provider,
    model: localStorage.getItem('ai_model') || DEFAULTS.model,
    apiKey: localStorage.getItem('ai_api_key') || DEFAULTS.apiKey,
    useExtendedContext: localStorage.getItem('ai_use_extended_context') === 'true',
  };
}

function getModelFromUI(provider) {
  var custom = document.getElementById('ai-model-custom').value.trim();
  if (custom) return custom;
  return document.getElementById('ai-model-select-' + provider).value;
}

function updateModelUI(provider) {
  ['groq', 'openai', 'gemini'].forEach(function(p) {
    document.getElementById('ai-model-select-' + p).style.display = p === provider ? '' : 'none';
  });
}

function saveSettings() {
  var provider = document.getElementById('ai-provider').value;
  var model = getModelFromUI(provider);
  var apiKey = document.getElementById('ai-api-key').value.trim();
  var useExt = document.getElementById('ai-use-extended-context').checked;

  localStorage.setItem('ai_provider', provider);
  localStorage.setItem('ai_model', model || PROVIDER_CONFIG[provider].defaultModel);
  localStorage.setItem('ai_model_custom', document.getElementById('ai-model-custom').value.trim());
  localStorage.setItem('ai_api_key', apiKey);
  localStorage.setItem('ai_use_extended_context', useExt ? 'true' : 'false');

  document.getElementById('ai-settings-saved').style.display = 'inline';
  setTimeout(function() {
    document.getElementById('ai-settings-saved').style.display = 'none';
  }, 2000);
}

function populateSettingsUI() {
  var s = loadSettings();
  document.getElementById('ai-provider').value = s.provider;
  updateModelUI(s.provider);

  // Try to select saved model in the provider's dropdown
  var sel = document.getElementById('ai-model-select-' + s.provider);
  if (sel) {
    for (var i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === s.model) { sel.selectedIndex = i; break; }
    }
  }
  // Restore custom override if saved
  var savedCustom = localStorage.getItem('ai_model_custom') || '';
  document.getElementById('ai-model-custom').value = savedCustom;

  document.getElementById('ai-use-extended-context').checked = s.useExtendedContext;
  // Do NOT pre-fill API key for security
}

// ─── LLM API Calls ───────────────────────────────────────────────────────────

function callLLM(messages, jsonMode) {
  var s = loadSettings();
  var cfg = PROVIDER_CONFIG[s.provider];
  var model = s.model || cfg.defaultModel;
  var apiKey = s.apiKey;

  if (!apiKey) return Promise.reject(new Error('No API key set. Open API Settings above.'));

  if (cfg.format === 'openai') {
    return callOpenAICompat(cfg.endpoint, apiKey, model, messages, jsonMode);
  } else if (cfg.format === 'gemini') {
    return callGemini(cfg.endpoint, apiKey, model, messages);
  }
}

function callOpenAICompat(endpoint, apiKey, model, messages, jsonMode) {
  var body = {
    model: model,
    messages: messages,
    temperature: 0.1,
  };
  if (jsonMode) {
    body.response_format = { type: 'json_object' };
  }
  return fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + apiKey,
    },
    body: JSON.stringify(body),
  }).then(function(r) {
    if (!r.ok) return r.text().then(function(t) {
      throw new Error('LLM API error ' + r.status + ': ' + t);
    });
    return r.json();
  }).then(function(data) {
    if (!data.choices || !data.choices[0] || !data.choices[0].message) {
      throw new Error('Unexpected LLM response format');
    }
    return data.choices[0].message.content;
  });
}

function callGemini(endpointTemplate, apiKey, model, messages) {
  // Convert OpenAI-style messages to Gemini format
  var systemMsg = messages.find(function(m) { return m.role === 'system'; });
  var userMsgs = messages.filter(function(m) { return m.role !== 'system'; });

  var contents = userMsgs.map(function(m) {
    return {
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }],
    };
  });

  var body = { contents: contents };
  if (systemMsg) {
    body.systemInstruction = { parts: [{ text: systemMsg.content }] };
  }
  body.generationConfig = {
    responseMimeType: 'application/json',
    temperature: 0.1,
  };

  var url = endpointTemplate.replace('{model}', model) + '?key=' + apiKey;

  return fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(function(r) {
    if (!r.ok) return r.text().then(function(t) {
      throw new Error('Gemini API error ' + r.status + ': ' + t);
    });
    return r.json();
  }).then(function(data) {
    if (!data.candidates || !data.candidates[0] || !data.candidates[0].content) {
      throw new Error('Unexpected Gemini response format');
    }
    return data.candidates[0].content.parts[0].text;
  });
}

function parseJSON(text) {
  // Strip markdown code fences if present
  var cleaned = text.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/, '').trim();
  return JSON.parse(cleaned);
}

// ─── System Prompts ──────────────────────────────────────────────────────────

function buildStage1SystemPrompt(schema) {
  var parts = [
    'You are an expert data analyst for Massachusetts environmental data.',
    'The user is querying a SQLite database. Here is the complete schema:',
    '',
    '```sql',
    schema,
    '```',
    '',
  ];

  if (STATE.extendedContext) {
    parts.push('Background context:', STATE.extendedContext, '');
  }

  parts.push(
    'When the user asks a question, respond with ONLY valid JSON in this exact format:',
    '{',
    '  "sql": "SELECT ... ;",',
    '  "chart_spec": { ... },',
    '  "reasoning": "One sentence explaining your approach"',
    '}',
    '',
    'chart_spec types:',
    '- Standard charts: type = "bar", "line", "scatter", "histogram", "pie", "table"',
    '  Fields: "x", "y", "color" (optional grouping), "title"',
    '',
    '- Choropleth map: type = "map"',
    '  Use when results contain town names, watershed names, or census block group IDs.',
    '  Fields: "geography" ("towns"|"watersheds"|"census_bg"), "geo_id_col" (column with geographic ID), "value_col" (numeric column to color by), "title"',
    '  Geographic ID columns: Town names are uppercase (e.g. "BOSTON"). Watershed names are uppercase (e.g. "CHARLES"). GEOID is a 12-digit string.',
    '  Common columns: Town/municipality → towns; Watershed/Waterbody → watersheds; GEOID → census_bg',
    '',
    '- Point map: type = "scatter_map"',
    '  Use when results contain latitude and longitude columns.',
    '  Fields: "lat_col", "lon_col", "text_col" (optional label), "value_col" (optional color/size), "title"',
    '',
    'SQL rules:',
    '- Write valid SQLite SELECT statements only',
    '- Never use INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or TRUNCATE',
    '- Use LIMIT 500 for row-level queries; no LIMIT for aggregations by geography',
    '- Column names must exactly match the schema',
    '- For map queries, always include the geographic ID column (Town, Watershed, GEOID, latitude, longitude)',
    '- If the question cannot be answered with available tables, set sql to null and explain in reasoning',
    '- If the user asks a follow-up, refer to prior SQL in the conversation to build on it',
    '- String values in this database are often ALL CAPS (e.g. waterBody = \'MYSTIC RIVER\', municipality = \'BOSTON\'). Always use UPPER() for string filters: WHERE UPPER(column) = UPPER(\'value\') or WHERE UPPER(column) LIKE UPPER(\'%value%\')',
    '- Common waterBody values include: MYSTIC RIVER, CHARLES RIVER, NEPONSET RIVER, BOSTON HARBOR, MERRIMACK RIVER, CONNECTICUT RIVER, etc. Always uppercase these.'
  );

  return parts.join('\n');
}

function buildStage2SystemPrompt() {
  return [
    'You are an expert data analyst interpreting query results.',
    'The user asked a question, SQL was executed, and you have the results.',
    'Respond with ONLY valid JSON in this exact format:',
    '{',
    '  "answer": "Clear, concise natural language answer (1-3 sentences)",',
    '  "chart_spec": { ... }',
    '}',
    '',
    'chart_spec types (choose best for the data):',
    '- Standard: type = "bar"|"line"|"scatter"|"histogram"|"pie"|"table". Fields: "x", "y", "color", "title"',
    '- Choropleth map: type = "map". Fields: "geography" ("towns"|"watersheds"|"census_bg"), "geo_id_col", "value_col", "title"',
    '- Point map: type = "scatter_map". Fields: "lat_col", "lon_col", "text_col", "value_col", "title"',
    '',
    'Guidelines:',
    '- The answer must directly address the user question using the actual data values',
    '- If results have a Town or municipality column, prefer type "map" with geography "towns"',
    '- If results have a Watershed or Waterbody column, prefer type "map" with geography "watersheds"',
    '- If results have latitude/longitude columns, prefer type "scatter_map"',
    '- Verify all column names in chart_spec exactly match the actual result columns',
    '- If the data has only one row or is not visual, set chart_spec.type to "table"',
    '- Do not invent numbers not present in the results',
  ].join('\n');
}

// ─── Main Analysis Flow ───────────────────────────────────────────────────────

async function runAnalysis(question) {
  if (!STATE.dbReady) throw new Error('Database not loaded yet.');
  if (STATE.workerBusy) throw new Error('A query is already running. Please wait.');

  // Stage 1: question + schema + history → SQL + chart_spec
  appendChatMessage('assistant', '⏳ Generating SQL query…', 'status');
  var stage1Messages = [
    { role: 'system', content: buildStage1SystemPrompt(STATE.schema) },
    ...STATE.conversationHistory,
    { role: 'user', content: question },
  ];

  var stage1Text = await callLLM(stage1Messages, true);
  var stage1 = parseJSON(stage1Text);

  if (!stage1.sql) {
    throw new Error('Could not generate SQL: ' + (stage1.reasoning || stage1.error || 'unknown reason'));
  }

  // SQL safety check
  if (WRITE_BLOCK_RE.test(stage1.sql)) {
    throw new Error('Generated SQL contains disallowed operations.');
  }

  updateLastStatus('⏳ Executing SQL query…');

  // Execute SQL via worker
  var sqlResult = await workerExec({ action: 'exec', sql: stage1.sql });
  if (sqlResult.error) {
    // Attempt retry with error context
    stage1 = await retrySQLWithError(question, stage1.sql, sqlResult.error);
    if (WRITE_BLOCK_RE.test(stage1.sql)) {
      throw new Error('Retry produced SQL with disallowed operations.');
    }
    sqlResult = await workerExec({ action: 'exec', sql: stage1.sql });
    if (sqlResult.error) throw new Error('SQL error after retry: ' + sqlResult.error);
  }

  var queryResults = sqlResult.results && sqlResult.results[0];
  if (!queryResults) {
    throw new Error(
      'Query returned no result set — the SQL may not be a SELECT statement, or the query failed silently.\n\nSQL attempted:\n' + stage1.sql
    );
  }
  if (queryResults.values.length === 0) {
    throw new Error(
      'Query returned 0 rows. The filters may not match any records.\n\nSQL:\n' + stage1.sql +
      '\n\nColumns expected: ' + queryResults.columns.join(', ') +
      '\n\nTry broadening the query (remove WHERE clauses, check spelling of values).'
    );
  }

  // Stage 2: question + SQL + preview rows → answer + refined chart_spec
  updateLastStatus('⏳ Interpreting results…');
  var preview = formatResultsForLLM(queryResults, MAX_PREVIEW_ROWS);
  var stage2Messages = [
    { role: 'system', content: buildStage2SystemPrompt() },
    {
      role: 'user',
      content: [
        'Question: ' + question,
        '',
        'SQL executed:',
        '```sql',
        stage1.sql,
        '```',
        '',
        'Query results (up to ' + MAX_PREVIEW_ROWS + ' rows):',
        preview,
      ].join('\n'),
    },
  ];

  var stage2Text = await callLLM(stage2Messages, true);
  var stage2 = parseJSON(stage2Text);

  // Create artifact
  removeLastStatus();
  var chartSpec = stage2.chart_spec || stage1.chart_spec || { type: 'table', x: queryResults.columns[0], y: queryResults.columns[1] };
  var artifactId = await createArtifact(question, stage1.sql, queryResults, chartSpec, stage2.answer);
  appendChatMessage('assistant', stage2.answer, 'answer', artifactId);

  // Append to conversation history for follow-up context
  STATE.conversationHistory.push(
    { role: 'user', content: question },
    {
      role: 'assistant',
      content: 'Answer: ' + stage2.answer + '\n\nSQL used:\n' + stage1.sql +
                '\n\nResult columns: ' + queryResults.columns.join(', ') +
                '\nData preview:\n' + formatResultsForLLM(queryResults, 5),
    }
  );
  // Keep only last MAX_HISTORY_TURNS pairs
  if (STATE.conversationHistory.length > MAX_HISTORY_TURNS * 2) {
    STATE.conversationHistory = STATE.conversationHistory.slice(-MAX_HISTORY_TURNS * 2);
  }
}

async function retrySQLWithError(question, failedSQL, errorMsg) {
  appendChatMessage('assistant', '⚠️ SQL error, retrying with correction…', 'status');
  var retryMessages = [
    { role: 'system', content: buildStage1SystemPrompt(STATE.schema) },
    { role: 'user', content: question },
    { role: 'assistant', content: JSON.stringify({ sql: failedSQL, reasoning: '' }) },
    {
      role: 'user',
      content: 'That SQL produced an error: "' + errorMsg + '". Please fix the SQL and return corrected JSON.',
    },
  ];
  var retryText = await callLLM(retryMessages, true);
  return parseJSON(retryText);
}

// ─── GeoJSON Loading ─────────────────────────────────────────────────────────

function loadGeoJSON(geography) {
  if (GEO_CACHE[geography]) return Promise.resolve(GEO_CACHE[geography]);
  var cfg = GEO_CONFIG[geography];
  if (!cfg) return Promise.reject(new Error('Unknown geography: ' + geography));
  return fetch(cfg.url)
    .then(function(r) {
      if (!r.ok) throw new Error('Failed to load map data (' + r.status + ')');
      return r.json();
    })
    .then(function(data) {
      GEO_CACHE[geography] = data;
      return data;
    });
}

// ─── Plotly Chart Rendering ──────────────────────────────────────────────────

function buildPlotlyFigure(chartSpec, queryResults) {
  var columns = queryResults.columns;
  var values = queryResults.values;

  // Transpose: values is array of rows, each row is array of cell values
  var colData = {};
  columns.forEach(function(col, ci) {
    colData[col] = values.map(function(row) { return row[ci]; });
  });

  var type = chartSpec.type || 'bar';
  var xKey = chartSpec.x;
  var yKey = chartSpec.y;
  var colorKey = chartSpec.color;
  var title = chartSpec.title || '';

  var data = [];
  var layout = {
    title: title,
    autosize: true,
    margin: { l: 50, r: 20, t: 40, b: 80 },
  };

  if (type === 'table') {
    data = [{
      type: 'table',
      header: {
        values: columns,
        fill: { color: '#285858' },
        font: { color: 'white' },
      },
      cells: {
        values: columns.map(function(c) { return colData[c] || []; }),
      },
    }];

  } else if (type === 'pie') {
    var labels = colData[xKey] || colData[columns[0]] || [];
    var values = colData[yKey] || colData[columns[1]] || [];
    data = [{
      type: 'pie',
      labels: labels,
      values: values,
    }];

  } else if (type === 'histogram') {
    data = [{
      type: 'histogram',
      x: colData[xKey] || colData[columns[0]] || [],
    }];

  } else if (colorKey && colData[colorKey]) {
    // Grouped traces — one per unique color value
    var groups = [...new Set(colData[colorKey])];
    groups.forEach(function(grp) {
      var mask = colData[colorKey].map(function(v) { return v === grp; });
      var xVals = colData[xKey] ? colData[xKey].filter(function(_, i) { return mask[i]; }) : [];
      var yVals = colData[yKey] ? colData[yKey].filter(function(_, i) { return mask[i]; }) : [];

      data.push({
        type: type === 'scatter' ? 'scatter' : type,
        mode: type === 'scatter' ? 'markers' : (type === 'line' ? 'lines+markers' : undefined),
        name: String(grp),
        x: xVals,
        y: yVals,
      });
    });

  } else {
    // Single trace
    var xVals = colData[xKey] || colData[columns[0]] || [];
    var yVals = colData[yKey] || colData[columns[1]] || [];

    data = [{
      type: type === 'scatter' ? 'scatter' : type,
      mode: type === 'scatter' ? 'markers' : (type === 'line' ? 'lines+markers' : undefined),
      x: xVals,
      y: yVals,
    }];
  }

  return { data: data, layout: layout };
}

function buildMapFigure(chartSpec, queryResults, geojson) {
  var colData = {};
  queryResults.columns.forEach(function(col, ci) {
    colData[col] = queryResults.values.map(function(row) { return row[ci]; });
  });

  var geography = chartSpec.geography || 'towns';
  var cfg = GEO_CONFIG[geography] || GEO_CONFIG.towns;
  var geoIdCol = chartSpec.geo_id_col;
  var valueCol = chartSpec.value_col;

  var rawIds = colData[geoIdCol] || colData[queryResults.columns[0]] || [];
  var locations = rawIds.map(cfg.normalize);
  var zValues = colData[valueCol] || colData[queryResults.columns[1]] || [];

  return {
    data: [{
      type: 'choroplethmap',
      geojson: geojson,
      locations: locations,
      z: zValues,
      featureidkey: cfg.featureidkey,
      colorscale: 'YlOrRd',
      marker: { opacity: 0.7, line: { width: 0.5, color: 'white' } },
      hovertemplate: '%{location}: %{z:,.1f}<extra></extra>',
      colorbar: { title: { text: valueCol || '' } },
    }],
    layout: {
      title: chartSpec.title || '',
      // center/zoom = MA default; fitbounds overrides when matched features exist
      map: {
        style: 'open-street-map',
        center: { lat: 42.4, lon: -71.8 },
        zoom: 7,
        fitbounds: 'locations',
      },
      margin: { r: 0, t: 40, l: 0, b: 0 },
      autosize: true,
    },
  };
}

function buildScatterMapFigure(chartSpec, queryResults) {
  var colData = {};
  queryResults.columns.forEach(function(col, ci) {
    colData[col] = queryResults.values.map(function(row) { return row[ci]; });
  });

  var latCol = chartSpec.lat_col;
  var lonCol = chartSpec.lon_col;
  var textCol = chartSpec.text_col;
  var valueCol = chartSpec.value_col;

  var rawLat = colData[latCol] || [];
  var rawLon = colData[lonCol] || [];

  // Validate coordinates — filter out nulls and out-of-range values
  var validMask = rawLat.map(function(lat, i) {
    var lon = parseFloat(rawLon[i]);
    lat = parseFloat(lat);
    return !isNaN(lat) && !isNaN(lon) &&
           lat >= -90 && lat <= 90 &&
           lon >= -180 && lon <= 180;
  });

  var nTotal = rawLat.length;
  var nValid = validMask.filter(Boolean).length;

  function applyMask(arr) {
    return (arr || []).filter(function(_, i) { return validMask[i]; });
  }

  if (nValid === 0) {
    // No valid coordinates — fall back to a table
    console.warn('scatter_map: no valid coordinates found in columns', latCol, lonCol, '— falling back to table');
    return buildPlotlyFigure({ type: 'table' }, queryResults);
  }

  var trace = {
    type: 'scattermap',
    lat: applyMask(rawLat).map(Number),
    lon: applyMask(rawLon).map(Number),
    mode: 'markers',
    marker: { size: 8, color: '#285858' },
  };

  if (nValid < nTotal) {
    trace.name = nValid + ' of ' + nTotal + ' points (invalid coords filtered)';
  }

  if (textCol && colData[textCol]) {
    trace.text = applyMask(colData[textCol]);
    trace.hovertemplate = '%{text}<extra></extra>';
  }
  if (valueCol && colData[valueCol]) {
    var colorVals = applyMask(colData[valueCol]).map(Number);
    trace.marker.color = colorVals;
    trace.marker.colorscale = 'YlOrRd';
    trace.marker.showscale = true;
    trace.marker.colorbar = { title: { text: valueCol } };
  }

  return {
    data: [trace],
    layout: {
      title: chartSpec.title || '',
      map: {
        style: 'open-street-map',
        center: { lat: 42.4, lon: -71.8 },
        zoom: 7,
        fitbounds: 'locations',
      },
      margin: { r: 0, t: 40, l: 0, b: 0 },
      autosize: true,
    },
  };
}

// Async wrapper — handles GeoJSON loading for map types, sync for everything else
function renderChart(containerId, chartSpec, queryResults) {
  var type = chartSpec.type;

  if (type === 'map') {
    var el = document.getElementById(containerId);
    if (el) el.textContent = 'Loading map data…';
    return loadGeoJSON(chartSpec.geography || 'towns')
      .then(function(geojson) {
        var fig = buildMapFigure(chartSpec, queryResults, geojson);
        return Plotly.newPlot(containerId, fig.data, fig.layout, { responsive: true });
      });
  }

  if (type === 'scatter_map') {
    var fig = buildScatterMapFigure(chartSpec, queryResults);
    return Promise.resolve(Plotly.newPlot(containerId, fig.data, fig.layout, { responsive: true }));
  }

  var fig = buildPlotlyFigure(chartSpec, queryResults);
  return Promise.resolve(Plotly.newPlot(containerId, fig.data, fig.layout, { responsive: true }));
}

// ─── Artifact Tray System ─────────────────────────────────────────────────────

async function createArtifact(question, sql, queryResults, chartSpec, answerText) {
  STATE.artifactCounter++;
  var id = STATE.artifactCounter;

  ARTIFACT_STORE[id] = { question, sql, queryResults, chartSpec, answerText };

  var el = document.createElement('div');
  el.className = 'ai-artifact-card';
  el.id = 'artifact-' + id;
  el.setAttribute('data-artifact-id', id);

  var truncQ = question.length > 60 ? question.slice(0, 57) + '…' : question;

  el.innerHTML = [
    '<div class="ai-artifact-header">',
    '  <span class="ai-artifact-num">#' + id + '</span>',
    '  <span class="ai-artifact-title">' + escapeHTML(truncQ) + '</span>',
    '  <button class="ai-artifact-toggle" aria-expanded="true" title="Collapse">▲</button>',
    '  <button class="ai-artifact-fullscreen" title="Fullscreen">⛶</button>',
    '</div>',
    '<div class="ai-artifact-body" style="display:block">',
    '  <div class="ai-chart-div" id="chart-' + id + '"></div>',
    '  <div class="ai-answer-text">' + escapeHTML(answerText || '') + '</div>',
    '  <div class="ai-sql-section">',
    '    <button class="ai-sql-toggle">Show SQL ▼</button>',
    '    <pre class="ai-sql-block" style="display:none">' + escapeHTML(sql) + '</pre>',
    '  </div>',
    '</div>',
  ].join('');

  var list = document.getElementById('ai-artifact-list');
  document.getElementById('ai-artifact-empty').style.display = 'none';

  // Collapse all existing cards, then insert new one expanded
  collapseAllArtifacts();
  list.insertBefore(el, list.firstChild);

  el.querySelector('.ai-artifact-toggle').addEventListener('click', function() {
    toggleArtifact(el);
  });
  el.querySelector('.ai-sql-toggle').addEventListener('click', function() {
    var pre = el.querySelector('.ai-sql-block');
    var btn = el.querySelector('.ai-sql-toggle');
    var hidden = pre.style.display === 'none';
    pre.style.display = hidden ? 'block' : 'none';
    btn.innerHTML = hidden ? 'Hide SQL ▲' : 'Show SQL ▼';
  });
  el.querySelector('.ai-artifact-fullscreen').addEventListener('click', function() {
    var d = ARTIFACT_STORE[id];
    openFullscreen(id, d.chartSpec, d.queryResults);
  });

  // Render chart (async for maps)
  await renderChart('chart-' + id, chartSpec, queryResults);

  return id;
}

function collapseAllArtifacts() {
  document.querySelectorAll('.ai-artifact-card').forEach(function(card) {
    var body = card.querySelector('.ai-artifact-body');
    var btn = card.querySelector('.ai-artifact-toggle');
    body.style.display = 'none';
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '▼';
    btn.title = 'Expand';
  });
}

function toggleArtifact(el) {
  var body = el.querySelector('.ai-artifact-body');
  var btn = el.querySelector('.ai-artifact-toggle');
  var isCollapsed = body.style.display === 'none';
  body.style.display = isCollapsed ? 'block' : 'none';
  btn.setAttribute('aria-expanded', isCollapsed ? 'true' : 'false');
  btn.innerHTML = isCollapsed ? '▲' : '▼';
  btn.title = isCollapsed ? 'Collapse' : 'Expand';
  if (isCollapsed) {
    var id = el.getAttribute('data-artifact-id');
    Plotly.relayout('chart-' + id, { autosize: true });
  }
}

function highlightArtifact(artifactId) {
  var el = document.getElementById('artifact-' + artifactId);
  if (!el) return;
  el.classList.remove('ai-highlight');
  void el.offsetWidth; // reflow to restart animation
  el.classList.add('ai-highlight');
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ─── Fullscreen Mode ─────────────────────────────────────────────────────────

function openFullscreen(artifactId, chartSpec, queryResults) {
  var overlay = document.getElementById('ai-fullscreen-overlay');
  var inner = document.getElementById('ai-fullscreen-chart');
  inner.innerHTML = '';
  var chartDiv = document.createElement('div');
  chartDiv.id = 'ai-fullscreen-chart-inner';
  chartDiv.style.width = '100%';
  chartDiv.style.height = '80vh';
  inner.appendChild(chartDiv);

  overlay.style.display = 'flex';

  renderChart('ai-fullscreen-chart-inner', chartSpec, queryResults);

  function closeOverlay() {
    overlay.style.display = 'none';
    Plotly.purge(chartDiv);
  }
  document.getElementById('ai-fullscreen-close').onclick = closeOverlay;
  overlay.onclick = function(e) { if (e.target === overlay) closeOverlay(); };
}

// ─── Chat Message System ─────────────────────────────────────────────────────

function appendChatMessage(role, text, subtype, artifactId) {
  var log = document.getElementById('ai-chat-log');
  var div = document.createElement('div');
  div.className = 'ai-chat-msg ai-chat-msg--' + role;
  if (subtype) div.setAttribute('data-subtype', subtype);

  if (subtype === 'answer' && artifactId) {
    var link = document.createElement('a');
    link.href = '#artifact-' + artifactId;
    link.textContent = '[Chart #' + artifactId + ']';
    link.className = 'ai-artifact-link';
    link.addEventListener('click', function(e) {
      e.preventDefault();
      var card = document.getElementById('artifact-' + artifactId);
      if (card) {
        var body = card.querySelector('.ai-artifact-body');
        if (body.style.display === 'none') toggleArtifact(card);
      }
      highlightArtifact(artifactId);
    });
    div.textContent = text + ' ';
    div.appendChild(link);
  } else {
    div.textContent = text;
  }

  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

function updateLastStatus(text) {
  var log = document.getElementById('ai-chat-log');
  var statusMsgs = log.querySelectorAll('[data-subtype="status"]');
  if (statusMsgs.length > 0) {
    statusMsgs[statusMsgs.length - 1].textContent = text;
  }
}

function removeLastStatus() {
  var log = document.getElementById('ai-chat-log');
  var statusMsgs = log.querySelectorAll('[data-subtype="status"]');
  if (statusMsgs.length > 0) {
    statusMsgs[statusMsgs.length - 1].remove();
  }
}

// ─── Utility Functions ───────────────────────────────────────────────────────

function showChatError(msg) {
  var errEl = document.getElementById('ai-chat-error');
  errEl.textContent = msg;
  errEl.style.display = 'block';
  setTimeout(function() { errEl.style.display = 'none'; }, 8000);
}

function formatResultsForLLM(queryResults, maxRows) {
  var cols = queryResults.columns;
  var vals = queryResults.values.slice(0, maxRows);
  var header = cols.join('\t');
  var rows = vals.map(function(r) { return r.join('\t'); });
  return header + '\n' + rows.join('\n');
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Event Handling & Init ────────────────────────────────────────────────────

async function handleSubmit() {
  var questionEl = document.getElementById('ai-question');
  var question = questionEl.value.trim();
  if (!question) return;
  if (!STATE.dbReady) {
    showChatError('Please load the database first.');
    return;
  }

  var s = loadSettings();
  if (!s.apiKey) {
    showChatError('Please set your API key in API Settings.');
    return;
  }

  document.getElementById('ai-submit').disabled = true;
  questionEl.value = '';
  var startersEl = document.getElementById('ai-starters');
  if (startersEl) startersEl.style.display = 'none';

  appendChatMessage('user', question, 'question');

  try {
    await runAnalysis(question);
  } catch (err) {
    removeLastStatus();
    appendChatMessage('assistant', 'Error: ' + err.message, 'error');
    showChatError(err.message);
  } finally {
    document.getElementById('ai-submit').disabled = false;
    questionEl.focus();
  }
}

document.addEventListener('DOMContentLoaded', function() {
  initWorker();
  populateSettingsUI();

  // Open settings drawer automatically when no API key is saved
  if (!loadSettings().apiKey) {
    document.getElementById('ai-settings').setAttribute('open', '');
  }

  document.getElementById('ai-load-db').addEventListener('click', loadDatabase);
  document.getElementById('ai-save-settings').addEventListener('click', saveSettings);
  document.getElementById('ai-provider').addEventListener('change', function() {
    updateModelUI(this.value);
  });

  var submitBtn = document.getElementById('ai-submit');
  var questionEl = document.getElementById('ai-question');

  submitBtn.addEventListener('click', handleSubmit);
  questionEl.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  });

  // Starter question buttons
  document.querySelectorAll('.ai-starter-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      questionEl.value = btn.textContent;
      var startersEl = document.getElementById('ai-starters');
      if (startersEl) startersEl.style.display = 'none';
      questionEl.focus();
      handleSubmit();
    });
  });
});
