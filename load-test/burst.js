// Burst test: VUS concurrent workers each fire ITERS back-to-back
// requests at the same client_id. If the endpoint over-admits,
// `requests_admitted` in the summary exceeds the bucket capacity (plus
// the few tokens lazily refilled during the burst).
//
// VUS defaults to 10 because free-plan AWS accounts cap Lambda at 10
// concurrent executions — more VUs just get throttled into 500s, which
// pollutes the comparison. 10 truly concurrent racers is enough to
// demonstrate the read-then-write race.
//
// Env:
//   URL        full endpoint URL (e.g. https://.../naive/check)
//   CLIENT_ID  bucket under test (default: burst-test)
//   VUS        concurrent workers (default: 10)
//   ITERS      requests per worker (default: 10)
import http from "k6/http";
import { check } from "k6";
import { Counter, Trend } from "k6/metrics";

const admitted = new Counter("requests_admitted");
const denied = new Counter("requests_denied");
const casRetries = new Trend("cas_retries");

export const options = {
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
  scenarios: {
    burst: {
      executor: "per-vu-iterations",
      vus: Number(__ENV.VUS || 10),
      iterations: Number(__ENV.ITERS || 10),
    },
  },
};

export default function () {
  const clientId = __ENV.CLIENT_ID || "burst-test";
  const res = http.post(`${__ENV.URL}?client_id=${clientId}&cost=1`);

  check(res, { "responded 200 or 429": (r) => r.status === 200 || r.status === 429 });

  const body = JSON.parse(res.body);
  if (body.retries !== undefined) casRetries.add(body.retries);
  if (res.status === 200 && body.allowed === true) {
    admitted.add(1);
  } else {
    denied.add(1);
  }
}
