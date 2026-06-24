#!/usr/bin/env bash
# Claude Code status line: model, effort, context usage, session usage, renewal time

input=$(cat)

# --- model & thinking ---
model=$(echo "$input" | jq -r '.model.display_name // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')
thinking=$(echo "$input" | jq -r '.thinking.enabled // false')

# --- context window ---
ctx_used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
ctx_total=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
ctx_used_abs=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')

# --- rate limits ---
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_resets=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
seven_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
seven_resets=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

# --- ANSI colors (dimmed-friendly) ---
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'
CYAN='\033[36m'
YELLOW='\033[33m'
GREEN='\033[32m'
MAGENTA='\033[35m'
RED='\033[31m'
BLUE='\033[34m'

parts=()

# model
if [ -n "$model" ]; then
    parts+=("$(printf "${CYAN}${BOLD}%s${RESET}" "$model")")
fi

# effort / thinking
if [ -n "$effort" ]; then
    parts+=("$(printf "${YELLOW}effort:${BOLD}%s${RESET}" "$effort")")
elif [ "$thinking" = "true" ]; then
    parts+=("$(printf "${YELLOW}thinking${RESET}")")
fi

# context usage: absolute (used/total) and percent
if [ -n "$ctx_used_abs" ] && [ -n "$ctx_total" ] && [ -n "$ctx_used_pct" ]; then
    if [ "$(echo "$ctx_used_pct > 80" | bc -l 2>/dev/null)" = "1" ]; then
        ctx_color="$RED"
    elif [ "$(echo "$ctx_used_pct > 50" | bc -l 2>/dev/null)" = "1" ]; then
        ctx_color="$YELLOW"
    else
        ctx_color="$GREEN"
    fi
    ctx_used_k=$(echo "$input" | jq -r '(.context_window.total_input_tokens / 1000) | floor | tostring + "k"')
    ctx_total_k=$(echo "$input" | jq -r '(.context_window.context_window_size / 1000) | floor | tostring + "k"')
    ctx_pct_fmt=$(printf "%.0f" "$ctx_used_pct")
    parts+=("$(printf "${MAGENTA}ctx:${ctx_color}${BOLD}%s/%s${RESET}${DIM}(${ctx_pct_fmt}%%)${RESET}" "$ctx_used_k" "$ctx_total_k")")
fi

# helper: format seconds until reset as "Xh Ym" or "Ym"
format_renewal() {
    local resets_at="$1"
    [ -z "$resets_at" ] && return
    local now
    now=$(date +%s)
    local secs=$(( resets_at - now ))
    [ "$secs" -le 0 ] && echo "now" && return
    local h=$(( secs / 3600 ))
    local m=$(( (secs % 3600) / 60 ))
    if [ "$h" -gt 0 ]; then
        echo "${h}h ${m}m"
    else
        echo "${m}m"
    fi
}

# 5-hour session limit
if [ -n "$five_pct" ]; then
    five_pct_fmt=$(printf "%.0f" "$five_pct")
    if [ "$(echo "$five_pct > 80" | bc -l 2>/dev/null)" = "1" ]; then
        sl_color="$RED"
    elif [ "$(echo "$five_pct > 50" | bc -l 2>/dev/null)" = "1" ]; then
        sl_color="$YELLOW"
    else
        sl_color="$GREEN"
    fi
    renewal=$(format_renewal "$five_resets")
    if [ -n "$renewal" ]; then
        parts+=("$(printf "${BLUE}5h:${sl_color}${BOLD}%s%%${RESET}${DIM}(renews %s)${RESET}" "$five_pct_fmt" "$renewal")")
    else
        parts+=("$(printf "${BLUE}5h:${sl_color}${BOLD}%s%%${RESET}" "$five_pct_fmt")")
    fi
fi

# 7-day session limit
if [ -n "$seven_pct" ]; then
    seven_pct_fmt=$(printf "%.0f" "$seven_pct")
    if [ "$(echo "$seven_pct > 80" | bc -l 2>/dev/null)" = "1" ]; then
        wl_color="$RED"
    elif [ "$(echo "$seven_pct > 50" | bc -l 2>/dev/null)" = "1" ]; then
        wl_color="$YELLOW"
    else
        wl_color="$GREEN"
    fi
    renewal=$(format_renewal "$seven_resets")
    if [ -n "$renewal" ]; then
        parts+=("$(printf "${BLUE}7d:${wl_color}${BOLD}%s%%${RESET}${DIM}(renews %s)${RESET}" "$seven_pct_fmt" "$renewal")")
    else
        parts+=("$(printf "${BLUE}7d:${wl_color}${BOLD}%s%%${RESET}" "$seven_pct_fmt")")
    fi
fi

# join parts with separator
sep="$(printf "${DIM} | ${RESET}")"
result=""
for part in "${parts[@]}"; do
    if [ -z "$result" ]; then
        result="$part"
    else
        result="${result}${sep}${part}"
    fi
done

printf "%b\n" "$result"
