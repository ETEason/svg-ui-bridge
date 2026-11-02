// Copy this folder to design/system. Run npm run build from that folder.
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { Settings } from './pages/settings';

for (const state of ['default', 'disabled'] as const) {
  const svg = renderToStaticMarkup(<Settings state={state} />);
  writeFileSync(fileURLToPath(new URL(`../settings.${state}.svg`, import.meta.url)), svg + '\n');
}
