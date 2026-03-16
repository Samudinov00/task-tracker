/**
 * notifications.js — колокольчик уведомлений в шапке
 *
 * Каждые 30 секунд запрашивает количество непрочитанных уведомлений.
 * Синхронизирует десктопный и мобильный колокольчики.
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

  // Ссылки на десктопный и мобильный варианты
  const badges   = [document.getElementById('notifBadge'), document.getElementById('notifBadgeMob')].filter(Boolean);
  const listEls  = { desk: document.getElementById('notifList'), mob: document.getElementById('notifListMob') };
  const bellBtns = [document.getElementById('bellBtn'), document.getElementById('bellBtnMob')].filter(Boolean);
  const markBtns = [document.getElementById('markAllReadBtn'), document.getElementById('markAllReadBtnMob')].filter(Boolean);

  if (badges.length === 0) return; // Вне авторизованной зоны

  // ── Обновить все бейджи ───────────────────────────────────────
  function updateBadge() {
    fetch('/notifications/count/', { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        const count = data.count || 0;
        const txt   = count > 99 ? '99+' : String(count);
        badges.forEach(b => {
          if (count > 0) { b.textContent = txt; b.classList.remove('d-none'); }
          else           { b.classList.add('d-none'); }
        });
      })
      .catch(() => {});
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Загрузить последние уведомления в указанный список ───────
  function loadRecent(listEl) {
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
          <div class="notif-item ${n.is_read ? '' : 'unread'}" data-url="${escHtml(n.task_url || '')}">
            <div class="small">${escHtml(n.message)}</div>
            <div class="text-muted" style="font-size:.72rem;margin-top:2px">
              ${escHtml(n.created_at)}
            </div>
          </div>
        `).join('');
        listEl.querySelectorAll('.notif-item[data-url]').forEach(el => {
          const url = el.dataset.url;
          if (url) el.addEventListener('click', () => { location.href = url; });
        });
        badges.forEach(b => b.classList.add('d-none'));
      })
      .catch(() => {
        listEl.innerHTML =
          '<div class="text-center text-danger py-3 small">Ошибка загрузки</div>';
      });
  }

  // ── Кнопки «Прочитать все» ────────────────────────────────────
  markBtns.forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      fetch('/notifications/mark-all-read/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': getCsrf() },
      })
      .then(() => {
        badges.forEach(b => b.classList.add('d-none'));
        Object.values(listEls).forEach(el => {
          if (el) el.innerHTML =
            '<div class="text-center text-muted py-3 small">Новых уведомлений нет</div>';
        });
      })
      .catch(() => {});
    });
  });

  // ── При открытии дропдаунов — загрузить список ───────────────
  const bellBtnDesk = document.getElementById('bellBtn');
  const bellBtnMob  = document.getElementById('bellBtnMob');
  if (bellBtnDesk) bellBtnDesk.addEventListener('show.bs.dropdown', () => loadRecent(listEls.desk));
  if (bellBtnMob)  bellBtnMob.addEventListener('show.bs.dropdown',  () => loadRecent(listEls.mob));

  // ── Первичный запрос + интервал ───────────────────────────────
  updateBadge();
  setInterval(updateBadge, 30_000);

})();
