function filterHistory() {
  const query = document.getElementById('historySearch').value.trim().toLowerCase();
  const category = document.getElementById('historyCategory').value;
  const cards = [...document.querySelectorAll('.history-card')];
  let visible = 0;
  cards.forEach(card => {
    const matchesQuery = !query || card.dataset.search.toLowerCase().includes(query);
    const matchesCategory = !category || card.dataset.category === category;
    card.classList.toggle('filtered-out', !(matchesQuery && matchesCategory));
    if (matchesQuery && matchesCategory) visible += 1;
  });
  document.getElementById('historyCount').textContent = `${visible} session${visible === 1 ? '' : 's'}`;
  document.getElementById('historyEmpty').classList.toggle('hidden', visible !== 0 || cards.length === 0);
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('historySearch').addEventListener('input', filterHistory);
  document.getElementById('historyCategory').addEventListener('change', filterHistory);
  document.querySelectorAll('.delete-session').forEach(button => {
    button.addEventListener('click', async () => {
      if (!window.confirm('Delete this session and all of its attempts?')) return;
      button.disabled = true;
      const response = await fetch(`/api/sessions/${button.dataset.sessionId}`, { method: 'DELETE' });
      if (!response.ok) {
        button.disabled = false;
        return;
      }
      button.closest('.history-card').remove();
      filterHistory();
    });
  });
});
