# shellcheck shell=bash
# clashgate i18n: zh (source text) | en | ru.
# Language order: CLASHGATE_LANG (this run) > CLASHGATE_LANG saved in /etc/clashgate/clashgate.env
# (installer picker / `clashgate lang`) > LC_ALL/LANG (en* -> en, ru* -> ru) > zh.
# Source strings are Chinese; in en/ru mode every user-facing message is looked up in i18n.<lang>.tsv
# ("%s" = placeholder). Unmapped text falls back to Chinese. Persian (fa) is panel-only (terminals render RTL badly).
_cs_lang_norm() { # any spelling -> zh|en|ru, or nothing
  case ${1:-} in
    en|EN|en_*|en-*|English|english) echo en ;;
    ru|RU|ru_*|ru-*) echo ru ;;
    zh|ZH|zh_*|zh-*|cn|CN) echo zh ;;
  esac
}
_cs_lang_saved() { # CLASHGATE_LANG persisted in the install env file (root only; silent otherwise)
  local f=${CS_LANG_FILE:-/etc/clashgate/clashgate.env} v   # CS_LANG_FILE: tests only
  [[ -r $f ]] || return 0
  v=$(sed -n 's/^CLASHGATE_LANG="\{0,1\}\([A-Za-z_-]*\)"\{0,1\}$/\1/p' "$f" 2>/dev/null | tail -n1)
  _cs_lang_norm "$v"
}
_cs_lang_detect() {
  local v
  v=$(_cs_lang_norm "${CLASHGATE_LANG:-}"); [[ -n $v ]] && { echo "$v"; return; }
  v=$(_cs_lang_saved); [[ -n $v ]] && { echo "$v"; return; }
  v=$(_cs_lang_norm "${LC_ALL:-}"); [[ -n $v ]] || v=$(_cs_lang_norm "${LANG:-}")   # LC_ALL=C.UTF-8 -> look at LANG
  echo "${v:-zh}"
}
CS_LANG=$(_cs_lang_detect)
CS_LANG_SAVED=$(_cs_lang_saved)   # what save_env writes back (installer / `clashgate lang` change it)
export CS_LANG

if [[ $CS_LANG != zh ]]; then
  declare -A _EN=()
  _EN_KEYS=()
  _cs_load_en() {
    local f k v
    f="$(dirname "${BASH_SOURCE[0]}")/i18n.$CS_LANG.tsv"
    [[ -r $f ]] || return 0
    while IFS=$'\t' read -r k v; do
      [[ -n $k && -n $v ]] || continue
      _EN[$k]=$v; _EN_KEYS+=("$k")
    done < "$f"
    # longest (most specific) keys first
    mapfile -t _EN_KEYS < <(for k in "${_EN_KEYS[@]}"; do printf '%d\t%s\n' "${#k}" "$k"; done | sort -t$'\t' -k1,1nr | cut -f2-)
  }
  _cs_load_en
fi

# L 中文 English: short inline labels. Russian comes from i18n.ru.tsv (keyed by the Chinese text), else English.
L() {
  case $CS_LANG in
    en) builtin printf '%s' "$2" ;;
    ru) builtin printf '%s' "${_EN[$1]-$2}" ;;
    *)  builtin printf '%s' "$1" ;;
  esac
}

if [[ $CS_LANG != zh ]]; then
  _tr_fmt() { REPLY=${_EN[$1]-$1}; }

  # translate an expanded message; keys with %s act as patterns
  _tr_msg() {
    local msg=$1 key segs k seg rest cap i n out en part caps
    REPLY=$msg
    local LC_ALL=C
    [[ $msg =~ [^[:print:][:space:][:cntrl:]] ]] || return 0
    if [[ -n ${_EN[$msg]+x} ]]; then REPLY=${_EN[$msg]}; return 0; fi
    for key in "${_EN_KEYS[@]}"; do
      [[ $key == *%s* ]] || continue
      [[ $msg == "${key%%\%s*}"* ]] || continue
      segs=(); k=$key
      while [[ $k == *%s* ]]; do segs+=("${k%%\%s*}"); k=${k#*%s}; done
      segs+=("$k")
      n=${#segs[@]}; rest=${msg#"${segs[0]}"}; caps=()
      local ok=1
      for ((i = 1; i < n; i++)); do
        seg=${segs[i]}
        if ((i == n - 1)); then
          [[ $rest == *"$seg" ]] || { ok=0; break; }
          caps+=("${rest%"$seg"}")
        else
          [[ $rest == *"$seg"* ]] || { ok=0; break; }
          caps+=("${rest%%"$seg"*}"); rest=${rest#*"$seg"}
        fi
      done
      ((ok)) || continue
      en=${_EN[$key]}; out=""; i=0
      while [[ $en == *%s* ]]; do
        part=${caps[i]-}; _tr_msg "$part"; out+="${en%%\%s*}$REPLY"; en=${en#*%s}; i=$((i + 1))
      done
      REPLY="$out$en"; return 0
    done
    return 0
  }

  printf() {
    local a=("$@") i=0 j
    ((${#a[@]})) || return 0
    [[ ${a[0]} == -v ]] && i=2
    _tr_fmt "${a[i]-}"; a[i]=$REPLY
    for ((j = i + 1; j < ${#a[@]}; j++)); do _tr_msg "${a[j]}"; a[j]=$REPLY; done
    builtin printf "${a[@]}"
  }
  echo() {
    local a=("$@") j
    for j in "${!a[@]}"; do [[ ${a[j]} == -* ]] && continue; _tr_msg "${a[j]}"; a[j]=$REPLY; done
    builtin echo "${a[@]}"
  }
else
  _tr_msg() { REPLY=$1; }
fi
