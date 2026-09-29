Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$synth.Volume = 100
$synth.SetOutputToWaveFile("d:\Cynexis\scratch\cynexis_online_sapi.wav")
$synth.Speak("CYNEXIS online.")
$synth.Dispose()
Write-Host "SAPI WAV File Created Successfully"
