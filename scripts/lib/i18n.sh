# shellcheck shell=bash
# clashgate i18n: CLASHGATE_LANG=en|zh (default: LC_ALL/LANG starting with "en" -> en, else zh).
# Source strings are Chinese; in English mode every user-facing message is looked up in i18n.en.tsv
# ("%s" = placeholder). Unmapped text falls back to Chinese.
_cs_lang_detect() {
  case ${CLASHGATE_LANG:-} in
    en|EN|en_*|en-*) echo en; return ;;
    zh|ZH|zh_*|zh-*) echo zh; return ;;
  esac
  case ${LC_ALL:-${LANG:-}} in en*) echo en ;; *) echo zh ;; esac
}
CS_LANG=$(_cs_lang_detect)
export CS_LANG

L() { if [[ $CS_LANG == en ]]; then builtin printf '%s' "$2"; else builtin printf '%s' "$1"; fi; }

if [[ $CS_LANG == en ]]; then
  declare -A _EN=()
  _EN_KEYS=()
  _cs_load_en() {
    local f k v
    f="$(dirname "${BASH_SOURCE[0]}")/i18n.en.tsv"
    [[ -r $f ]] || return 0
    while IFS=$'\t' read -r k v; do
      [[ -n $k && -n $v ]] || continue
      _EN[$k]=$v; _EN_KEYS+=("$k")
    done < "$f"
    # longest (most specific) keys first
    mapfile -t _EN_KEYS < <(for k in "${_EN_KEYS[@]}"; do printf '%d\t%s\n' "${#k}" "$k"; done | sort -t$'\t' -k1,1nr | cut -f2-)
  }
  _cs_load_en

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
