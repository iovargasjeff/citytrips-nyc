param(
  [Parameter(Mandatory = $true)][string]$LinesFile,
  [Parameter(Mandatory = $true)][string]$OutputDirectory
)

Add-Type -AssemblyName System.Speech
$lines = Get-Content -Raw -Encoding UTF8 $LinesFile | ConvertFrom-Json
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like '*Raul*' } | Select-Object -First 1
if (-not $voice) {
  $voice = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'es-*' } | Select-Object -First 1
}
if (-not $voice) { throw 'No Spanish Windows speech voice is installed.' }

$synth.SelectVoice($voice.VoiceInfo.Name)
$synth.Rate = 0
$synth.Volume = 92
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

for ($index = 0; $index -lt $lines.Count; $index++) {
  $audioPath = Join-Path $OutputDirectory ('narration-{0:D2}.wav' -f ($index + 1))
  $synth.SetOutputToWaveFile($audioPath)
  [void]$synth.Speak([string]$lines[$index])
  $synth.SetOutputToNull()
}

$synth.Dispose()
Write-Output "Voice: $($voice.VoiceInfo.Name)"
