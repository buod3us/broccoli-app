@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo ========================================
echo   Отправка на GitHub: только папка web\
echo ========================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Git не найден. Установите: https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist ".git" (
    echo [1/4] Инициализация git в этой папке...
    git init
    git branch -M main
    echo.
    echo ------------------------------------------------------------------
    echo  ПЕРВЫЙ РАЗ: создайте репозиторий на GitHub ^(без README^), затем выполните
    echo  в этой папке вручную ^(один раз^):
    echo.
    echo    git remote add origin https://github.com/buod3us/broccoli-app.git
    echo.
    echo  Замените URL на свой. После этого снова запустите этот bat.
    echo ------------------------------------------------------------------
    echo.
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Не настроен remote "origin".
    echo Выполните в этой папке:
    echo   git remote add origin https://github.com/buod3us/broccoli-app.git
    pause
    exit /b 1
)

if not exist "web\" (
    echo [ОШИБКА] Нет папки web\ рядом с этим bat.
    pause
    exit /b 1
)

echo [2/4] Добавление только папки web\ ...
git add -- web/

git diff --cached --quiet
if not errorlevel 1 (
    echo [ИНФО] В папке web\ нет новых изменений для коммита.
    echo.
    goto :try_push
)

echo [3/4] Коммит...
git commit -m "web: обновление %date% %time%"
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Коммит не создан. Один раз настройте имя и почту:
    echo   git config user.name "Ваше Имя"
    echo   git config user.email "email@example.com"
    pause
    exit /b 1
)

:try_push
echo [4/4] Отправка на GitHub ^(git push^)...
git push -u origin main
if errorlevel 1 (
    echo.
    echo Push на "main" не вышел. Пробую "master"...
    git push -u origin master
    if errorlevel 1 (
        echo.
        echo [ОШИБКА] Не удалось отправить. Проверьте:
        echo   - вход в GitHub ^(Personal Access Token вместо пароля^)
        echo   - правильность URL репозитория
        echo   - что ветка называется main или master: git branch
        pause
        exit /b 1
    )
)

echo.
echo ========================================
echo   Готово: изменения на GitHub.
echo ========================================
echo Если включён GitHub Pages для папки /web — подождите 1–2 минуты и обновите Mini App.
echo.
pause
endlocal
