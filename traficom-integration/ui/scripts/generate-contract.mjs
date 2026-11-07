// Generates TypeScript from the shared contract: API types from openapi.json, plus the valid
// fixtures wrapped in `satisfies`, so `tsc` proves they fit those types. With --check, nothing is
// written and the script fails if a committed file is out of date.
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const uiDir = join(dirname(fileURLToPath(import.meta.url)), "..");
const contractDir = join(uiDir, "..", "contract");
const header = "// GENERATED from traficom-integration/contract. Do not edit.\n";

async function schemaSource() {
  const ast = await openapiTS(pathToFileURL(join(contractDir, "openapi.json")));
  return header + astToString(ast);
}

function fixturesSource() {
  const validDir = join(contractDir, "fixtures", "valid");
  const lines = [header, 'import type { components } from "../schema.gen";', ""];
  for (const [index, file] of readdirSync(validDir).sort().entries()) {
    const model = file.split(".")[0];
    const json = readFileSync(join(validDir, file), "utf-8").trim();
    lines.push(`// ${file}`);
    lines.push(`export const fixture${index} = ${json} satisfies components["schemas"]["${model}"];`);
    lines.push("");
  }
  return lines.join("\n");
}

const outputs = [
  [join(uiDir, "src", "api", "schema.gen.ts"), await schemaSource()],
  [join(uiDir, "src", "api", "__contract__", "fixtures.gen.ts"), fixturesSource()],
];

const check = process.argv.includes("--check");
let stale = false;
for (const [path, source] of outputs) {
  if (check) {
    let current = null;
    try {
      current = readFileSync(path, "utf-8");
    } catch {
      // A missing file is reported as out of date below.
    }
    if (current !== source) {
      console.error(`${path} is out of date; run: npm run contract:generate`);
      stale = true;
    }
  } else {
    writeFileSync(path, source);
  }
}
process.exit(stale ? 1 : 0);
