# AIsktagOS: встроенный ИИ Mind в zsh. Подключается из ~/.zshrc.
#   Ctrl+G   — превратить описание в строке в команду (она только подставится, запускаете вы)
#   ai …     — спросить (знаки ? и * в вопросе не раскрываются как шаблоны)
#   ai why   — разобрать ошибку последней команды
command -v ai >/dev/null || return 0

alias ai='noglob ai'

# Запоминаем предыдущую команду и её код возврата для «ai why»
autoload -Uz add-zsh-hook
_aisktag_precmd() { _aisktag_status=$?; }
_aisktag_preexec() {
    export AI_PREV_CMD="$_aisktag_cur" AI_PREV_STATUS="${_aisktag_status:-0}"
    _aisktag_cur="$1"
}
add-zsh-hook precmd _aisktag_precmd
add-zsh-hook preexec _aisktag_preexec

# Ctrl+G: «найти файлы больше 100 МБ» → find . -type f -size +100M
_aisktag_ai_cmd() {
    [[ -z $BUFFER ]] && { zle -M "Mind: сначала опишите задачу словами, затем Ctrl+G"; return; }
    local task=$BUFFER out
    zle -M "⏳ Mind думает…"
    zle -R
    if out=$(ai cmd "$task" 2>/dev/null) && [[ -n $out ]]; then
        BUFFER=$out
        CURSOR=${#BUFFER}
        zle -M "Mind предложил команду — проверьте и нажмите Enter"
    else
        zle -M "Mind: не удалось получить команду (ai status)"
    fi
}
zle -N _aisktag_ai_cmd
bindkey '^G' _aisktag_ai_cmd
