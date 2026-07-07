#!/bin/bash
# Configuración central del sistema de auto-arranque/apagado de Minecraft.
# Editá lo que necesites acá, no hace falta tocar los .py para lo básico.

# ---------------------------------------------------------------
# CRAFTY: datos de conexión a la API del panel
# ---------------------------------------------------------------
export CRAFTY_URL="https://localhost:8443"
export CRAFTY_TOKEN="CRAFTY_API_KEY"
export SERVER_ID="a9f17c0f-8870-40b5-af3a-8947e8c759a2"
export CRAFTY_DIR="$HOME/Dir/to/crafty-4"

# ---------------------------------------------------------------
# PUERTOS: cuál mira internet y cuál usa Java internamente
# ---------------------------------------------------------------
export MC_PUBLIC_PORT="56768"     # el que abrís en el router, escucha el gateway
export MC_INTERNAL_HOST="127.0.0.1"
export MC_INTERNAL_PORT="25565"   # el que realmente usa Java (server.properties)

# ---------------------------------------------------------------
# TIEMPOS: cuánto tarda en apagar todo por inactividad
# ---------------------------------------------------------------
export IDLE_LIMIT_SECONDS=150       # sin jugadores durante este tiempo -> apaga el server MC
export CRAFTY_IDLE_SECONDS=300      # tiempo extra sin reconexión -> apaga Crafty
export CHECK_INTERVAL_SECONDS=30    # cada cuánto chequea si hay jugadores
export STARTUP_TIMEOUT_SECONDS=30  # cuánto espera a que el server levante antes de rendirse

# ---------------------------------------------------------------
# MENSAJES: lo que ven tus amigos en el cliente de Minecraft
# ---------------------------------------------------------------
# Podés usar estas variables DENTRO del texto, entre llaves, y se
# reemplazan solas por los valores calculados a partir de los tiempos
# de arriba (IDLE_LIMIT_SECONDS, CRAFTY_IDLE_SECONDS, STARTUP_TIMEOUT_SECONDS).
# Así, si cambiás esos tiempos, el mensaje se actualiza solo sin que
# tengas que reescribir el texto:
#   {idle_min}             -> minutos sin jugadores hasta que se apaga el server MC
#   {crafty_idle_min}      -> minutos extra hasta que se apaga Crafty
#   {startup_timeout_seg}  -> segundos que espera el arranque antes de rendirse
#
# Ejemplo: "El server se apaga solo a los {idle_min} min sin gente" con
# IDLE_LIMIT_SECONDS=300 se muestra como "...a los 5.0 min sin gente".

# Este es el texto que aparece en la LISTA de servidores mientras
# el server está apagado y nadie lo despertó todavía.
export MOTD_DORMIDO="Estoy ZZZ pibe... Conectate pa despertarme"

# Este es el texto que aparece en la lista mientras se está iniciando
# (después de que alguien ya intentó conectarse).
export MOTD_INICIANDO="Para wachin, ya me levanto..."

# Este es el mensaje de kick que ve el jugador si aprieta "Conectar"
# mientras el server todavía no está listo.
export KICK_MENSAJE="Ya me levanto (esperá ~{startup_timeout_seg}s)..."

# ---------------------------------------------------------------
# LOG: límite de tamaño del archivo gateway.log (evita el bugaso de 27GB)
# ---------------------------------------------------------------
# Ruta del archivo de log. Por defecto: gateway.log al lado de gateway.py
export LOG_FILE="$HOME/Dir/a/tu/server/gateway.log"

# Tamaño máximo de CADA archivo de log antes de rotar. Podés escribirlo
# como bytes planos (ej: 10485760) o con unidad: "10 MB", "1024KB", "1GB".
export LOG_MAX_BYTES="10 MB"

# Cuántos archivos viejos (gateway.log.1, .2, .3...) conserva antes de
# empezar a borrar los más antiguos. Con 10MB x 3 backups, el log nunca
# va a pesar más de ~40MB en total.
export LOG_BACKUP_COUNT=3

# Si además de al archivo querés que el gateway imprima por stdout
# (útil si lo corrés como servicio systemd y mirás con journalctl).
# Poné "0" si solo querés el archivo.
export LOG_TO_STDOUT="1"

# Ventana (en segundos) para agrupar intentos repetidos de la MISMA ip.
# En vez de una línea de log por cada golpe de un bot escaneando el puerto,
# se loguea el primero y después un resumen ("IP x.x.x.x: N intentos en
# los últimos X segundos") una vez que se cierra la ventana. Esto es lo
# que evita que un escaneo insistente vuelva a inflar el log como pasó
# con el bug de los 27GB.
export LOG_SUPPRESS_WINDOW_SECONDS=60

# ---------------------------------------------------------------
# CRAFTY.LOG: mismo problema que el gateway.log, pero para la salida
# (stdout/stderr) del proceso de Crafty. Antes se abria con "ab" sin
# limite y podia crecer varios GB. Ahora rota igual que gateway.log.
# ---------------------------------------------------------------
# Ruta del archivo de log de Crafty.
export CRAFTY_LOG_FILE="$HOME/Dir/a/tu/server/autostart/crafty.log"

# Tamano maximo de CADA archivo antes de rotar. Podes escribirlo como
# bytes planos (ej: 20971520) o con unidad: "20 MB", "1024 KB", "1 GB".
export CRAFTY_LOG_MAX_BYTES="10 MB"

# Cuantos archivos viejos (crafty.log.1, .2, .3...) conserva antes de
# empezar a borrar los mas antiguos. Con 20MB x 3 backups, crafty.log
# nunca va a pesar mas de ~80MB en total.
export CRAFTY_LOG_BACKUP_COUNT=3

# Nivel de detalle del log de Crafty:
#   "INFO"    -> loguea todo (arranques, paradas, avisos y errores)
#   "WARNING" -> solo loguea warnings y errores, descarta los INFO
export CRAFTY_LOG_LEVEL="INFO"
