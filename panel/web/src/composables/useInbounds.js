// Panel state and actions for the home page inbound list and add-node form.
// Split out of usePanel.js: `p` carries the shared state and helpers usePanel creates first.
import { reactive, computed, watch } from 'vue'
import { t } from '../i18n.js'

export function useInbounds(p) {
  const { busyKey, openConfirmDialog, postAction, state } = p

  // 1.44, custom server: the options the safe defaults lock, as optional fields of the add-node form.
  // Blank = the default (random secret, default cipher ...), so nothing changes for users who skip
  // them. Sent as adv_<key>; the server reads them only in custom server mode.
  const PW = { key: 'password', desc: '密码' }
  const USER = { key: 'username', desc: '用户名' }
  const ADV_FIELDS = {
    'vless-reality': [
      { key: 'uuid', desc: 'UUID', wide: true },
      { key: 'short_id', desc: 'Short ID' },
      { key: 'vless_enc', desc: '量子加密', options: [{ value: '', desc: '开启（默认）' }, { value: 'off', desc: '关闭' }] },
      { key: 'reality_key', desc: 'Reality 私钥', wide: true },
    ],
    'vless-enc': [{ key: 'uuid', desc: 'UUID', wide: true }],
    // 1.45: plain options; blank host = this server's domain, blank path = random
    'vless-xhttp': [
      { key: 'host', desc: 'Host' },
      { key: 'path', desc: '路径' },
      {
        key: 'mode',
        desc: 'XHTTP 模式',
        options: [{ value: '', desc: 'auto（默认）' }].concat(
          ['stream-one', 'stream-up', 'packet-up'].map((v) => ({ value: v, desc: v }))
        ),
      },
      { key: 'vless_enc', desc: '量子加密', options: [{ value: '', desc: '开启（默认）' }, { value: 'off', desc: '关闭' }] },
      { key: 'uuid', desc: 'UUID', wide: true },
    ],
    hysteria2: [
      { ...PW, wide: true },
      { key: 'obfs', desc: '混淆', options: [{ value: '', desc: '关闭（默认）' }, { value: 'salamander', desc: 'Salamander' }] },
      { key: 'obfs_password', desc: '混淆密码' },
    ],
    shadowsocks: [
      {
        key: 'cipher',
        desc: '加密方式',
        wide: true,
        options: [{ value: '', desc: 'aes-256-gcm（默认）' }].concat(
          ['aes-128-gcm', 'chacha20-ietf-poly1305', 'xchacha20-ietf-poly1305',
            '2022-blake3-aes-128-gcm', '2022-blake3-aes-256-gcm', '2022-blake3-chacha20-poly1305'].map((v) => ({ value: v, desc: v }))
        ),
      },
      { ...PW, wide: true },
    ],
    snell: [{ key: 'psk', desc: 'PSK', wide: true }],
    anytls: [USER, PW],
    shadowquic: [USER, PW],
    sudoku: [
      { key: 'aead', desc: 'AEAD 加密', options: [{ value: '', desc: 'chacha20-poly1305（默认）' }, { value: 'aes-128-gcm', desc: 'aes-128-gcm' }] },
      { key: 'table', desc: '表格类型', options: [{ value: '', desc: 'prefer_ascii（默认）' }, { value: 'prefer_entropy', desc: 'prefer_entropy' }] },
    ],
    tuic: [{ key: 'uuid', desc: 'UUID', wide: true }, { ...PW, wide: true }],
    trusttunnel: [USER, PW],
    mieru: [USER, PW],
    http: [USER, PW],
    socks: [USER, PW],
  }

  const PROTOCOLS = [
    {
      value: 'vless-reality',
      label: 'VLESS Reality',
      defaultName: 'VlessReality',
      desc: '免证书的新一代协议',
      lockedNote: '已锁定安全默认：默认启用量子加密。SNI 可自填，留空从内置域名池随机抽取',
    },
    {
      value: 'vless-enc',
      label: 'VLESS Encryption',
      defaultName: 'VlessEnc',
      desc: '用来替代 SS 的新一代裸奔协议',
      lockedNote: '已锁定安全默认：量子加密 (mlkem768x25519plus) 与 XTLS Vision，UUID 与密钥自动生成，支持 UDP',
    },
    {
      // 1.45: listed only with the custom server mode on (customOnly)
      value: 'vless-xhttp',
      label: 'VLESS XHTTP',
      defaultName: 'VlessXhttp',
      desc: 'XHTTP 传输的 VLESS，内置量子加密，支持 CDN',
      lockedNote: '仅在自定义服务端模式下可用，需要证书',
      customOnly: true,
    },
    {
      value: 'hysteria2',
      label: 'Hysteria2',
      defaultName: 'Hysteria2',
      desc: '新一代 UDP 协议',
      lockedNote: '已启用安全默认：密码随机生成，不开启混淆，保持标准 HTTP/3 外观',
    },
    {
      value: 'shadowsocks',
      label: 'Shadowsocks',
      defaultName: 'Shadowsocks',
      desc: '经典轻量级加密协议，默认锁定 aes-256-gcm',
      lockedNote: '已锁定安全默认：加密算法固定为 aes-256-gcm，密码自动随机生成',
    },
    {
      value: 'snell',
      label: 'Snell V6',
      defaultName: 'SnellV6',
      desc: '轻量高效的私有协议，内置基于 PSK 的流量整形',
      lockedNote: '已锁定安全默认：PSK 自动随机生成，流量整形使用 v6 默认模式',
    },
    {
      value: 'anytls',
      label: 'AnyTLS',
      defaultName: 'AnyTLS',
      desc: '内置随机填充与随机指纹的新一代 TLS 协议',
      lockedNote: '已锁定安全默认：客户端 TLS 指纹与长度填充策略均自动随机生成',
    },
    {
      value: 'shadowquic',
      label: 'ShadowQUIC',
      defaultName: 'ShadowQUIC',
      desc: '免证书的新一代 QUIC 协议，内置随机 JLS 伪装',
      lockedNote: '已锁定安全默认：伪装地址 (JLS) 可自填，留空从内置域名池随机抽取，拥塞控制默认 bbr，关闭 0-RTT',
    },
    {
      value: 'sudoku',
      label: 'Sudoku',
      defaultName: 'Sudoku',
      desc: '基于数独流量特征变换与 chacha20 加密的抗审查协议',
      lockedNote: '已锁定安全默认：AEAD 加密固定为 chacha20-poly1305，密钥对自动生成',
    },
    {
      value: 'tuic',
      label: 'TUIC',
      defaultName: 'TUIC',
      desc: '基于 QUIC 的低延迟 UDP 协议',
      lockedNote: '已启用安全默认：UUID 与密码随机生成，关闭 0-RTT（防重放），native UDP 转发',
    },
    {
      value: 'trusttunnel',
      label: 'TrustTunnel',
      defaultName: 'TrustTunnel',
      desc: '基于标准 HTTP/2 与 HTTP/3 的高隐蔽 TLS 隧道协议',
      lockedNote: '已启用安全默认：强随机密码与 TLS 证书加密传输',
    },
    {
      value: 'mieru',
      label: 'Mieru',
      defaultName: 'Mieru',
      desc: '抗深度包检测（DPI）的混淆传输代理协议',
      lockedNote: '已启用安全默认：强随机密码与抗 DPI 流量混淆',
    },
    {
      value: 'http',
      label: 'HTTP',
      defaultName: 'HTTP',
      desc: '通用 HTTP / HTTPS 代理协议',
      lockedNote: '已启用安全默认：鉴权密码自动随机生成，有证书时默认开启 TLS',
    },
    {
      value: 'socks',
      label: 'SOCKS5',
      defaultName: 'SOCKS5',
      desc: '通用 SOCKS5 代理协议，支持 UDP 转发',
      lockedNote: '已启用安全默认：鉴权密码自动随机生成，默认开启 UDP，有证书时默认开启 TLS',
    },
  ]

  // A select shows blank until its model matches an option: start every select on its '' (默认) option.
  // '' is never sent (see submitAddInbound), so the server still applies its default.
  function advDefaults(kind) {
    return Object.fromEntries((ADV_FIELDS[kind] || []).filter((f) => f.options).map((f) => [f.key, '']))
  }

  const DEFAULT_NAMES = Object.fromEntries(PROTOCOLS.map((p) => [p.value, p.defaultName]))
  const PROTOCOL_MAP = Object.fromEntries(PROTOCOLS.map((p) => [p.value, p]))

  const inboundForm = reactive({
    kind: 'vless-reality',
    name: 'VlessReality',
    port: '',
    tuic_cc: 'bbr',
    tt_cc: 'bbr',
    mieru_transport: 'TCP',
    // 1.45: TLS on by default when there is a certificate (else the password goes over the wire in clear)
    http_tls: state.certs_present ? '1' : '0',
    socks_tls: state.certs_present ? '1' : '0',
    sni: '',
    adv: advDefaults('vless-reality'),
  })

  const currentProtocol = computed(() => PROTOCOL_MAP[inboundForm.kind] || PROTOCOLS[0])
  const currentDefaultName = computed(() => DEFAULT_NAMES[inboundForm.kind] || 'VlessReality')
  // Protocols that show one extra option field (SNI or a select) in the add-node form.
  const PROTOCOL_HAS_OPTION = new Set(['vless-reality', 'shadowquic', 'tuic', 'trusttunnel', 'mieru', 'http', 'socks'])
  const sniEditable = computed(() =>
    inboundForm.kind === 'vless-reality' || inboundForm.kind === 'shadowquic'
  )

  watch(
    () => inboundForm.kind,
    (newKind, oldKind) => {
      const oldDefault = DEFAULT_NAMES[oldKind] || ''
      const newDefault = DEFAULT_NAMES[newKind] || newKind
      if (!inboundForm.name.trim() || inboundForm.name.trim() === oldDefault) {
        inboundForm.name = newDefault
      }
      inboundForm.adv = advDefaults(newKind)   // the optional fields belong to one protocol
    }
  )

  watch(
    () => state.certs_present,
    (has) => {
      inboundForm.http_tls = has ? '1' : '0'
      inboundForm.socks_tls = has ? '1' : '0'
    }
  )

  // A custom-only protocol (VLESS XHTTP) leaves the form when the custom server mode is turned off.
  watch(
    () => state.custom_server_enabled,
    (on) => {
      if (!on && (PROTOCOL_MAP[inboundForm.kind] || {}).customOnly) inboundForm.kind = 'vless-reality'
    }
  )

  let pendingAddReqId = ''

  async function submitAddInbound() {
    if (busyKey.value) return
    if (!pendingAddReqId) {
      pendingAddReqId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    }
    const payload = {
      kind: inboundForm.kind,
      name: inboundForm.name.trim() || currentDefaultName.value,
      port: inboundForm.port.trim(),
      tuic_cc: inboundForm.tuic_cc,
      tt_cc: inboundForm.tt_cc,
      mieru_transport: inboundForm.mieru_transport,
      http_tls: inboundForm.http_tls,
      socks_tls: inboundForm.socks_tls,
      sni: sniEditable.value ? inboundForm.sni.trim() : '',
      req_id: pendingAddReqId,
    }
    if (state.custom_server_enabled) {
      for (const f of ADV_FIELDS[inboundForm.kind] || []) {
        const v = String(inboundForm.adv[f.key] || '').trim()
        if (v) payload['adv_' + f.key] = v
      }
    }
    const res = await postAction('/inbounds/add', payload, 'add-inbound')
    // No answer (timeout / dropped connection): keep the id so a retry is not added twice.
    if (res) pendingAddReqId = ''
    if (res && res.ok) {
      inboundForm.port = ''
      inboundForm.sni = ''
      inboundForm.adv = advDefaults(inboundForm.kind)
      inboundForm.name = currentDefaultName.value
    }
  }

  function resetInboundPassword(item) {
    if (!item || !item.reset_url) return
    openConfirmDialog({
      title: t('重置密码'),
      message: t('确定重置节点「{name}」的密码？点顶部「应用配置」后生效，客户端需要重新更新订阅。', { name: item.name }),
      confirmText: t('确认重置'),
      tone: 'amber',
      onConfirm: () => postAction(item.reset_url, {}, `rst-${item.key}`),
    })
  }

  function deleteInbound(item) {
    if (!item || !item.delete_url) return
    openConfirmDialog({
      title: t('删除节点'),
      message: t('确定删除节点「{name}」？点顶部「应用配置」后生效。', { name: item.name }),
      confirmText: t('确认删除'),
      tone: 'rose',
      onConfirm: () => postAction(item.delete_url, {}, `del-${item.key}`),
    })
  }

  return {
    ADV_FIELDS,
    PROTOCOLS,
    DEFAULT_NAMES,
    PROTOCOL_MAP,
    inboundForm,
    currentProtocol,
    currentDefaultName,
    PROTOCOL_HAS_OPTION,
    sniEditable,
    pendingAddReqId,
    submitAddInbound,
    resetInboundPassword,
    deleteInbound,
  }
}
