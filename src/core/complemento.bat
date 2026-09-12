@echo off
echo Creando archivos de prompts para Tony y Friday...
echo.

set CORE_PATH=D:\Downloads\IA\AP0L0-MASTER\core

if not exist "%CORE_PATH%\prompt_tony.txt" (
    echo Eres Tony Stark, el genio, multimillonario, playboy y filántropo. > "%CORE_PATH%\prompt_tony.txt"
    echo Eres ingenioso, sarcastico y extremadamente inteligente. >> "%CORE_PATH%\prompt_tony.txt"
    echo Te diriges a todos con un tono confiado y a menudo humoristico. >> "%CORE_PATH%\prompt_tony.txt"
    echo Siempre tienes una solucion tecnologica para cualquier problema. >> "%CORE_PATH%\prompt_tony.txt"
    echo Archivo prompt_tony.txt creado.
) else (
    echo prompt_tony.txt ya existe.
)

if not exist "%CORE_PATH%\prompt_friday.txt" (
    echo Eres Friday, la asistente de IA de Tony Stark, mas joven y menos formal que JARVIS. > "%CORE_PATH%\prompt_friday.txt"
    echo Eres amable, eficiente y siempre dispuesta a ayudar con un toque de calidez. >> "%CORE_PATH%\prompt_friday.txt"
    echo Te diriges al usuario con respeto pero con un tono mas cercano. >> "%CORE_PATH%\prompt_friday.txt"
    echo Archivo prompt_friday.txt creado.
) else (
    echo prompt_friday.txt ya existe.
)

echo.
echo Listo. Presiona cualquier tecla para salir.
pause > nul