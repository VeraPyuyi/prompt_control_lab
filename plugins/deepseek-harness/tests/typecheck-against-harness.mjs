import { createRequire } from 'node:module'
import { readdirSync } from 'node:fs'
import { isAbsolute, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const harnessRoot = process.env.DEEPSEEK_HARNESS_SOURCE
const typescriptPath = process.env.TYPESCRIPT_JS
if (!harnessRoot || !typescriptPath) {
  console.error('Set DEEPSEEK_HARNESS_SOURCE and TYPESCRIPT_JS to run the pinned source contract check.')
  process.exit(2)
}

const ts = require(typescriptPath)
const configPath = resolve(harnessRoot, 'tsconfig.base.json')
const loaded = ts.readConfigFile(configPath, ts.sys.readFile)
if (loaded.error) {
  console.error(ts.formatDiagnosticsWithColorAndContext([loaded.error], formatHost()))
  process.exit(1)
}
const parsed = ts.parseJsonConfigFileContent(loaded.config, ts.sys, harnessRoot, {
  noEmit: true,
  composite: false,
  incremental: false,
  rootDir: undefined,
  outDir: undefined,
  typeRoots: process.env.NODE_TYPE_ROOTS ? [process.env.NODE_TYPE_ROOTS] : undefined,
})
const sourceRoot = resolve(fileURLToPath(new URL('../src', import.meta.url)))
const rootNames = readdirSync(sourceRoot)
  .filter(name => name.endsWith('.ts'))
  .map(name => resolve(sourceRoot, name))
const program = ts.createProgram({ rootNames, options: parsed.options })
// The pinned source checkout may not have its workspace dependencies installed.
// Report this plugin's diagnostics only; Harness diagnoses its own source in its CI.
const diagnostics = ts.getPreEmitDiagnostics(program).filter(diagnostic => {
  if (!diagnostic.file) return true
  const path = relative(sourceRoot, resolve(diagnostic.file.fileName))
  return path === '' || (!path.startsWith('..') && !isAbsolute(path))
})
if (diagnostics.length > 0) {
  console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics, formatHost()))
  process.exit(1)
}
console.log(`TypeScript contract check passed against ${harnessRoot}`)

function formatHost() {
  return {
    getCanonicalFileName: path => path,
    getCurrentDirectory: () => process.cwd(),
    getNewLine: () => '\n',
  }
}
