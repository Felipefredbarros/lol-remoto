<#
.SYNOPSIS
    Reinicia o LoL Remoto instalado (para usar o codigo novo depois de atualizar).

.DESCRIPTION
    So para e inicia a tarefa "LoL Remoto"; nao mexe em firewall, PIN nem configuracao.
    Se o Windows recusar, rode este script como administrador.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\reiniciar.ps1
#>
$ErrorActionPreference = "Stop"
$NomeTarefa = "LoL Remoto"

if (-not (Get-ScheduledTask -TaskName $NomeTarefa -ErrorAction SilentlyContinue)) {
    Write-Warning "A tarefa '$NomeTarefa' nao esta instalada. Rode scripts\instalar.ps1 como administrador."
    exit 1
}
Stop-ScheduledTask -TaskName $NomeTarefa
Start-ScheduledTask -TaskName $NomeTarefa
Write-Host "LoL Remoto reiniciado." -ForegroundColor Green
