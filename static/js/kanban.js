/**
 * kanban.js — drag & drop для Канбан-доски
 *
 * Используется SortableJS.
 * CAN_DRAG и MOVE_URL объявляются в шаблоне kanban.html.
 */

(function () {
  'use strict';

  if (typeof CAN_DRAG === 'undefined' || !CAN_DRAG) return;
  if (typeof Sortable === 'undefined') {
    console.warn('SortableJS не загружен');
    return;
  }

  // Получить CSRF-токен из cookie
  function getCsrf() {
    const name = 'csrftoken';
    for (const cookie of document.cookie.split(';')) {
      const [k, v] = cookie.trim().split('=');
      if (k === name) return decodeURIComponent(v);
    }
    return '';
  }

  // Показать/скрыть подсказку «Нет задач» внутри колонки
  function refreshHint(colEl) {
    const hint  = colEl.querySelector('.kanban-drop-hint');
    const cards = colEl.querySelectorAll('.task-card');
    if (hint) hint.style.display = cards.length ? 'none' : '';
  }

  // Инициализируем Sortable на каждой колонке
  document.querySelectorAll('.kanban-col-body').forEach(function (col) {
    Sortable.create(col, {
      group:      'kanban',      // разрешаем перетаскивание между колонками
      animation:  160,
      ghostClass: 'sortable-ghost',
      chosenClass:'sortable-chosen',
      dragClass:  'sortable-drag',
      // Исключаем клики по ссылкам и кнопкам из триггера drag
      filter:     'a, button, .dropdown',
      preventOnFilter: false,

      onEnd: function (evt) {
        const card      = evt.item;
        const taskUuid  = card.dataset.taskUuid;
        const newCol    = evt.to;
        const newStatus = newCol.dataset.status;

        // Обновляем подсказки в исходной и целевой колонках
        refreshHint(evt.from);
        refreshHint(newCol);

        // Собираем упорядоченный список uuid задач в целевой колонке
        const colIds = Array.from(
          newCol.querySelectorAll('.task-card')
        ).map(c => c.dataset.taskUuid);

        // AJAX-запрос на сервер
        fetch(MOVE_URL(taskUuid), {
          method:  'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrf(),
          },
          body: JSON.stringify({
            status:     newStatus,
            column_ids: colIds,
          }),
        })
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (data) {
          if (!data.success) {
            console.error('Ошибка перемещения:', data.error);
            location.reload();
          } else {
            // Обновим бейдж счётчика в заголовке колонки
            updateColumnCount(evt.from);
            updateColumnCount(newCol);
          }
        })
        .catch(function (err) {
          console.error('Fetch error:', err);
          location.reload();
        });
      },
    });

    // Инициализируем подсказки
    refreshHint(col);
  });

  // Обновить счётчик задач в заголовке колонки
  function updateColumnCount(colEl) {
    const card  = colEl.closest('.kanban-column');
    if (!card) return;
    const badge = card.querySelector('.card-header .badge');
    if (badge) {
      badge.textContent = colEl.querySelectorAll('.task-card').length;
    }
  }

})();
