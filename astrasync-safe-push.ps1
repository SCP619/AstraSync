# AstraSync: verify Git and SSH identity before pushing a contributor branch.
# Usage (Windows CMD):
#   powershell -NoProfile -File .\astrasync-safe-push.ps1 -Account aosaf
#   powershell -NoProfile -File .\astrasync-safe-push.ps1 -Account aosaf -Push
# Run from inside your local AstraSync Git clone. Does not modify Git configuration.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('aosaf', 'scp619')]
    [string]$Account,

    [switch]$Push
)

$ErrorActionPreference = 'Stop'

$accounts = @{
    aosaf = @{
        GitHubUser = 'Aosaf098'
        SshAlias   = 'github-aosaf'
        BranchRoot = 'aosaf/'
        Email      = 'aosafibad10@gmail.com'
    }
    scp619 = @{
        GitHubUser = 'SCP619'
        SshAlias   = 'github-scp619'
        BranchRoot = 'scp619/'
        Email      = ''  # Teammate must configure their own verified email locally.
    }
}

$selected = $accounts[$Account]
$expectedRemote = "git@$($selected.SshAlias):SCP619/AstraSync.git"

function Invoke-GitRead([string[]]$CommandArgs) {
    $result = & git @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($CommandArgs -join ' ')"
    }
    return ($result | Out-String).Trim()
}

try {
    $repoRoot = Invoke-GitRead -CommandArgs @('rev-parse', '--show-toplevel')
    $branch = Invoke-GitRead -CommandArgs @('branch', '--show-current')
    $remote = Invoke-GitRead -CommandArgs @('remote', 'get-url', 'origin')
    $gitName = Invoke-GitRead -CommandArgs @('config', '--local', 'user.name')
    $gitEmail = Invoke-GitRead -CommandArgs @('config', '--local', 'user.email')

    Write-Host "Repository: $repoRoot"
    Write-Host "Branch:     $branch"
    Write-Host "Committer:  $gitName <$gitEmail>"
    Write-Host "Remote:     $remote"

    if ([string]::IsNullOrWhiteSpace($branch) -or -not $branch.StartsWith($selected.BranchRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Account $Account must use a '$($selected.BranchRoot)...' feature branch. Don't push directly to main."
    }
    if ($remote -ne $expectedRemote) {
        throw "Wrong remote for $Account. Expected: $expectedRemote`nIn this account's own clone, use: git remote set-url origin $expectedRemote"
    }
    if ([string]::IsNullOrWhiteSpace($gitName) -or [string]::IsNullOrWhiteSpace($gitEmail)) {
        throw 'Configure the real contributor name and GitHub-verified email with git config --local.'
    }
    if ($Account -eq 'aosaf' -and $gitEmail -ne $selected.Email) {
        throw "This is not the configured Aosaf commit email ($($selected.Email))."
    }

    $latestAuthor = Invoke-GitRead -CommandArgs @('log', '-1', '--format=%an|%ae')
    Write-Host "Last commit: $latestAuthor"
    if ($latestAuthor -ne "$gitName|$gitEmail") {
        throw "The last commit author differs from this clone's configured identity. Review authorship before pushing; do not rewrite someone else's commits."
    }

    # GitHub SSH's successful message typically exits with code 1, not 0.
    # Check the identified username in its text, not the process exit code.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $sshOutput = (& ssh -T "git@$($selected.SshAlias)" 2>&1 | Out-String)
    $ErrorActionPreference = $previousPreference
    $expectedGreeting = "Hi $($selected.GitHubUser)!"
    if (-not $sshOutput.Contains($expectedGreeting)) {
        throw "SSH account verification failed. Expected '$expectedGreeting'. Actual output: $sshOutput"
    }
    Write-Host "SSH account: $($selected.GitHubUser) (verified)" -ForegroundColor Green

    $changes = Invoke-GitRead -CommandArgs @('status', '--porcelain')
    if ($changes) {
        Write-Warning 'There are uncommitted or untracked files. A push only sends commits, not these files.'
        if ($Push) { throw 'Commit or intentionally set aside local changes before pushing.' }
    }

    if (-not $Push) {
        Write-Host 'DRY RUN OK. Add -Push when you are ready.' -ForegroundColor Green
        exit 0
    }

    Write-Host "Ready to push '$branch' as $($selected.GitHubUser) to SCP619/AstraSync."
    $confirmation = Read-Host 'Type PUSH to confirm'
    if ($confirmation -cne 'PUSH') {
        Write-Host 'Cancelled. Nothing was pushed.'
        exit 0
    }

    & git push -u origin $branch
    if ($LASTEXITCODE -ne 0) { throw 'git push failed.' }
    Write-Host 'Push completed.' -ForegroundColor Green
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
