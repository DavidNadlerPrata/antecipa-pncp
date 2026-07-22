# ANTECIPA - Publica/sincroniza a pasta do projeto (Drive) no GitHub.
#
# A pasta do Drive e a fonte da verdade; o repositorio git vive num staging
# local persistente (fora do Drive, para nao sincronizar o .git). O script:
#   1. clona o repo no staging, se ainda nao existir;
#   2. espelha a pasta do projeto sobre o staging (robocopy /MIR, preservando
#      o .git e excluindo artefatos locais);
#   3. commita e faz push do que mudou.
#
# Uso:
#   .\publica_github.ps1                          # mensagem padrao com data
#   .\publica_github.ps1 -Mensagem "ajusta modelo v2"

param(
    [string]$Mensagem = "Sincroniza projeto ANTECIPA ($(Get-Date -Format 'yyyy-MM-dd'))"
)

$ErrorActionPreference = "Stop"
$repoUrl = "https://github.com/DavidNadlerPrata/antecipa-pncp.git"
$fonte   = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$staging = Join-Path $env:LOCALAPPDATA "antecipa-pncp"

# 1. staging persistente com o historico do repo
if (-not (Test-Path (Join-Path $staging ".git"))) {
    Write-Host "Clonando $repoUrl em $staging ..."
    git clone $repoUrl $staging
}

# 2. espelha a fonte sobre o staging (exclui .git e artefatos locais)
robocopy $fonte $staging /MIR /XD .git __pycache__ /XF .Rhistory README.html /NFL /NDL /NJH /NJS
if ($LASTEXITCODE -ge 8) { throw "robocopy falhou (codigo $LASTEXITCODE)" }
# codigos 0-7 do robocopy significam sucesso; zera para nao confundir o git
$global:LASTEXITCODE = 0

# 3. commit + push somente se houver mudanca
Set-Location $staging
git add -A
$mudancas = git status --porcelain
if (-not $mudancas) {
    Write-Host "Nada a publicar - repositorio ja esta em dia."
    return
}
Write-Host "Mudancas detectadas:" ($mudancas | Measure-Object -Line).Lines "arquivo(s)"
git commit -m $Mensagem
git push
Write-Host "Publicado: https://github.com/DavidNadlerPrata/antecipa-pncp"
