/// <reference path="../.astro/types.d.ts" />

/**
 * Build-time constant injected by astro.config.mjs (vite define) from
 * .claude-plugin/plugin.json — the plugin's source-of-truth manifest. Keeps
 * the site's rendered version stamps true by construction (DT-7).
 */
declare const __WICKED_GARDEN_VERSION__: string;
