const state = {
  questions: [],
  current: null,
  sessionId: null,
  recognition: null,
  voiceBaseText: '',
  voiceFinalText: '',
  voiceRendering: false,
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail?.message || data.message || 'Request failed');
  return data;
}

async function loadQuestions() {
  const category = document.getElementById('categoryFilter').value;
  const data = await fetchJson(`/api/questions?category=${encodeURIComponent(category)}&limit=20`);
  state.questions = data.items;
  state.current = state.questions[Math.floor(Math.random() * state.questions.length)] || null;
  document.getElementById('questionCount').textContent = `${state.questions.length} questions available`;
  renderQuestion();
}

function renderQuestion() {
  const box = document.getElementById('questionBox');
  if (!state.current) {
    box.innerHTML = '<p class="muted">No question available for this category.</p>';
    return;
  }
  document.getElementById('questionDifficulty').textContent = state.current.difficulty || '';
  box.innerHTML = `<span class="question-category">${state.current.category}</span><h2>${state.current.question}</h2>`;
}

async function nextQuestion() {
  const category = document.getElementById('categoryFilter').value;
  const response = await fetchJson(`/api/questions?category=${encodeURIComponent(category || '')}&limit=20`);
  const list = response.items;
  if (list.length === 0) {
    document.getElementById('status').textContent = 'No matching questions available.';
    return;
  }
  state.questions = list;
  state.current = list[Math.floor(Math.random() * list.length)];
  document.getElementById('questionCount').textContent = `${list.length} questions available`;
  renderQuestion();
  document.getElementById('answerInput').focus();
}

