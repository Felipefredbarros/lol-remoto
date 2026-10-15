#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Remove a tarefa de inicializacao e a regra de firewall do LoL Remoto.

.DESCRIPTION
    A configuracao (PIN, topico do ntfy, sessoes) em %APPDATA%\LolRemoto e os logs e icones
    em %LOCALAPPDATA%\LolRemoto sao mantidos. Apague essas pastas manualmente se quiser
    remover tudo.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\desinstalar.ps1
#>
$ErrorActionPreference = "Stop"
$NomeTarefa = "LoL Remoto"
$NomeRegra = "LoL Remoto (Tailscale)"

if (Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $NomeTarefa
    Unregister-ScheduledTask -TaskName $NomeTarefa -Confirm:$false
    Write-Host "Tarefa '$NomeTarefa' removida."
} else {
    Write-Host "Tarefa '$NomeTarefa' nao estava instalada."
}

Get-NetFirewallRule -DisplayName $NomeRegra -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Write-Host "Regra de firewall '$NomeRegra' removida (se existia)."
Write-Host "Config mantida em $env:APPDATA\LolRemoto e logs em $env:LOCALAPPDATA\LolRemoto."
