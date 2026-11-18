// Read-only identity/hash preflight for the explicitly authorized connector update.
// This does not edit EasyEDA design objects, permissions, or IndexedDB records.
const expectedUuid = '4dae27407c1d43be98e8e210d45fe587';
const sha = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join('');
const candidates = [];
for (const entry of await indexedDB.databases()) {
  if (!entry.name || !/^User_.+_v6$/.test(entry.name)) continue;
  const db = await new Promise((resolve, reject) => {
    const request = indexedDB.open(entry.name);
    request.onupgradeneeded = () => { request.transaction.abort(); reject(new Error('Refusing database creation/upgrade')); };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  try {
    if (!db.objectStoreNames.contains('extensionsIndex') || !db.objectStoreNames.contains('extensionsObjectStorage')) continue;
    const tx = db.transaction(['extensionsIndex', 'extensionsObjectStorage'], 'readonly');
    const get = (store, key) => new Promise((resolve, reject) => {
      const request = tx.objectStore(store).get(key);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const [index, record] = await Promise.all([get('extensionsIndex', expectedUuid), get('extensionsObjectStorage', `${expectedUuid}|dist/index.js`)]);
    if (!index || !record?.source || index.config?.uuid !== expectedUuid) continue;
    candidates.push({
      team: entry.name.slice(5, -3),
      uuid: expectedUuid,
      version: index.config.version,
      enabled: index.isEnable,
      allowExternalInteractions: index.isAllowExternalInteractions,
      installedBundleSha256: await sha(await record.source.arrayBuffer()),
      installedBundleBytes: record.source.size,
    });
  } finally { db.close(); }
}
return { candidates };
