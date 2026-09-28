/**
 * Unofficial Comix.to Security & Token Bridge
 * Executes the sandboxed comix.to security bundle to sign requests and decrypt payloads.
 */

import fs from 'fs';
import readline from 'readline';

let cachedProcessedJs = null;
let cachedSecurePath = null;

function getProcessedJs(securePath) {
  if (cachedProcessedJs && cachedSecurePath === securePath) {
    return cachedProcessedJs;
  }
  let js = fs.readFileSync(securePath, 'utf8');

  // Preprocess imports for Function sandbox
  js = js.replace(
    /import\s*\{\s*r\s*as\s*e\s*\}\s*from\s*["']\.\/rolldown-runtime[^\x00-\x1f"']+\.js["'];?/g,
    'const e = (x) => (x && x.__esModule) ? x : { default: x };'
  );

  // Expose exports to global scope
  js = js.replace(
    /export\s*\{([^}]+)\};?/g,
    (m, g1) => {
      const parts = g1.split(',').map(s => s.trim());
      let code = '';
      for (const p of parts) {
        const [orig, alias] = p.split(/\s+as\s+/);
        code += `global['${alias || orig}'] = ${orig}; global['${orig}'] = ${orig}; `;
      }
      return code;
    }
  );

  cachedProcessedJs = js;
  cachedSecurePath = securePath;
  return js;
}

function createRecursiveProxy(name, overrides = {}) {
  function target() {}
  Object.assign(target, overrides);
  return new Proxy(target, {
    get: (t, prop) => {
      if (typeof prop === 'string' && prop in overrides) return overrides[prop];
      if (prop === 'then' || typeof prop === 'symbol') return undefined;
      return createRecursiveProxy(`${name}.${String(prop)}`);
    },
    set: (t, prop, val) => {
      if (typeof prop === 'string') overrides[prop] = val;
      return true;
    },
    apply: () => createRecursiveProxy(`${name}()`),
    construct: () => createRecursiveProxy(`new_${name}`)
  });
}

function createAxiosSandbox(securePath, cfgToken, mangaId, chapterId, urlPath) {
  const processedJs = getProcessedJs(securePath);

  const documentOverrides = {
    querySelector: (selector) => {
      if (selector.includes('meta[name="cfg"]') || selector.includes("meta[name='cfg']") || selector === 'meta[name=cfg]') {
        return createRecursiveProxy('metaElement', {
          getAttribute: (attr) => attr === 'content' ? cfgToken : null
        });
      }
      return null;
    },
    querySelectorAll: (selector) => {
      if (selector === 'meta') {
        const metaEl = createRecursiveProxy('metaElement', {
          getAttribute: (attr) => attr === 'content' ? cfgToken : null,
          name: 'cfg',
          content: cfgToken
        });
        const list = [metaEl];
        list.item = (idx) => list[idx];
        return list;
      }
      return [];
    },
    createElement: (tag) => createRecursiveProxy(`element(${tag})`),
    head: createRecursiveProxy('document.head'),
    body: createRecursiveProxy('document.body')
  };

  let pageUrl = 'https://comix.to';
  let pagePath = '/';
  if (mangaId) {
    pageUrl = chapterId
      ? `https://comix.to/title/${mangaId}-slug/${chapterId}-chapter-1`
      : `https://comix.to/title/${mangaId}-slug`;
    pagePath = chapterId
      ? `/title/${mangaId}-slug/${chapterId}-chapter-1`
      : `/title/${mangaId}-slug`;
  } else if (urlPath && (urlPath.startsWith('/manga') || urlPath.startsWith('/browse'))) {
    pageUrl = 'https://comix.to/browse';
    pagePath = '/browse';
  } else if (urlPath && urlPath.startsWith('/collections')) {
    pageUrl = 'https://comix.to/collections';
    pagePath = '/collections';
  }

  const mockLocation = createRecursiveProxy('location', {
    href: pageUrl,
    origin: 'https://comix.to',
    protocol: 'https:',
    host: 'comix.to',
    hostname: 'comix.to',
    port: '',
    pathname: pagePath,
    search: '',
    hash: '',
    replace: () => {},
    assign: () => {},
    reload: () => {},
    toString: () => pageUrl
  });

  const mockNavigator = createRecursiveProxy('navigator', {
    appCodeName: 'Mozilla',
    userAgent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
  });

  const mockFetch = async () => ({
    ok: true,
    status: 200,
    text: async () => '{"result": {}}',
    json: async () => ({ result: {} }),
    headers: new Map()
  });

  const windowOverrides = {
    document: createRecursiveProxy('document', documentOverrides),
    location: mockLocation,
    navigator: mockNavigator,
    fetch: mockFetch,
    Object, Array, String, Number, Boolean, RegExp, Date, Math, JSON,
    console: { log: () => {}, error: () => {}, warn: () => {} },
    setTimeout: () => 1,
    clearTimeout: () => {},
    setInterval: () => 1,
    clearInterval: () => {},
    Promise
  };

  const mockWindow = createRecursiveProxy('window', windowOverrides);
  mockWindow.window = mockWindow;
  mockWindow.self = mockWindow;
  mockWindow.global = mockWindow;

  const sandboxFunc = new Function(
    'window', 'document', 'location', 'navigator', 'fetch', 'self', 'global',
    processedJs
  );

  sandboxFunc(mockWindow, windowOverrides.document, mockLocation, mockNavigator, mockFetch, mockWindow, mockWindow);

  const builder = global.Lu || global.r;
  if (typeof builder !== 'function') {
    throw new Error('Failed to locate Axios interceptor builder in secure bundle');
  }

  const mockAxios = {
    interceptors: {
      request: {
        use: (success) => { mockAxios.requestInterceptor = success; }
      },
      response: {
        use: (success) => { mockAxios.responseInterceptor = success; }
      }
    },
    defaults: { headers: { common: {} } }
  };
  builder(mockAxios);
  return mockAxios;
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

let currentSecurePath = '';
let currentCfg = '';
let currentMangaId = '';

rl.on('line', async (line) => {
  if (!line.trim()) return;
  try {
    const msg = JSON.parse(line);
    const { id, action } = msg;

    if (action === 'init') {
      currentSecurePath = msg.securePath;
      currentCfg = msg.cfg;
      currentMangaId = msg.mangaId;
      console.log(JSON.stringify({ id, success: true }));
      return;
    }

    if (action === 'sign') {
      const { urlPath, params = {}, chapterId, mangaId } = msg;
      const targetMangaId = mangaId || currentMangaId;
      const axiosInstance = createAxiosSandbox(currentSecurePath, currentCfg, targetMangaId, chapterId, urlPath);
      const config = { url: urlPath, params: { ...params }, headers: {} };
      const resConfig = await axiosInstance.requestInterceptor(config);
      console.log(JSON.stringify({ id, success: true, params: resConfig.params }));
      return;
    }

    if (action === 'decrypt') {
      const { urlPath, data, chapterId, mangaId } = msg;
      const targetMangaId = mangaId || currentMangaId;
      const axiosInstance = createAxiosSandbox(currentSecurePath, currentCfg, targetMangaId, chapterId, urlPath);
      const decrypted = await axiosInstance.responseInterceptor({
        data,
        headers: { 'x-enc': '1' },
        config: { url: urlPath, baseURL: '/api/v1', method: 'get' }
      });
      console.log(JSON.stringify({ id, success: true, data: decrypted.data || decrypted }));
      return;
    }

    console.log(JSON.stringify({ id, success: false, error: 'Unknown action' }));
  } catch (err) {
    console.log(JSON.stringify({ success: false, error: err.message, stack: err.stack }));
  }
});
