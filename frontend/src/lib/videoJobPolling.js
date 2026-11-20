const terminal = new Set(["completed", "failed", "render_skipped"]);

export function hasActiveVideoJobs(jobs, lectureId) {
  return jobs.some((job) => job.lecture_id === lectureId && !terminal.has(job.status));
}

// Schedule after each response so slow requests cannot overlap.
export function pollVideoJobs(load, onError, timers = globalThis) {
  let cancelled = false;
  let timer;
  const schedule = () => {
    if (!cancelled) timer = timers.setTimeout(tick, 2500);
  };
  const tick = async () => {
    try { await load(); } catch (error) { if (!cancelled) onError(error); }
    schedule();
  };
  schedule();
  return () => { cancelled = true; timers.clearTimeout(timer); };
}