async function ensureSession() {
  if (state.sessionId) return state.sessionId;
  const response = await fetchJson('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category: document.getElementById('categoryFilter').value || null }) });
  state.sessionId = response.session_id;
  window.localStorage.setItem('mockInterviewSessionId', state.sessionId);
  return state.sessionId;
}

async function submitAnswer() {
  const answer = document.getElementById('answerInput').value.trim();
  const status = document.getElementById('status');
  const feedbackEl = document.getElementById('feedback');
  if (!state.current) return;
  if (!answer) {
    status.textContent = 'Please enter an answer before submitting.';
    return;
  }
  status.textContent = 'Scoring your answer...';
  document.getElementById('submitButton').disabled = true;
  feedbackEl.classList.add('hidden');
  try {
    const sessionId = await ensureSession();
    const payload = { question_id: state.current.id, text: answer };
    const result = await fetchJson(`/api/sessions/${sessionId}/answers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    status.textContent = 'Feedback ready.';
    document.getElementById('attemptCount').textContent = Number(document.getElementById('attemptCount').textContent) + 1;
    feedbackEl.innerHTML = `
      <div class="feedback-header"><div><p class="eyebrow">Feedback ready</p><h2>Overall score: ${result.overall_score} <small>${result.overall_label || ''}</small></h2></div><a class="text-link" href="/session-summary">View session →</a></div>
      <p class="priority-callout"><strong>Next focus:</strong> ${result.priority_improvement?.dimension || 'overall answer quality'} (${result.priority_improvement?.score ?? ''})</p>
      <div class="feedback-metrics">
        <div><span>Relevance</span><strong>${result.relevance_score}</strong></div>
        <div><span>Completeness</span><strong>${result.completeness}</strong></div>
        <div><span>Keywords</span><strong>${result.keyword_coverage}</strong></div>
        <div><span>Fluency</span><strong>${result.fluency}</strong></div>
      </div>
      <div class="feedback-columns">
      <div><h3>Strengths</h3><ul>${result.strengths.map(item => `<li>${item}</li>`).join('')}</ul></div>
      <div><h3>Suggestions</h3><ul>${result.suggestions.map(item => `<li>${item}</li>`).join('')}</ul></div>
      </div>
      ${result.gaps?.length ? `<h3>Gaps to close</h3><ul>${result.gaps.map(item => `<li>${item}</li>`).join('')}</ul>` : ''}
      ${result.uncovered_points?.length ? `<h3>Points to cover</h3><ul>${result.uncovered_points.slice(0, 3).map(item => `<li>${item}</li>`).join('')}</ul>` : ''}
    `;
    feedbackEl.classList.remove('hidden');
  } catch (error) {
    status.textContent = error.message;
  } finally {
    document.getElementById('submitButton').disabled = false;
  }
}

function init() {
  document.getElementById('nextQuestion').addEventListener('click', nextQuestion);
  document.getElementById('submitButton').addEventListener('click', submitAnswer);
  document.getElementById('categoryFilter').addEventListener('change', () => {
    state.sessionId = null;
    loadQuestions().catch(err => { document.getElementById('status').textContent = err.message; });
  });
  document.getElementById('answerInput').addEventListener('input', event => {
    const words = event.target.value.trim() ? event.target.value.trim().split(/\s+/).length : 0;
    document.getElementById('wordCount').textContent = `${words} word${words === 1 ? '' : 's'}`;
  });
  document.getElementById('answerInput').addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') submitAnswer();
  });
  document.getElementById('clearButton').addEventListener('click', () => {
    document.getElementById('answerInput').value = '';
    document.getElementById('wordCount').textContent = '0 words';
    document.getElementById('answerInput').focus();
  });
  document.getElementById('micButton').addEventListener('click', toggleVoiceInput);
  window.addEventListener('pagehide', stopVoiceInput);
  loadQuestions().catch(err => {
    document.getElementById('status').textContent = err.message;
  });
}

function joinAnswerParts(...parts) {
  return parts.map(part => part.trim()).filter(Boolean).join(' ').trim();
}

function updateWordCount() {
  const answer = document.getElementById('answerInput').value.trim();
  const words = answer ? answer.split(/\s+/).length : 0;
  document.getElementById('wordCount').textContent = `${words} word${words === 1 ? '' : 's'}`;
}

function setVoiceButton(recording) {
  const button = document.getElementById('micButton');
  button.textContent = recording ? 'Stop listening' : 'Start voice input';
  button.classList.toggle('recording', recording);
  button.setAttribute('aria-pressed', String(recording));
}

function stopVoiceInput() {
  if (!state.recognition) return;
  state.recognition.stop();
}

function toggleVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const status = document.getElementById('status');
  if (state.recognition) {
    stopVoiceInput();
    return;
  }
  if (!SpeechRecognition) {
    status.textContent = 'Voice input is not supported in this browser. You can type your answer instead.';
    return;
  }

  const recognition = new SpeechRecognition();
  state.recognition = recognition;
  state.voiceBaseText = document.getElementById('answerInput').value.trim();
  state.voiceFinalText = '';
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = 'en-IN';
  recognition.onstart = () => {
    setVoiceButton(true);
    status.textContent = 'Listening in English (India)… speak clearly, then click Stop listening.';
  };
  recognition.onresult = event => {
    let interimText = '';
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = event.results[index][0].transcript.trim();
      if (event.results[index].isFinal) state.voiceFinalText = joinAnswerParts(state.voiceFinalText, transcript);
      else interimText = joinAnswerParts(interimText, transcript);
    }
    const answer = joinAnswerParts(state.voiceBaseText, state.voiceFinalText);
    state.voiceRendering = true;
    document.getElementById('answerInput').value = answer;
    document.getElementById('transcriptBox').textContent = interimText ? `Listening: ${interimText}` : state.voiceFinalText;
    updateWordCount();
    state.voiceRendering = false;
  };
  recognition.onerror = event => {
    const messages = {
      'not-allowed': 'Microphone permission was denied. Allow microphone access for localhost and try again.',
      'audio-capture': 'No microphone was found. Connect a microphone and try again.',
      'network': 'The browser speech service is unavailable. Check your connection or type your answer instead.',
      'no-speech': 'No speech was detected. Try again and speak closer to the microphone.',
    };
    status.textContent = messages[event.error] || `Voice input failed (${event.error}). You can type your answer instead.`;
  };
  recognition.onend = () => {
    state.recognition = null;
    setVoiceButton(false);
    const answer = joinAnswerParts(state.voiceBaseText, state.voiceFinalText);
    if (answer) {
      state.voiceRendering = true;
      document.getElementById('answerInput').value = answer;
      updateWordCount();
      state.voiceRendering = false;
      document.getElementById('transcriptBox').textContent = state.voiceFinalText;
      status.textContent = 'Voice input added. Review and edit your answer before submitting.';
    }
  };
  try {
    recognition.start();
  } catch (error) {
    state.recognition = null;
    setVoiceButton(false);
    status.textContent = 'Voice input could not start. Check microphone permissions and try again.';
  }
}

window.addEventListener('DOMContentLoaded', init);
