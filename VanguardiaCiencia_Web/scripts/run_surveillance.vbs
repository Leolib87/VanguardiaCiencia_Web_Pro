Set WshShell = CreateObject("WScript.Shell")
Do
    ' Ejecuta el Agente de Vigilancia de forma invisible
    WshShell.Run "python C:\Users\leoli\OneDrive\Desktop\VanguardiaCiencia_Web\scripts\agent_vigilancia.py", 0, True
    ' Espera 8 horas (8 * 60 * 60 * 1000 milisegundos)
    WScript.Sleep 28800000 
Loop
