/**
 * notifications.js — колокольчик уведомлений в шапке
 *
 * Каждые 30 секунд запрашивает количество непрочитанных уведомлений.
 * При клике на колокольчик загружает список последних.
 */

(function () {
  'use strict';

  // Получить CSRF-токен из cookie
  function getCsrf() {
    const name = 'csrftoken';
    for (const cookie of document.cookie.split(';')) {
      const [k, v] = cookie.trim().split('=');
      if (k === name) return decodeURIComponent(v);
    }
    return '';
  }

  const badge    = document.getElementById('notifBadge');
  const listEl   = document.getElementById('notifList');
  const bellBtn  = document.getElementById('bellBtn');
  const markBtn  = document.getElementById('markAllReadBtn');

  if (!badge) return; // Вне авторизованной зоны

  // ── Обновить бейдж ────────────────────────────────────────────
  function updateBadge() {
    fetch('/notifications/count/', { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        const count = data.count || 0;
        if (count > 0) {
          badge.textContent = count > 99 ? '99+' : count;
          badge.classList.remove('d-none');
        } else {
          badge.classList.add('d-none');
        }
      })
      .catch(() => {});
  }

  // ── Загрузить последние уведомления в дропдаун ───────────────
  function loadRecent() {
    if (!listEl) return;
    listEl.innerHTML = '<div class="text-center text-muted py-3 small">Загрузка…</div>';

    fetch('/notifications/recent/', { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        const items = data.notifications || [];
        if (items.length === 0) {
          listEl.innerHTML =
            '<div class="text-center text-muted py-3 small">Новых уведомлений нет</div>';
          return;
        }
        listEl.innerHTML = items.map(n => `
          <div class="notif-item ${n.is_read ? '' : 'unread'}"
               onclick="location.href='${n.task_url || '#'}'">
            <div class="small">${escHtml(n.message)}</div>
            <div class="text-muted" style="font-size:.72rem;margin-top:2px">
              ${escHtml(n.created_at)}
            </div>
          </div>
        `).join('');
        // После просмотра сбросить бейдж
        badge.classList.add('d-none');
      })
      .catch(() => {
        listEl.innerHTML =
          '<div class="text-center text-danger py-3 small">Ошибка загрузки</div>';
      });
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Кнопка «Прочитать все» ────────────────────────────────────
  if (markBtn) {
    markBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      fetch('/notifications/mark-all-read/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': getCsrf() },
      })
      .then(() => {
        badge.classList.add('d-none');
        if (listEl) {
          listEl.innerHTML =
            '<div class="text-center text-muted py-3 small">Новых уведомлений нет</div>';
        }
      })
      .catch(() => {});
    });
  }

  // ── При открытии дропдауна — загрузить список ─────────────────
  if (bellBtn) {
    bellBtn.addEventListener('show.bs.dropdown', loadRecent);
  }

  // ── Первичный запрос + интервал ───────────────────────────────
  updateBadge();
  setInterval(updateBadge, 30_000);

})();
