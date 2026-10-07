# Как поднять сайт через GitHub Pages

Репозиторий: https://github.com/surok111/GENOMIQ-
HTML сайта: `docs/index.html`

Сайт будет доступен по адресу: https://surok111.github.io/GENOMIQ-/

GitHub Pages умеет публиковать папку `/docs` напрямую, поэтому workflow и дополнительные файлы не нужны.

## Шаги

### 1. Главная страница должна называться `index.html`

Файл `docs/genomiq_site.html` переименован в `docs/index.html`
(иначе будет 404 по основному адресу).

### 2. Загрузите изменения на GitHub

```powershell
git add .
git commit -m "Add site to docs"
git push origin main
```

### 3. Включите Pages

1. Откройте репозиторий на GitHub -> **Settings** -> **Pages**.
2. **Build and deployment** -> **Source**: **Deploy from a branch**.
3. **Branch**: `main`, папка: **/docs** -> **Save**.

### 4. Дождитесь публикации

1. Вкладка **Actions** -> workflow "pages build and deployment" должен стать зелёным (1–3 минуты).
2. Адрес сайта появится вверху страницы Settings -> Pages.
3. Откройте https://surok111.github.io/GENOMIQ-/

Дальше каждый `git push` в `main` автоматически обновляет сайт.

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| 404 по адресу сайта | Файл не называется `index.html`, или Pages ещё не развернулся, или выбрана не папка `/docs` |
| Нет стилей/картинок | Используйте относительные пути (`style.css`, а не `/style.css`): сайт живёт в подпути `/GENOMIQ-/` |
| Старая версия сайта | Подождите пару минут и обновите страницу через Ctrl+F5 |
| Приватный репозиторий | Pages для приватных репо доступны только на платных тарифах |
| Своё доменное имя | Settings -> Pages -> Custom domain, плюс CNAME-запись у регистратора |

## Локальная проверка перед пушем

```powershell
cd docs
python -m http.server 8000
```

Откройте http://localhost:8000
