# Neovim · entorno de desarrollo

Base NvChad para Neovim 0.11.5, con JavaScript/TypeScript, React, C, C++ y Python.
La tecla líder es **Espacio**. Se conservan Ctrl+S, jk, J/K visuales y Ctrl+D/U.

## Empezar

Abre una carpeta o archivo con nvim. Espacio muestra los grupos de atajos.
El inicio ofrece archivos, búsqueda, sesiones y esta guía.
:NvimGuide abre esta guía; :NvimHealth comprueba herramientas y parsers.

| Acción | Atajo |
| --- | --- |
| Archivos del proyecto / texto del proyecto | Espacio ff / fw |
| Buscar palabra / repetir búsqueda | Espacio fg / fr |
| Buffers / recientes / buscar atajos | Espacio fb / fo / fk |
| Buscar dentro del archivo | Espacio fz |
| Árbol de archivos | Ctrl+N |
| Definición / referencias / implementación | gd / gr / gi |
| Documentación / renombrar / acciones | K / Espacio cr / ca |
| Símbolos / organizar imports | Espacio cs / ci |
| Diagnóstico / panel de problemas | Espacio cd / cx |
| Diagnóstico anterior / siguiente | [d / ]d |
| Formatear / pausar formato automático | Espacio fm / uf |
| Ejecutar archivo / tareas del proyecto | Espacio rf / rr |
| Probar archivo Python / repetir tarea | Espacio rt / rl |
| Seleccionar intérprete Python | Espacio rp |
| Iniciar depuración / breakpoint | F5 / F9 |
| Siguiente línea / entrar / salir | F10 / F11 / Shift+F11 |
| Terminar depuración / paneles / evaluar | Espacio dq / dt / de |
| Revisar cambios / historial Git | Espacio gv / gh |
| Vista previa / preparar / retirar bloque Git | Espacio gp / gs / gu |
| Recuperar sesión / elegir sesión | Espacio qs / qS |
| Hint de tipos / diagnóstico expandido | Espacio uh / ud |
| Herramientas / plugins / salud | Espacio pm / pl / ph |

Telescope: Ctrl+J/K selecciona; Ctrl+U/D desplaza la vista previa; Ctrl+Q envía resultados a quickfix; Esc cierra.
Tab/Shift+Tab recorre buffers. Espacio x cierra el buffer y pregunta si hay cambios.
Autocompletado: Ctrl+Espacio solicita, Ctrl+N/P o Tab selecciona, Enter confirma una selección explícita.
mini.surround: sa añade delimitadores, sd elimina, sr sustituye; mini.ai mejora objetos de texto.
Alt+I alterna la terminal flotante. Ctrl+X sale del modo terminal para recorrer su salida.

### Leer el resultado de una ejecución

Espacio rf guarda y ejecuta el archivo. Al terminar, el panel queda en modo normal:
puedes leer y copiar la salida sin que una tecla la cierre. Usa `gg` para leerla desde
el comienzo. La barra indica el nombre y el resultado de la tarea.

| Acción en el panel de salida | Tecla |
| --- | --- |
| Subir / bajar una línea | ↑ / ↓ o k / j |
| Subir / bajar media pantalla | Ctrl+U / Ctrl+D |
| Ir al inicio / al final | gg / G |
| Buscar un error | /ReferenceError y Enter; n para el siguiente |
| Volver al código sin cerrar el panel | Ctrl+W y k |
| Cerrar el panel (conserva la salida en buffers) | q |

Mientras el programa sigue ejecutándose, las teclas van al programa; Ctrl+C lo
interrumpe. Usa Esc o Ctrl+X para explorar su salida y `i` para volver a escribirle.
Una vez terminado, `i` ya no reactiva una terminal cerrada.

## Lenguajes y proyectos

**JS/TS/React:** TypeScript Language Server, ESLint cuando el proyecto tiene configuración,
snippets, importaciones, navegación, renombrado y diagnósticos.
Los archivos JavaScript independientes tienen comprobación semántica (`checkJs`):
un nombre como `cnsole` se marca antes de ejecutar. Los diagnósticos se actualizan
al salir del modo insertar; Espacio cd muestra el mensaje completo bajo el cursor.
Se respeta el `checkJs` de jsconfig.json/tsconfig.json si existe, y `// @ts-nocheck`
permite excluir un archivo explícitamente.
Conform usa la versión local de Prettier cuando existe; respeta .prettierrc y .editorconfig.
Si hay biome.json/biome.jsonc y un binario Biome disponible en el proyecto, utiliza Biome.
Las tareas leen package.json y detectan npm, pnpm, yarn o bun, incluidos monorepos.
Para JSX/TSX, aplicaciones web y scripts con loaders, ejecuta la tarea del proyecto.

