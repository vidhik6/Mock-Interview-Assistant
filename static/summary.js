function formatScore(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : '—';
}

function parseScore(value) {
  try {
    return JSON.parse(value || '{}');
  } catch {
    // Sessions created before JSON storage used Python's dict representation.
    const legacy = (value || '{}')
      .replace(/\bNone\b/g, 'null')
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
      .replace(/'/g, '"');
    return JSON.parse(legacy);
  }
}

function scoreClass(value) {
  if (Number(value) >= 70) return 'score-good';
  if (Number(value) >= 50) return 'score-mid';
  return 'score-low';
}

function renderSummary(data) {
  const attempts = data.attempts || [];
  const parsed = attempts.map(attempt => ({ ...attempt, score: parseScore(attempt.score) }));
  const latest = parsed[parsed.length - 1]?.score || {};
  const average = parsed.length
    ? parsed.reduce((sum, attempt) => sum + Number(attempt.score.overall_score || 0), 0) / parsed.length
    : 0;

  document.getElementById('sessionTitle').textContent = `${data.category || 'Mixed'} interview`;
  document.getElementById('sessionMeta').textContent = `${attempts.length} attempt${attempts.length === 1 ? '' : 's'} · Session ${data.session_id.slice(0, 8)}`;
  document.getElementById('sessionScore').textContent = formatScore(average);

  const metrics = [
    ['Average score', average, ''],
    ['Relevance', latest.relevance_score, ''],
    ['Completeness', latest.completeness, ''],
    ['Fluency', latest.fluency, ''],
  ];
  document.getElementById('summaryStats').innerHTML = metrics.map(([label, value]) => `
    <article class="metric-card">
      <span>${label}</span>
      <strong class="${scoreClass(value)}">${formatScore(value)}</strong>
      <small>out of 100</small>
    </article>
  `).join('');

  document.getElementById('attemptList').innerHTML = parsed.length
    ? parsed.map((attempt, index) => `
      <article class="attempt-item">
        <div>
          <span class="attempt-number">0${index + 1}</span>
          <strong>${attempt.category || 'Interview'} response</strong>
          <p>${attempt.answer.slice(0, 150)}${attempt.answer.length > 150 ? '…' : ''}</p>
        </div>
        <strong class="attempt-score ${scoreClass(attempt.score.overall_score)}">${formatScore(attempt.score.overall_score)}</strong>
      </article>
    `).join('')
    : '<p class="muted">No answers have been submitted in this session yet.</p>';

  const focus = latest.priority_improvement;
  document.getElementById('focusTitle').textContent = focus?.dimension || 'Keep practicing';
  document.getElementById('focusText').textContent = focus
    ? `Your latest response scored ${formatScore(focus.score)} in this area. Review the feedback and try one more answer with that dimension in mind.`
    : 'Submit an answer during practice to receive a personalized focus area.';
  document.getElementById('summaryContent').classList.remove('hidden');
}

async function loadSummary() {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session_id') || window.localStorage.getItem('mockInterviewSessionId') || window.SUMMARY_SESSION_ID;
  const status = document.getElementById('summaryStatus');
  if (!sessionId) {
    status.textContent = 'No sessions yet. Start a practice session to see your summary here.';
    return;
  }
  try {
    const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail?.message || 'Unable to load this session.');
    renderSummary(data);
    status.classList.add('hidden');
  } catch (error) {
    status.textContent = error.message;
  }
}

window.addEventListener('DOMContentLoaded', loadSummary);
