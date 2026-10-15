#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Faz o LoL Remoto iniciar sozinho (sem janela) quando voce entra no Windows.

.DESCRIPTION
    1. Na primeira instalacao, pede o PIN de acesso (so o hash fica salvo) e cria o topico do ntfy.
    2. Registra a tarefa "LoL Remoto" no Agendador de Tarefas (gatilho: logon do usuario atual).
    3. Cria a regra de firewall liberando a porta do app e a do --simular (porta + 1)
       apenas para a rede do Tailscale (100.64.0.0/10).
    4. Inicia a tarefa, mostra o endereco para o celular e oferece uma notificacao de teste.
    Ver docs/decisoes/0011-instalacao-como-tarefa-no-logon.md.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
#>
$ErrorActionPreference = "Stop"
$NomeTarefa = "LoL Remoto"
$NomeRegra = "LoL Remoto (Tailscale)"
$RedeTailscale = "100.64.0.0/10"
$PastaSrc = (Resolve-Path (Join-Path $PSScriptRoot "..\src")).Path
$ArquivoConfig = Join-Path $env:APPDATA "LolRemoto\config.json"
$ArquivoLog = Join-Path $env:LOCALAPPDATA "LolRemoto\lol-remoto.log"

Write-Host "==> Localizando o Python..." -ForegroundColor Cyan
$python = (& py -c "import sys; print(sys.executable)").Trim()
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "pythonw.exe nao encontrado em '$pythonw'. Instale o Python pelo python.org."
}
Write-Host "    $pythonw"

# Sem config, o app criaria um PIN aleatorio e o mostraria num console que nao existe
# (a tarefa roda sem janela). Por isso o PIN e definido aqui, antes.
if (-not (Test-Path $ArquivoConfig)) {
    Write-Host "==> Defina o PIN de acesso (so o hash fica salvo)..." -ForegroundColor Cyan
    Push-Location $PastaSrc
    try { & $python -m lol_remoto --trocar-pin } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "O PIN nao foi definido. Rode o instalador de novo." }
} else {
    Write-Host "==> Configuracao existente mantida ($ArquivoConfig)" -ForegroundColor Cyan
}
$config = Get-Content $ArquivoConfig -Raw | ConvertFrom-Json
$porta = if ($config.porta) { [int]$config.porta } else { 8766 }
$portaSimulacao = $porta + 1

Write-Host "==> Registrando a tarefa '$NomeTarefa'..." -ForegroundColor Cyan
$usuario = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "-m lol_remoto" -WorkingDirectory $PastaSrc
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$ajustes = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $NomeTarefa -Action $acao -Trigger $gatilho `
    -Principal $principal -Settings $ajustes -Force `
    -Description "Servidor do LoL Remoto (fila e selecao de campeoes pelo celular via Tailscale)." | Out-Null

Write-Host "==> Criando regra de firewall (portas $porta e $portaSimulacao, somente Tailscale)..." -ForegroundColor Cyan
Get-NetFirewallRule -DisplayName $NomeRegra -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $NomeRegra -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort @("$porta", "$portaSimulacao") -RemoteAddress $RedeTailscale `
    -Profile Any | Out-Null

Write-Host "==> Iniciando..." -ForegroundColor Cyan
Stop-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $NomeTarefa
Start-Sleep -Seconds 3

$ouvindo = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue
if (-not $ouvindo) {
    Write-Warning "O app nao abriu a porta $porta. Se ele estiver aberto num terminal, feche-o e rode scripts\reiniciar.ps1. Log: $ArquivoLog"
}

$ipTailscale = $null
if (Get-Command tailscale -ErrorAction SilentlyContinue) {
    $ipTailscale = (& tailscale ip -4 2>$null | Select-Object -First 1)
}

Write-Host ""
Write-Host "Pronto! O LoL Remoto vai iniciar sozinho sempre que voce entrar no Windows." -ForegroundColor Green
Write-Host "  PIN:      o que voce definiu. Para trocar: cd src; py -m lol_remoto --trocar-pin"
Write-Host "  Neste PC: http://localhost:$porta"
if ($ipTailscale) {
    Write-Host "  Celular:  http://${ipTailscale}:$porta   (simulacao: http://${ipTailscale}:$portaSimulacao)"
} else {
    Write-Warning "Tailscale nao encontrado. Instale em https://tailscale.com/download para acessar pelo celular."
}
Write-Host "  Depois de atualizar o codigo: scripts\reiniciar.ps1"
Write-Host "  Log:      $ArquivoLog"

$resposta = Read-Host "Mandar uma notificacao de teste para o celular agora? (s/N)"
if ($resposta -match "^[sS]") {
    Push-Location $PastaSrc
    try { & $python -m lol_remoto --testar-notificacao } finally { Pop-Location }
}
