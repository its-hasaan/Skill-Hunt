// Pings the API's /health on a cron so Render's free instance never sleeps
// (it spins down after 15 idle minutes). Replaces the GitHub Actions
// keep-warm, which would burn ~8,600 of a private repo's 2,000 monthly minutes.
export async function ping(env, fetchImpl = fetch) {
  const started = Date.now();
  try {
    const res = await fetchImpl(env.HEALTH_URL, { signal: AbortSignal.timeout(60_000) });
    return { ok: res.ok, status: res.status, ms: Date.now() - started };
  } catch (err) {
    return { ok: false, error: String(err), ms: Date.now() - started };
  }
}

export default {
  async scheduled(event, env, ctx) {
    const result = ping(env).then((r) => {
      console.log(JSON.stringify({ keepwarm: r }));
      return r;
    });
    ctx.waitUntil(result);
  },
};
