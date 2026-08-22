import { createInterface } from 'node:readline'

const lines = createInterface({ input: process.stdin })
for await (const line of lines) {
  const request = JSON.parse(line)
  if (process.env.EXIT_STDERR) {
    process.stderr.write(process.env.EXIT_STDERR)
    process.exit(17)
  }
  if (process.env.RPC_ERROR_MESSAGE) {
    process.stdout.write(`${JSON.stringify({
      jsonrpc: '2.0',
      id: request.id,
      error: { code: -32603, message: process.env.RPC_ERROR_MESSAGE },
    })}\n`)
    continue
  }
  if (process.env.HOLD_REQUEST) continue
  let result
  if (process.env.INVALID_METHOD === request.method) result = {}
  else if (request.method === 'health') result = { status: 'ok', pid: process.pid }
  else if (request.method === 'harness_status') {
    result = {
      run_id: request.params.run_id,
      status: 'active',
      risk_level: 'low',
      stability: 'insufficient_evidence',
      report_path: null,
      method: request.method,
      pid: process.pid,
    }
  } else if (request.method === 'harness_event') {
    result = { accepted: true, duplicate: false, method: request.method, pid: process.pid }
  } else result = { method: request.method, pid: process.pid, ...request.params }
  process.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', id: request.id, result })}\n`)
}
