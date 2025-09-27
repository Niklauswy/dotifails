#!/usr/bin/env bash
# Desenvolvido pelo William Santos
# contato: thespation@gmail.com ou https://github.com/thespation
# Traducido y modificado por: Alejandro Fermín https://github.com/lostalejandro

# Configuración de manejo de errores y logging
set -e  # Salir en errores, pero será manejado por nuestras funciones
LOG_FILE="/tmp/bspwm_install_$(date +%Y%m%d_%H%M%S).log"
FAILED_COMPONENTS=()
TEMP_DIRS=()

# Función de logging simplificada
log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Función para manejo seguro de comandos
safe_execute() {
    local description="$1"
    shift
    local cmd="$*"
    
    if eval "$cmd" >> "$LOG_FILE" 2>&1; then
        log "✅ $description"
        return 0
    else
        log "❌ $description falló"
        FAILED_COMPONENTS+=("$description")
        return 1
    fi
}

# Función de limpieza
cleanup() {
    log "INFO: Ejecutando limpieza..."
    for temp_dir in "${TEMP_DIRS[@]}"; do
        if [[ -d "$temp_dir" ]]; then
            log "INFO: Limpiando directorio temporal: $temp_dir"
            rm -rf "$temp_dir" 2>/dev/null || log "WARNING: No se pudo eliminar $temp_dir"
        fi
    done
}

# Función de reintento simplificada
retry_command() {
    local description="$1"
    shift
    local cmd="$*"
    
    for i in {1..3}; do
        if safe_execute "$description (intento $i)" "$cmd"; then
            return 0
        fi
        [[ $i -lt 3 ]] && sleep 3
    done
    return 1
}

