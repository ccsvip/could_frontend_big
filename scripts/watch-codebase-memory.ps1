param(
    [string]$RepoPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [ValidateSet("fast", "moderate", "full")]
    [string]$Mode = "full",
    [int]$DebounceSeconds = 12,
    [switch]$NoPersistence
)

$ErrorActionPreference = "Stop"

$RepoPath = (Resolve-Path $RepoPath).Path
$persistence = -not $NoPersistence.IsPresent

$includedExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
@(
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".mjs", ".cjs",
    ".json", ".md", ".yml", ".yaml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss", ".sql", ".sh", ".ps1", ".bat",
    ".dockerfile"
) | ForEach-Object { [void]$includedExtensions.Add($_) }

$excludedPathPattern = [regex]::new(
    "(^|[\\/])(" +
    "\.git|\.svn|\.idea|\.claude|\.omc|\.omo|\.playwright-cli|\.playwright-mcp|" +
    "node_modules|dist|build|coverage|__pycache__|\.pytest_cache|\.mypy_cache|" +
    "media|staticfiles|output|renders|\.codebase-memory" +
    ")([\\/]|$)",
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
)

function Test-IndexablePath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return $false
    }

    $relativePath = [System.IO.Path]::GetRelativePath($RepoPath, $Path)
    if ($relativePath.StartsWith("..")) {
        return $false
    }

    if ($excludedPathPattern.IsMatch($relativePath)) {
        return $false
    }

    $extension = [System.IO.Path]::GetExtension($Path)
    if ($includedExtensions.Contains($extension)) {
        return $true
    }

    $fileName = [System.IO.Path]::GetFileName($Path)
    return $fileName -in @("Dockerfile", "Makefile", "AGENTS.md", "CLAUDE.md")
}

function Invoke-CodebaseMemoryIndex {
    $payload = @{
        repo_path   = $RepoPath
        mode        = $Mode
        persistence = $persistence
    } | ConvertTo-Json -Compress

    $startedAt = Get-Date
    Write-Host "[$($startedAt.ToString("yyyy-MM-dd HH:mm:ss"))] Indexing $RepoPath (mode=$Mode, persistence=$persistence)"

    & codebase-memory-mcp cli index_repository $payload

    if ($LASTEXITCODE -ne 0) {
        throw "codebase-memory-mcp index_repository failed with exit code $LASTEXITCODE"
    }

    $finishedAt = Get-Date
    $elapsed = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 1)
    Write-Host "[$($finishedAt.ToString("yyyy-MM-dd HH:mm:ss"))] Index complete (${elapsed}s)"
}

$watcher = [System.IO.FileSystemWatcher]::new($RepoPath)
$watcher.IncludeSubdirectories = $true
$watcher.Filter = "*.*"
$watcher.NotifyFilter = [System.IO.NotifyFilters]'FileName, DirectoryName, LastWrite, Size'
$watcher.EnableRaisingEvents = $true

$queue = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
$lastChangeAt = $null
$indexInProgress = $false

$action = {
    if (Test-IndexablePath -Path $Event.SourceEventArgs.FullPath) {
        $script:queue.Enqueue($Event.SourceEventArgs.FullPath)
        $script:lastChangeAt = Get-Date
    }
}

$subscriptions = @(
    Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action
    Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action
    Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action $action
    Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $action
)

Write-Host "Watching $RepoPath for codebase-memory-mcp indexing."
Write-Host "Debounce: ${DebounceSeconds}s. Mode: $Mode. Press Ctrl+C to stop."

try {
    while ($true) {
        Start-Sleep -Seconds 1

        if ($null -eq $lastChangeAt -or $indexInProgress) {
            continue
        }

        $quietSeconds = ((Get-Date) - $lastChangeAt).TotalSeconds
        if ($quietSeconds -lt $DebounceSeconds) {
            continue
        }

        $changedPaths = [System.Collections.Generic.List[string]]::new()
        $path = $null
        while ($queue.TryDequeue([ref]$path)) {
            [void]$changedPaths.Add($path)
        }

        if ($changedPaths.Count -eq 0) {
            $lastChangeAt = $null
            continue
        }

        $indexInProgress = $true
        $lastChangeAt = $null

        $sample = $changedPaths |
            Select-Object -Unique -First 5 |
            ForEach-Object { [System.IO.Path]::GetRelativePath($RepoPath, $_) }

        Write-Host "Detected $($changedPaths.Count) file event(s): $($sample -join ', ')"

        try {
            Invoke-CodebaseMemoryIndex
        }
        catch {
            Write-Warning $_
        }
        finally {
            $indexInProgress = $false
        }
    }
}
finally {
    $watcher.EnableRaisingEvents = $false
    $subscriptions | ForEach-Object {
        Unregister-Event -SubscriptionId $_.Id -ErrorAction SilentlyContinue
        Remove-Job -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    $watcher.Dispose()
}
