/// <reference path="../.astro/types.d.ts" />

/**
 * Build-time constant injected by astro.config.mjs (vite define) from
 * .claude-plugin/plugin.json — the plugin's source-of-truth manifest. Keeps
 * the site's rendered version stamps true by construction (DT-7).
 */
declare const __WICKED_GARDEN_VERSION__: string;
/** The SKILL.md count under skills/**, counted at build time by astro.config.mjs. */
declare const __WICKED_GARDEN_SKILLS__: number;
/** The work-shape count: the archetypes in .claude-plugin/archetypes.json, counted at build time. */
declare const __WICKED_GARDEN_WORK_SHAPES__: number;
/** The skills/qe-* dir names, sorted, listed at build time by astro.config.mjs (checked against the QE fleet in SSR). */
declare const __WICKED_GARDEN_QE_DIRS__: string[];
