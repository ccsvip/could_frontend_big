$ErrorActionPreference = 'Stop'
$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = 'C:\Program Files\nodejs\node.exe'
$startInfo.UseShellExecute = $false
$startInfo.RedirectStandardInput = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.Arguments = '"C:\Users\amigo\AppData\Roaming\npm\node_modules\oh-my-codex\dist\scripts\codex-native-hook.js"'
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $startInfo
$null = $process.Start()
$stdinTask = [Console]::OpenStandardInput().CopyToAsync($process.StandardInput.BaseStream)
$stdoutTask = $process.StandardOutput.BaseStream.CopyToAsync([Console]::OpenStandardOutput())
$stderrTask = $process.StandardError.BaseStream.CopyToAsync([Console]::OpenStandardError())
$stdinTask.Wait()
$process.StandardInput.Close()
$process.WaitForExit()
$stdoutTask.Wait()
$stderrTask.Wait()
exit $process.ExitCode
