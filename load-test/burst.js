// Burst test: N VUs fire one request each at the same client_id in a
// tight window. If the endpoint over-admits, `requests_admitted` in the
// summary exceeds the bucket capacity (plus the few tokens lazily
// refilled during the burst).
//
// Env:
//   URL        full endpoint URL (e.g. https://.../naive/check)
//   CLIENT_ID  bucket under test (default: burst-test)
//   VUS        concurrent requests (default: 100)
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const admitted = new Counter("requests_admitted");
const denied = new Counter("requests_denied");

export const options = {
  scenarios: {
    burst: {
      executor: "per-vu-iterations",
      vus: Number(__ENV.VUS || 100),
      iterations: 1,
    },
  },
};

export default function () {
  const clientId = __ENV.CLIENT_ID || "burst-test";
  const res = http.post(`${__ENV.URL}?client_id=${clientId}&cost=1`);

  check(res, { "responded 200 or 429": (r) => r.status === 200 || r.status === 429 });

  const body = JSON.parse(res.body);
  if (res.status === 200 && body.allowed === true) {
    admitted.add(1);
  } else {
    denied.add(1);
  }
}
