# Regenerate the README dashboard demo:  vhs assets/dash-demo.tape
# Requires: vhs, ttyd, ffmpeg on PATH, and `oracle` (token-oracle) installed with real usage data.
Output "assets/dash-demo.gif"
Set Shell bash
Set FontSize 14
Set Width 760
Set Height 560
Set Padding 20
Set Framerate 24
Set TypingSpeed 45ms

Hide
Type "export TOKEN_ORACLE_SKIP_BOOTSTRAP=1 PS1='$ '"
Enter
Type "clear"
Enter
Show

Type "oracle dash"
Sleep 400ms
Enter
Sleep 7s