**Python:** Pyright para tipos/completado y Ruff para lint/formato, sin duplicar hover.
Detecta el entorno activo y .venv/venv del proyecto; Espacio rp permite cambiarlo para esta sesión.
Respeta pyproject.toml y ruff.toml. Las pruebas usan pytest del entorno del proyecto:
las dependencias de cada proyecto siguen siendo responsabilidad de su propio entorno.

**C/C++:** clangd con índice en segundo plano y clang-tidy; clang-format respeta .clang-format.
Espacio ch alterna cabecera e implementación.
Los proyectos necesitan sus opciones reales de compilación en compile_commands.json.
El menú de tareas ofrece configurar CMake con CMAKE_EXPORT_COMPILE_COMMANDS=ON,
compilar y ejecutar CTest; también reconoce Makefile.
Para archivos independientes, Espacio rf compila con GCC/G++, -g, -O0, avisos y C17/C++20.
Los binarios temporales van a la caché de Neovim; no se escriben en el proyecto.

## Depuración

Incluye paneles de variables, pila, breakpoints, consola y REPL.
F9 marca una línea y F5 elige cómo iniciar. C/C++ pide un binario compilado con -g;
el menú de tareas puede preparar el archivo independiente.
Python usa debugpy y el intérprete del proyecto. Node usa el adaptador oficial js-debug.
También se pueden usar configuraciones del proyecto en .vscode/launch.json.
JS/TS con bundlers o aliases necesita su configuración de lanzamiento/source maps.

Nada ejecuta builds, scripts, tests ni aplicaciones al abrir un archivo.
Las tareas y sesiones de depuración se inician mediante una acción explícita.

## Apariencia y rendimiento

Rosé Pine, fondo del editor transparente, ventanas flotantes legibles, pestañas,
barra de estado con Git, diagnósticos, servidores activos y estado del formato.
La búsqueda usa el motor fzf nativo, muestra vistas previas y omite dependencias.
En ventanas estrechas coloca la vista previa debajo de los resultados para conservarla
incluso con fuentes grandes; en ventanas anchas la coloca al lado.
Los plugins de depuración, Git avanzado y paneles se cargan cuando se usan.
Los archivos de más de 1 MB omiten resaltado pesado y formato automático.
Los cambios pueden deshacerse incluso después de cerrar Neovim mediante undo persistente.

El formato al guardar está activo; Espacio uf lo pausa para esta sesión.
Las reglas del proyecto tienen preferencia sobre los valores generales.
No se instalan herramientas al abrir archivos ni se actualizan plugins en segundo plano.
Las sesiones guardan la distribución local y se restauran solo cuando lo pides.

## Mantenimiento

:Mason administra servidores, formateadores y depuradores locales; :ConformInfo explica
qué formateador eligió el archivo; :checkhealth vim.lsp revisa los servidores.
Las versiones base están fijadas para evitar saltos incompatibles con Neovim 0.11.5.
lazy-lock.json conserva las revisiones exactas. Revisa compatibilidad antes de actualizar el núcleo.

La configuración se divide en lua/configs, lua/workbench, mappings.lua y chadrc.lua.
Los respaldos de instalación se administran con `dotifails restore`.

Para comprobar la instalación, ejecuta `~/.config/nvim/scripts/verify.sh` desde una terminal.
Usa ejemplos temporales: verifica LSP, diagnósticos, formato, búsqueda y paneles;
después inicia depuraciones de Python, Node y C++ para comprobar breakpoints,
variables y avance de línea. Deja los resultados y registros en la ruta temporal que imprime.
Consulta `docs/validation.md` en el repositorio para los resultados de la instalación portable.

`scripts/check-js-output.py` comprueba los diagnósticos de JavaScript y las teclas
del panel de salida con una UI aislada y archivos temporales. Requiere un Python
con `pynvim`, que puede instalarse en un entorno virtual de pruebas.

`scripts/install.lua` sirve para reinstalar las herramientas de esta configuración
de forma explícita: `nvim --headless -c 'luafile ~/.config/nvim/scripts/install.lua' -c 'qa'`.
Ripgrep se instala desde APT. Node y Neovim se instalan con versión y SHA-256 fijadas;
Mason usa las versiones de `mason-lock.json`.

Referencias: [Ruff](https://docs.astral.sh/ruff/editors/setup/),
[clangd](https://clangd.llvm.org/installation),
[DAP](https://github.com/mfussenegger/nvim-dap),
[fzf nativo](https://github.com/nvim-telescope/telescope-fzf-native.nvim).
