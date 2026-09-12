' kaan-trade paneli -- masaustu uygulamasi baslatici
'
' Bu dosya uygulamayi HIC KOMUT PENCERESI ACMADAN baslatir.
' Cift tiklayin, sadece uygulama penceresi acilir.

Dim kabuk, klasor
Set kabuk = CreateObject("WScript.Shell")
klasor = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

kabuk.CurrentDirectory = klasor

' pythonw.exe konsol penceresi acmaz (python.exe acar)
Dim pythonw
pythonw = klasor & ".venv\Scripts\pythonw.exe"

If CreateObject("Scripting.FileSystemObject").FileExists(pythonw) Then
    kabuk.Run """" & pythonw & """ """ & klasor & "masaustu.py""", 0, False
Else
    MsgBox "Sanal ortam bulunamadi:" & vbCrLf & pythonw & vbCrLf & vbCrLf & _
           "Kurulumun tamamlandigindan emin olun.", 16, "kaan-trade"
End If