# Función para verificar disponibilidad de comandos
check_command() {
    local cmd="$1"
    if command -v "$cmd" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Función para verificar dependencias básicas del sistema
check_system_requirements() {
    log "INFO: Verificando requisitos del sistema..."
    
    # Verificar que estamos en un sistema Debian/Ubuntu
    if [[ ! -f /etc/debian_version ]]; then
        log "ERROR: Este script está diseñado para sistemas basados en Debian"
        return 1
    fi
    
    # Verificar comandos básicos necesarios
    local required_commands=("sudo" "apt" "curl" "wget" "git")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! check_command "$cmd"; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        log "ERROR: Los siguientes comandos son necesarios pero no están disponibles: ${missing_commands[*]}"
        return 1
    fi
    
    # Verificar conexión a internet
    if ! safe_execute "Verificación de conexión a internet" "curl -s --connect-timeout 10 https://www.google.com > /dev/null"; then
        log "WARNING: No se pudo verificar la conexión a internet, algunas descargas pueden fallar"
    fi
    
    log "SUCCESS: Verificación de requisitos del sistema completada"
    return 0
}

# Configurar trap para limpieza en caso de interrupción
trap cleanup EXIT

# Verificar que estamos ejecutando como usuario normal (no root)
if [[ $EUID -eq 0 ]]; then
    log "ERROR: Este script no debe ejecutarse como root. Usa sudo solo cuando sea necesario."
    exit 1
fi

log "INFO: Iniciando instalación de BSPWM"
log "INFO: Log guardado en: $LOG_FILE"

# Verificar requisitos del sistema
if ! check_system_requirements; then
    log "ERROR: Los requisitos del sistema no se cumplen. Abortando instalación."
    exit 1
fi

clear
##--------------------------------Funciones utilizadas en el script--------------------------------##
#--Identificar Distribución--#
#--Función: Instalar aplicaciones específicas de XFCE (si están disponibles)--#
function APPS_XFCE()
{
    log "INFO: Verificando e instalando componentes adicionales de XFCE..."
    
    local xfce_apps=(
        "xfce4-panel"
        "xfce4-settings"
        "xfce4-session"
        "xfce4-appfinder"
        "thunar"
        "xfce4-terminal"
    )
    
    local available_apps=()
    
    # Verificar qué aplicaciones están disponibles
    for app in "${xfce_apps[@]}"; do
        if safe_execute "Verificación de disponibilidad de $app" "apt-cache show $app > /dev/null 2>&1"; then
            available_apps+=("$app")
        else
            log "INFO: $app no está disponible en los repositorios"
        fi
    done
    
    # Instalar aplicaciones disponibles
    if [[ ${#available_apps[@]} -gt 0 ]]; then
        if safe_execute "Instalación de componentes XFCE adicionales" "sudo apt install ${available_apps[*]} -y"; then
            log "SUCCESS: Componentes XFCE adicionales instalados: ${available_apps[*]}"
        else
            log "WARNING: Algunos componentes XFCE adicionales no se pudieron instalar"
        fi
    else
        log "INFO: No hay componentes XFCE adicionales disponibles para instalar"
    fi
}

function VERIF_DISTRIB()
{
    log "INFO: Iniciando proceso de instalación de BSPWM..."
    
    # Lista de funciones a ejecutar con sus descripciones
    local functions=(
        "ACTUALIZAR:Actualización del sistema"
        "BSPWM:Instalación de BSPWM base"
        "KSUPERKEY:Instalación de ksuperkey"
        "I3LOCK:Instalación de i3lock-color"
        "ZSH:Configuración de ZSH"
        "PICOM:Instalación de Picom compositor"
        "APPS:Instalación de aplicaciones complementarias"
        "APPS_XFCE:Instalación de componentes XFCE adicionales"
        "PERSONA:Aplicación de personalizaciones"
    )
    
    echo ""
    echo "🚀 Iniciando instalación de BSPWM..."
    echo "📊 Total de pasos: ${#functions[@]}"
    echo ""
    
    local step=1
    for func_desc in "${functions[@]}"; do
        local func_name="${func_desc%%:*}"
        local description="${func_desc##*:}"
        
        echo "📋 Paso $step/${#functions[@]}: $description"
        log "INFO: Ejecutando paso $step: $func_name - $description"
        
        # Ejecutar la función y continuar aunque falle
        if $func_name; then
            log "SUCCESS: Paso $step completado exitosamente: $func_name"
            echo "✅ Paso $step completado"
        else
            log "ERROR: Paso $step falló: $func_name"
            echo "❌ Paso $step falló, pero continuando..."
            FAILED_COMPONENTS+=("Paso $step: $description")
        fi
        
        echo ""
        ((step++))
        sleep 1s
    done
    
    log "INFO: Proceso de instalación completado"
    echo "🏁 Proceso de instalación finalizado."
}

#--Función: Actualizar sistema (base Debian)--#
function ACTUALIZAR(){
    log "INFO: #-----------------------------Actualizar sistema-------------------------------#"
    
    # Actualizar repositorios
    if safe_execute "Actualización de repositorios" "sudo apt update"; then
        log "INFO: #--------------------------Repositorios actualizados---------------------------#"
        sleep 1s
    else
        log "WARNING: La actualización de repositorios falló, pero continuando..."
    fi
    
    # Actualizar programas
    if safe_execute "Actualización de programas" "sudo apt upgrade -y"; then
        log "INFO: #---------------------------Programas actualizados-----------------------------#"
        sleep 1s
    else
        log "WARNING: La actualización de programas falló, pero continuando..."
    fi
    
    # Limpieza del sistema
    safe_execute "Actualización de distribución" "sudo apt dist-upgrade -y" || log "WARNING: dist-upgrade falló"
    safe_execute "Limpieza automática" "sudo apt autoclean" || log "WARNING: autoclean falló"
    safe_execute "Eliminación de paquetes huérfanos" "sudo apt autoremove -y" || log "WARNING: autoremove falló"
    
    clear
    log "INFO: #-----------------------------Sistema actualizado------------------------------#"
    sleep 2s
}

			
#--Función: Instalar base BSPWM--#
function BSPWM()
{
    log "INFO: #----------------------------Instalando base BSPWM-----------------------------#"
    
    # Lista de paquetes base de BSPWM
    local packages=("bspwm" "sxhkd" "rofi" "polybar" "dunst" "arandr")
    local failed_packages=()
    
    # Intentar instalar todos los paquetes juntos primero
    if safe_execute "Instalación de paquetes base BSPWM" "sudo apt install ${packages[*]} -y"; then
        log "SUCCESS: Todos los paquetes base de BSPWM se instalaron correctamente"
    else
        log "WARNING: La instalación conjunta falló, intentando instalar paquetes individualmente..."
        
        # Si falla, instalar uno por uno
        for package in "${packages[@]}"; do
            if ! safe_execute "Instalación de $package" "sudo apt install $package -y"; then
                failed_packages+=("$package")
                log "ERROR: No se pudo instalar $package"
            fi
        done
        
        if [[ ${#failed_packages[@]} -gt 0 ]]; then
            log "WARNING: Los siguientes paquetes no se pudieron instalar: ${failed_packages[*]}"
            log "WARNING: El sistema puede no funcionar completamente sin estos paquetes"
        fi
    fi
    
    clear
    log "INFO: #----------------------------Base BSPWM instalada------------------------------#"
    sleep 2s
}


#--Función: Instalar ksuperkey--#
function KSUPERKEY()
{
    log "Instalando ksuperkey..."
    local temp_dir="/tmp/ksuperkey_build_$(date +%s)"
    TEMP_DIRS+=("$temp_dir")
    
    safe_execute "Dependencias ksuperkey" "sudo apt install gcc make libx11-dev libxtst-dev pkg-config git -y" &&
    safe_execute "Clonar ksuperkey" "mkdir -p $temp_dir && cd $temp_dir && git clone https://github.com/hanschen/ksuperkey.git" &&
    safe_execute "Compilar ksuperkey" "cd $temp_dir/ksuperkey && make && sudo make install"
}
	
#--Función: Instalar i3lock-color--#
function I3LOCK()
{
    log "Instalando i3lock-color..."
    local temp_dir="/tmp/i3lock_build_$(date +%s)"
    TEMP_DIRS+=("$temp_dir")
    
    local deps="autoconf gcc make pkg-config libpam0g-dev libcairo2-dev libfontconfig1-dev libxcb-composite0-dev libev-dev libx11-xcb-dev libxcb-xkb-dev libxcb-xinerama0-dev libxcb-randr0-dev libxcb-image0-dev libxcb-util0-dev libxcb-xrm-dev libxcb-xtest0-dev libxkbcommon-dev libxkbcommon-x11-dev libjpeg-dev git"
    
    safe_execute "Dependencias i3lock-color" "sudo apt install $deps -y" &&
    safe_execute "Clonar i3lock-color" "mkdir -p $temp_dir && cd $temp_dir && git clone https://github.com/Raymo111/i3lock-color.git" &&
    safe_execute "Instalar i3lock-color" "cd $temp_dir/i3lock-color && chmod +x ./install-i3lock-color.sh && ./install-i3lock-color.sh"
}




#--Función: Instalar y configurar ZSH--#
function ZSH()
{
    log "Configurando ZSH..."
    
    safe_execute "Instalar ZSH y zplug" "sudo apt install zsh zplug -y" &&
    safe_execute "Cambiar shell a ZSH" "chsh -s $(which zsh)" &&
    retry_command "Oh My Zsh" 'RUNZSH=no CHSH=no sh -c "$(wget -O- https://raw.github.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"' &&
    
    # Plugins y themes
    local custom_dir="${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}"
    retry_command "Powerlevel10k theme" "git clone --depth=1 https://github.com/romkatv/powerlevel10k.git $custom_dir/themes/powerlevel10k" &&
    retry_command "Syntax highlighting" "git clone https://github.com/zsh-users/zsh-syntax-highlighting.git $custom_dir/plugins/zsh-syntax-highlighting" &&
    retry_command "Auto suggestions" "git clone https://github.com/zsh-users/zsh-autosuggestions $custom_dir/plugins/zsh-autosuggestions"
}
	



#--Función: Instalar aplicaciones complementarias (base Debian)--#
function APPS()
{
    log "INFO: #------------------------Instalar apps complementarias-------------------------#"
    
    # Lista de aplicaciones básicas del sistema
    local basic_apps=(
        "xsel" "neofetch" "cmatrix" "flameshot" "gnome-terminal" "ranger" 
        "xbacklight" "gpick" "light" "cava" "nautilus" "htop" "feh" "dmenu" 
        "nm-tray" "xfconf" "xsettingsd" "xfce4-power-manager" "zenity" 
        "git" "ttf-mscorefonts-installer" "bat" "curl" "cargo"
    )
    
    # Instalar aplicaciones básicas
    local failed_basic=()
    log "INFO: Instalando aplicaciones básicas..."
    
    if safe_execute "Instalación de aplicaciones básicas" "sudo apt install ${basic_apps[*]} -y"; then
        log "SUCCESS: Aplicaciones básicas instaladas correctamente"
    else
        log "WARNING: La instalación conjunta falló, intentando individualmente..."
        for app in "${basic_apps[@]}"; do
            if ! safe_execute "Instalación de $app" "sudo apt install $app -y"; then
                failed_basic+=("$app")
                log "WARNING: No se pudo instalar $app"
            fi
        done
    fi
    
    # Deshabilitar MPD si está instalado
    if safe_execute "Deshabilitación de MPD" "sudo systemctl disable mpd"; then
        log "SUCCESS: MPD deshabilitado"
    else
        log "INFO: MPD no estaba instalado o ya estaba deshabilitado"
    fi
    
    # Funciones simplificadas de instalación
    install_jetbrains_font() {
        retry_command "JetBrains Font" '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/install_manual.sh)"'
    }
    
    install_vim_plug() {
        local plug_dir="${XDG_DATA_HOME:-$HOME/.local/share}/nvim/site/autoload"
        safe_execute "Crear dir vim-plug" "mkdir -p $plug_dir" &&
        retry_command "Vim-plug" "curl -fLo $plug_dir/plug.vim https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim"
    }
    
    install_lsd() {
        check_command "cargo" && retry_command "LSD" "cargo install --git https://github.com/lsd-rs/lsd.git --branch master"
    }
    
    install_fzf() {
        if [[ -d "$HOME/.fzf" ]]; then
            safe_execute "Actualizar FZF" "cd $HOME/.fzf && git pull"
        else
            retry_command "Clonar FZF" "git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf" &&
            safe_execute "Instalar FZF" "$HOME/.fzf/install --all"
        fi
    }
    
    install_nodejs() {
        retry_command "NVM" 'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash' &&
        safe_execute "Node.js" 'export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" && nvm install 20'
    }
    
    install_neovim() {
        local nvim_archive="/tmp/bspwm/nvim.tar.gz"
        if [[ -f "$nvim_archive" ]]; then
            local temp_dir="/tmp/nvim_install_$(date +%s)"
            TEMP_DIRS+=("$temp_dir")
            safe_execute "Extraer Neovim" "mkdir -p $temp_dir && tar xzf $nvim_archive -C $temp_dir" &&
            safe_execute "Instalar Neovim" "sudo mv $temp_dir/nvim-linux* /opt/nvim && sudo ln -sf /opt/nvim/bin/nvim /usr/local/bin/nvim"
        fi
    }
    
    # Instalar GitHub CLI y extensión Copilot
    install_github_cli() {
        log "Instalando GitHub CLI..."
        if ! check_command "curl"; then
            safe_execute "Instalar curl" "sudo apt update && sudo apt install curl -y"
        fi
        
        if retry_command "Configurar repo GitHub CLI" '
            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg &&
            sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg &&
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null &&
            sudo apt update && sudo apt install gh -y
        '; then
            log "✅ GitHub CLI instalado"
            # Instalar extensión GitHub Copilot
            safe_execute "GitHub Copilot CLI extension" "gh extension install github/gh-copilot --force" || log "⚠️ GitHub Copilot extensión falló (requiere auth)"
        fi
    }
    
    # Instalar Brave Browser
    install_brave() {
        log "Instalando Brave Browser..."
        if retry_command "Configurar repo Brave" '
            sudo curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg &&
            echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] https://brave-browser-apt-release.s3.brave.com/ stable main" | sudo tee /etc/apt/sources.list.d/brave-browser-release.list &&
            sudo apt update && sudo apt install brave-browser -y
        '; then
            log "✅ Brave Browser instalado"
        fi
    }
    
    # Ejecutar instalaciones de componentes opcionales
    install_jetbrains_font
    install_vim_plug
    install_lsd
    install_fzf
    install_nodejs
    install_neovim
    install_github_cli
    install_brave
    
    # Resumen de aplicaciones que fallaron
    if [[ ${#failed_basic[@]} -gt 0 ]]; then
        log "WARNING: Las siguientes aplicaciones básicas no se pudieron instalar: ${failed_basic[*]}"
    fi
    
    log "INFO: Instalación de aplicaciones complementarias completada"
    sleep 2s
}

	
#--Función: Usar personalizaciones para: fonts, configs, iconos, temas, polybar, dunst y rofi--#
function PERSONA()
{
    log "INFO: #---------Copiar personalizaciones (iconos, temas, fonts, fondos, etc)---------#"
    
    local source_dir="/tmp/bspwm"
    
    # Verificar que el directorio fuente existe
    if [[ ! -d "$source_dir" ]]; then
        log "ERROR: El directorio de personalización $source_dir no existe"
        return 1
    fi
    
    cd "$source_dir" || {
        log "ERROR: No se pudo acceder al directorio $source_dir"
        return 1
    }
    
    # Copiar fuentes al sistema
    if [[ -d "$source_dir/fonts" ]]; then
        if safe_execute "Copia de fuentes al sistema" "sudo cp -r $source_dir/fonts/* /usr/share/fonts/"; then
            safe_execute "Actualización de caché de fuentes" "sudo fc-cache -f -v" || log "WARNING: No se pudo actualizar el caché de fuentes"
            log "SUCCESS: Fuentes copiadas al sistema"
        else
            log "WARNING: No se pudieron copiar las fuentes al sistema"
        fi
    else
        log "WARNING: Directorio de fuentes no encontrado"
    fi
    
    # Copiar iconos al sistema
    if [[ -d "$source_dir/icons" ]]; then
        if safe_execute "Copia de iconos al sistema" "sudo cp -r $source_dir/icons/* /usr/share/icons/"; then
            log "SUCCESS: Iconos copiados al sistema"
        else
            log "WARNING: No se pudieron copiar los iconos al sistema"
        fi
    else
        log "WARNING: Directorio de iconos no encontrado"
    fi
    
    # Copiar temas al sistema
    if [[ -d "$source_dir/themes" ]]; then
        if safe_execute "Copia de temas al sistema" "sudo cp -r $source_dir/themes/* /usr/share/themes/"; then
            log "SUCCESS: Temas copiados al sistema"
        else
            log "WARNING: No se pudieron copiar los temas al sistema"
        fi
    else
        log "WARNING: Directorio de temas no encontrado"
    fi
    
    # Copiar fondos de pantalla al sistema
    if [[ -d "$source_dir/backgrounds" ]]; then
        if safe_execute "Copia de fondos de pantalla" "sudo cp -r $source_dir/backgrounds/* /usr/share/backgrounds/"; then
            log "SUCCESS: Fondos de pantalla copiados"
        else
            log "WARNING: No se pudieron copiar los fondos de pantalla"
        fi
    else
        log "WARNING: Directorio de fondos no encontrado"
    fi
    
    # Crear directorio .config si no existe
    safe_execute "Creación de directorio .config" "mkdir -p ~/.config"
    
    # Copiar carpeta de scripts si existe
    if [[ -d "$source_dir/home/scripts" ]]; then
        if safe_execute "Copia de carpeta scripts" "cp -rf $source_dir/home/scripts $HOME/"; then
            safe_execute "Permisos ejecutables scripts" "chmod +x $HOME/scripts/* 2>/dev/null" || true
            log "✅ Carpeta scripts copiada"
        fi
    fi
    
    # Copiar configuraciones de usuario
    local user_configs=(
        ".config"
        ".Xresources.d"
        ".Xresources"
        ".gtkrc-2.0"
        ".xsettingsd"
        ".dmrc"
        ".fehbg"
        ".zshrc"
        ".p10k.zsh"
    )
    
    for config in "${user_configs[@]}"; do
        local source_path="$source_dir/home/$config"
        if [[ -e "$source_path" ]]; then
            if [[ "$config" == ".config" ]]; then
                safe_execute "Config $config" "cp -rf $source_path/* ~/.config/"
            else
                safe_execute "Config $config" "cp -rf $source_path $HOME/"
            fi
        fi
    done
    
    clear
    log "INFO: #---------------------Personalizaciones principales copiadas-------------------#"
    sleep 2s
    clear
    
    # Llamar al reporte final en lugar de solo NOTF_SUCESS
    INSTALLATION_REPORT
}

#--Función: Instalar Picom compositor--#
function PICOM()
{
    log "Instalando Picom compositor..."
    
    local deps="libconfig-dev libdbus-1-dev libegl-dev libev-dev libgl-dev libpcre2-dev libpixman-1-dev libx11-xcb-dev libxcb1-dev libxcb-composite0-dev libxcb-damage0-dev libxcb-dpms0-dev libxcb-glx0-dev libxcb-image0-dev libxcb-present0-dev libxcb-randr0-dev libxcb-render0-dev libxcb-render-util0-dev libxcb-shape0-dev libxcb-util-dev libxcb-xfixes0-dev libxext-dev meson ninja-build uthash-dev"
    
    safe_execute "Dependencias Picom" "sudo apt install $deps -y" &&
    safe_execute "Clonar Picom" "mkdir -p $HOME/.config && cd $HOME/.config && git clone https://github.com/FT-Labs/picom" &&
    safe_execute "Compilar Picom" "cd $HOME/.config/picom && meson setup --buildtype=release build && ninja -C build && ninja -C build install" &&
    
    # Copiar configuración si existe
    local config_source="/tmp/bspwm/home/.config/bspwm/picom.conf"
    [[ -f "$config_source" ]] && safe_execute "Config Picom" "cp $config_source $HOME/.config/picom/"
}

	
#--Función: Generar reporte de instalación--#
function INSTALLATION_REPORT()
{
    log "INFO: #--------------------------Generando reporte de instalación--------------------------#"
    
    echo ""
    echo "========================================="
    echo "    REPORTE DE INSTALACIÓN DE BSPWM"
    echo "========================================="
    echo ""
    
    if [[ ${#FAILED_COMPONENTS[@]} -eq 0 ]]; then
        echo "✅ ¡INSTALACIÓN COMPLETADA EXITOSAMENTE!"
        echo ""
        echo "🎉 Todos los componentes se instalaron correctamente."
        log "SUCCESS: Instalación completada sin errores"
    else
        echo "⚠️  INSTALACIÓN COMPLETADA CON ADVERTENCIAS"
        echo ""
        echo "❌ Los siguientes componentes presentaron problemas:"
        for component in "${FAILED_COMPONENTS[@]}"; do
            echo "   • $component"
        done
        echo ""
        echo "ℹ️  El sistema BSPWM debería funcionar, pero algunos componentes"
        echo "   opcionales pueden no estar disponibles."
        log "WARNING: Instalación completada con ${#FAILED_COMPONENTS[@]} componentes fallidos"
    fi
    
    echo ""
    echo "📋 PASOS SIGUIENTES:"
    echo "   1. Reinicia tu sistema para aplicar todos los cambios"
    echo "   2. Selecciona 'bspwm' en la pantalla de login"
    echo "   3. Usa Super+Enter para abrir terminal"
    echo "   4. Usa Super+Espacio para abrir rofi"
    echo ""
    echo "📝 Log detallado guardado en: $LOG_FILE"
    echo ""
    echo "========================================="
    
    # Mostrar notificación gráfica si zenity está disponible
    NOTF_SUCESS
}

#--Función: Notificar operacion exitosa--#
function NOTF_SUCESS()
{
    local message
    if [[ ${#FAILED_COMPONENTS[@]} -eq 0 ]]; then
        message="Instalación exitosa. Para que todo funcione correctamente, es recomendable que reinicie su sistema."
        log "SUCCESS: Notificación de éxito mostrada"
    else
        message="Instalación completada con advertencias. Revise el log en $LOG_FILE para más detalles. Se recomienda reiniciar el sistema."
        log "WARNING: Notificación de advertencia mostrada"
    fi
    
    if check_command "zenity"; then
        zenity --info --width 400 --title "Instalación BSPWM" --text "$message" 2>/dev/null || {
            echo "NOTIFICACIÓN: $message"
        }
    else
        echo "NOTIFICACIÓN: $message"
    fi
}

#--Función: Notificar Fallo--#
function NOTF_FALLA()
{
    clear
    log "ERROR: Sistema no soportado detectado"
    echo "#----------------------------Sistema no soportado------------------------------#"
    echo "#--------Este script fue diseñado para correr en las siguientes distros:-------#"		
    echo "#------------------Debian Bullseye o Bookworm (XFCE y GNOME)-------------------#"
    echo ""
    echo "Por favor, verifica que estés ejecutando este script en una distribución soportada."
    echo ""
}
		
##--------------------------------Funciones utilizadas en el script--------------------------------##
	clear
			echo "#------------------Este asistente instalará bspwm en su máquina----------------#"
	VERIF_DISTRIB

