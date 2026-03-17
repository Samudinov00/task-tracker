# Заметки для Claude

## Деплой и статические файлы

При деплое с изменениями CSS/JS/шаблонов нужно удалять volume `staticfiles`, иначе nginx продолжает отдавать старые файлы даже после пересборки контейнера:

```bash
docker compose down
docker volume rm task-tracker_staticfiles
docker compose build web
docker compose up -d
```

Без этого шага изменения дизайна не появятся на сайте.
