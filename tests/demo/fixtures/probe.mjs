#!/usr/bin/env node
// Probe script for walkthrough integration tests.
// Reads DATA_DIR/run.json and outputs JSON to stdout.
import fs from "node:fs";
import path from "node:path";

const DATA_DIR = process.env.DATA_DIR || "./data";
const runFile = path.join(DATA_DIR, "run.json");

if (!fs.existsSync(runFile)) {
  process.stdout.write(JSON.stringify({ exists: false }) + "\n");
  process.exit(0);
}

const data = JSON.parse(fs.readFileSync(runFile, "utf8"));
process.stdout.write(JSON.stringify({ exists: true, ran_at: data.ran_at }) + "\n");
