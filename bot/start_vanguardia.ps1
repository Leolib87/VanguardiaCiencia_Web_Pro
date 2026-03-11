# LANZADOR DUAL VANGUARDIA CIENCIA (WEB + BOT EDITOR)
# Creado por Gemini CLI para Leandro Torres (Marzo 2026)

$AstroRoot = "C:\Users\leoli\BOTS_SYSTEM\VanguardiaCiencia_Web"
$BotRoot = "C:\Users\leoli\BOTS_SYSTEM\VanguardiaCiencia_Web\bot"

Write-Host "Iniciando Ecosistema Vanguardia Ciencia..." -ForegroundColor Cyan

# 1. Iniciar Servidor Web Astro (dev) de forma invisible/segundo plano
Write-Host "Lanzando Servidor Web Astro (Localhost)..." -ForegroundColor Green
Set-Location $AstroRoot
Start-Process "npm" -ArgumentList "run dev" -WindowStyle Hidden

# 2. Iniciar Bot Editor (publisher.py)
Write-Host "Lanzando Bot Editor (Instancia Gemini Aislada)..." -ForegroundColor Green
$env:GEMINI_CLI_HOME = $BotRoot
Set-Location $BotRoot
Start-Process "python" -ArgumentList "publisher.py" -WindowStyle Hidden

Write-Host "Ecosistema Vanguardia Ciencia iniciado con éxito." -ForegroundColor Yellow
