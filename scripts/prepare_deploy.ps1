[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSourceSha,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')][string]$Release,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$source = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$target = [IO.Path]::GetFullPath('C:\dev\sipe_sipe_biometric_api_deploy').TrimEnd('\')
$utf8 = [Text.UTF8Encoding]::new($false)

function Git-Source {
    $out = & git -c "safe.directory=$($source.Replace('\','/'))" -C $source @args
    if ($LASTEXITCODE -ne 0) { throw 'Falló la comprobación Git del desarrollo.' }
    return $out
}
function Git-Target {
    $out = & git -c "safe.directory=$($target.Replace('\','/'))" -C $target @args
    if ($LASTEXITCODE -ne 0) { throw 'Falló la comprobación Git del repositorio deploy.' }
    return $out
}
function Write-Utf8([string]$path, [string]$content) {
    [IO.Directory]::CreateDirectory((Split-Path -Parent $path)) | Out-Null
    [IO.File]::WriteAllText($path, $content, $utf8)
}
function Assert-NoLinks([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    if ((Get-Item -Force -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "No se permiten enlaces en el runtime: $path"
    }
    $links = @(Get-ChildItem -Force -Recurse -LiteralPath $path |
        Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
    if ($links.Count -gt 0) { throw "Hay enlaces dentro de $path; no se eliminará ni copiará." }
}
function Clear-Runtime([string]$relative) {
    if ($relative -ne 'backend/app') { throw 'Destino de limpieza no permitido.' }
    $absolute = [IO.Path]::GetFullPath((Join-Path $target $relative))
    if (-not $absolute.StartsWith($target + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'La limpieza sale del repositorio deploy.'
    }
    Assert-NoLinks $absolute
    if (Test-Path -LiteralPath $absolute) { Remove-Item -LiteralPath $absolute -Recurse -Force }
    [IO.Directory]::CreateDirectory($absolute) | Out-Null
}

if ($source -ne 'C:\dev\sipe_sipe_biometric_api') { throw 'Este preparador solo opera en el desarrollo autorizado.' }
foreach ($root in @($source, $target)) {
    if (-not (Test-Path -LiteralPath (Join-Path $root '.git'))) { throw "No existe el repositorio: $root" }
    if ((Get-Item -Force -LiteralPath $root).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'No usar repositorios enlazados.' }
}
if ((Git-Source branch --show-current) -ne 'develop') { throw 'Se requiere develop.' }
$sha = Git-Source rev-parse HEAD
if ($sha -ne $ExpectedSourceSha) { throw "SHA inesperado: $sha" }
if (-not $Release) { $Release = 'qa-' + $sha.Substring(0, 12) }

# Un release sólo puede copiar código ya confirmado.
$runtimePaths = @('app', 'requirements.txt')
$dirty = @(Git-Source status --porcelain --untracked-files=all -- @runtimePaths)
if ($dirty.Count -gt 0) { throw 'Hay cambios funcionales sin commit en los orígenes runtime. Revisarlos antes de preparar.' }
Assert-NoLinks (Join-Path $source 'app')
Assert-NoLinks (Join-Path $target 'backend/app')

$runtimeFiles = @(Git-Source ls-files -- app requirements.txt)
if ($runtimeFiles.Count -lt 10) { throw 'Inventario runtime incompleto.' }
foreach ($relative in $runtimeFiles) {
    if ($relative -match '(^|/)(\.env[^/]*|__pycache__|tests?[^/]*)(/|$)|\.(pyc|pyo|dump|pem|key)$') {
        throw "Archivo no permitido en runtime: $relative"
    }
}
if ($ValidateOnly) {
    Write-Output "Validación sin cambios: develop $sha; $($runtimeFiles.Count) archivos runtime; destino $target"
    return
}

# Copiar sólo el runtime confirmado; nunca .git, .env, tests ni secretos.
foreach ($relative in @('backend/app')) { Clear-Runtime $relative }
foreach ($relative in $runtimeFiles) {
    $destination = Join-Path $target $relative
    [IO.Directory]::CreateDirectory((Split-Path -Parent $destination)) | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $destination
}
$template = [IO.File]::ReadAllText((Join-Path $source 'deploy/Dockerfile.backend.runtime'))
Write-Utf8 (Join-Path $target 'backend/Dockerfile') ($template.Replace('__SOURCE_SHA__', $sha).Replace('__RELEASE__', $Release))
$manifest = [ordered]@{
    release = $Release
    source_sha = $sha
    source_branch = 'develop'
    build_date = [DateTimeOffset]::UtcNow.ToString('o')
    status = 'prepared'
    notes = 'Runtime copiado desde sipe-sipe-biometric-api en develop; sin despliegue ni publicacion.'
}
Write-Utf8 (Join-Path $target 'release.json') (($manifest | ConvertTo-Json) + "`n")

# Verificar la entrega, no sólo el contexto local: lo ignorado desaparecería al hacer pull.
$deliveryPaths = @($runtimeFiles) + @('backend/Dockerfile', 'release.json')
$ignored = @($deliveryPaths | Git-Target check-ignore --stdin)
if ($LASTEXITCODE -gt 1) { throw 'No se pudo verificar la inclusión Git del runtime.' }
if ($ignored.Count -gt 0) { throw ("Git está excluyendo runtime necesario: " + ($ignored -join ', ')) }
Write-Output "Runtime preparado desde $sha. Sin commit ni push. Falta smoke local del deploy."
& git -c "safe.directory=$($target.Replace('\','/'))" -C $target diff --stat
& git -c "safe.directory=$($target.Replace('\','/'))" -C $target status --short
